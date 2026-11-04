"""Shared plumbing for Develop Spaces: shapes, mixing, loudness, true peak and the safety limiter.

Every effect in this folder takes x as float32 (samples, channels) and returns float32 (samples, channels).
"""
import numpy as np
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import resample_poly
from math import gcd

try:
    import pyloudnorm as _pyln
except Exception:
    _pyln = None

CEILING_DBTP = -1.0

def as2d(x):
    """Return x as a float32 array of shape (samples, channels)."""
    a = np.asarray(x)
    if a.ndim == 1:
        a = a[:, None]
    if a.ndim != 2:
        raise ValueError("audio must be (samples,) or (samples, channels)")
    return a.astype(np.float32, copy=False)

def to_stereo64(x):
    """float64 (samples, 2): mono is copied to both sides, more than two channels keep the first two."""
    a = as2d(x).astype(np.float64)
    if a.shape[1] == 1:
        return np.repeat(a, 2, axis=1)
    return a[:, :2].copy()

def pad_to(a, n, front=0):
    """Zero pad a (samples, ch) to n samples, with `front` zeros before it."""
    out = np.zeros((n, a.shape[1]), dtype=a.dtype)
    m = min(a.shape[0], n - front)
    out[front:front + m] = a[:m]
    return out

def resample(x, sr_in, sr_out):
    if sr_in == sr_out:
        return x
    g = gcd(int(sr_in), int(sr_out))
    return resample_poly(x, sr_out // g, sr_in // g, axis=0)

def true_peak_db(y, os=4):
    """True peak in dBTP by 4x polyphase oversampling (a BS.1770 style estimate, scipy's Kaiser filter)."""
    a = np.asarray(y, dtype=np.float64)
    if a.ndim == 1:
        a = a[:, None]
    if a.shape[0] == 0:
        return -np.inf
    up = resample_poly(a, os, 1, axis=0)
    pk = max(np.max(np.abs(up)), np.max(np.abs(a)))
    return 20.0 * np.log10(pk) if pk > 0 else -np.inf

def lufs(y, sr):
    """Integrated loudness (BS.1770 gated) by pyloudnorm; RMS dBFS minus 0.691 for clips under half a second."""
    a = np.asarray(y, dtype=np.float64)
    if a.ndim == 1:
        a = a[:, None]
    if a.shape[0] >= int(0.5 * sr) and _pyln is not None:
        v = _pyln.Meter(sr).integrated_loudness(a)
        if np.isfinite(v):
            return float(v)
    e = np.mean(np.sum(a * a, axis=1))
    return float(-0.691 + 10 * np.log10(e + 1e-30))

def match_loudness(wet, ref, sr, gain_db=0.0):
    """Scale wet so its integrated loudness over the span of ref (its first len(ref) samples, at least
    half a second) equals ref's, plus gain_db. Measuring the wet over the dry's own span keeps a short
    hit's long tail from being pushed up to the hit's loudness. The gain is also capped so the wet's
    true peak never stands over the dry's (a spring's first chirp or a cave's first cluster would
    otherwise make the safety limiter work). Silent input leaves wet untouched."""
    lr = lufs(ref, sr)
    lw = lufs(wet[: max(int(ref.shape[0]), int(0.5 * sr))], sr)
    if not np.isfinite(lr) or not np.isfinite(lw) or lw < -120 or lr < -120:
        return wet
    g_db = lr - lw
    cap = true_peak_db(ref) - true_peak_db(wet)
    if np.isfinite(cap):
        g_db = min(g_db, cap)
    return wet * (10 ** ((g_db + gain_db) / 20.0))

def _release(h, coef):
    r = np.empty_like(h)
    prev = 1.0
    for i in range(h.shape[0]):
        v = prev + (1.0 - prev) * coef
        if h[i] < v:
            v = h[i]
        r[i] = v
        prev = v
    return r

try:
    from numba import njit
    _release = njit(cache=True)(_release)
except Exception:
    pass

def safety_limit(y, sr, ceiling_db=CEILING_DBTP, margin_db=0.3, look_ms=5.0, release_ms=150.0):
    """Gentle lookahead peak limiter on the 4x oversampled peak, linked across channels.

    Returns (y_out, max_gain_reduction_db). Untouched when the true peak is already under the ceiling.
    The gain is a min filter then a moving average of the same span (so it never exceeds the needed gain),
    then a slow release. Never a hard clip.
    """
    a = np.asarray(y, dtype=np.float64)
    tp = true_peak_db(a)
    if tp <= ceiling_db - 0.05:
        return a, 0.0
    thr = 10 ** ((ceiling_db - margin_db) / 20.0)
    n = a.shape[0]
    up = np.abs(resample_poly(a, 4, 1, axis=0))[: 4 * n]
    pk = np.max(up, axis=1)
    pk = np.pad(pk, (0, 4 * n - pk.shape[0]))
    pk = np.max(pk.reshape(n, 4), axis=1)
    pk = np.maximum(pk, np.max(np.abs(a), axis=1))
    pk = np.maximum(pk, np.maximum(np.roll(pk, 1), np.roll(pk, -1)))
    g = np.minimum(1.0, thr / np.maximum(pk, 1e-12))
    L = max(1, int(look_ms * 1e-3 * sr))
    h = minimum_filter1d(g, 2 * L + 1, mode="nearest")
    h = uniform_filter1d(h, 2 * L + 1, mode="nearest")
    h = np.minimum(h, g)
    coef = 1.0 - np.exp(-1.0 / (release_ms * 1e-3 * sr))
    r = _release(h.astype(np.float64), coef)
    out = a * r[:, None]
    for _ in range(4):
        tp2 = true_peak_db(out)
        if tp2 <= ceiling_db - 0.02:
            break
        out = out * 10 ** ((ceiling_db - 0.1 - tp2) / 20.0)
    return out, float(-20 * np.log10(max(np.min(r), 1e-12)))

def finish(dry, wet, mix, sr, front=0):
    """Equal power dry/wet mix (y = cos(mix pi/2) dry + sin(mix pi/2) wet), then the safety limiter, as
    float32. The wet of a space is uncorrelated with the dry, so equal power keeps the loudness level
    through the mix when the wet is loudness matched; mix 1 is the wet alone.

    dry is placed `front` samples late (a preverb lead), both are padded to the longer length.
    """
    dry = to_stereo64(dry)
    n = max(dry.shape[0] + front, wet.shape[0])
    d = pad_to(dry, n, front)
    w = pad_to(wet.astype(np.float64), n)
    m = float(np.clip(mix, 0.0, 1.0))
    gd = 0.0 if m >= 1.0 else float(np.cos(0.5 * np.pi * m))
    gw = float(np.sin(0.5 * np.pi * m))
    y = gd * d + gw * w
    y, _ = safety_limit(y, sr)
    return y.astype(np.float32)

def fade(a, n_in=0, n_out=0):
    """Raised-cosine fades in place on a (samples, ch) float array."""
    if n_in > 0:
        k = min(n_in, a.shape[0])
        a[:k] *= (0.5 - 0.5 * np.cos(np.pi * (np.arange(k) + 0.5) / n_in))[:, None]
    if n_out > 0:
        k = min(n_out, a.shape[0])
        a[a.shape[0] - k:] *= (0.5 + 0.5 * np.cos(np.pi * (np.arange(k) + 0.5) / n_out))[:, None]
    return a
