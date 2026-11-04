"""Measurements shared by the checks and the judging: test signals, harmonics, aliasing, clicks, wow and
flutter, band responses. Nothing here is used by the effects themselves.
"""
import numpy as np
from scipy import signal

import common as C

def tone(f, dur, sr, level_db=-12.0, phase=0.0):
    t = np.arange(int(dur * sr)) / sr
    return (C.undb(level_db) * np.sin(2 * np.pi * f * t + phase))[:, None]

def vowel(f0, dur, sr, formants=((700.0, 90.0), (1200.0, 110.0), (2600.0, 160.0)), level_db=-14.0):
    """A sung vowel: a band-limited pulse train at f0 through formant resonances."""
    import speakers as SP
    n = int(dur * sr)
    p = SP.blit(n, sr, f0)[:, None]
    y = np.zeros_like(p)
    for f, bw in formants:
        y += signal.lfilter(*_reson(f, bw, sr), p, axis=0)
    y = C.butter(y, sr, "highpass", 60.0)
    return y / np.max(np.abs(y)) * C.undb(level_db)

def _reson(f, bw, sr):
    r = np.exp(-np.pi * bw / sr)
    th = 2 * np.pi * f / sr
    return [1 - r], [1, -2 * r * np.cos(th), r * r]

def spectrum(y1, sr):
    """Magnitude spectrum (Blackman-Harris window, dB re the window's coherent gain), with its frequencies."""
    y1 = np.asarray(y1, dtype=np.float64)
    w = signal.windows.blackmanharris(y1.shape[0])
    Y = np.abs(np.fft.rfft(y1 * w)) / (w.sum() / 2.0)
    return np.fft.rfftfreq(y1.shape[0], 1.0 / sr), 20 * np.log10(Y + 1e-15)

def level_at(f, Y, fq, bw=3.0):
    sel = np.abs(f - fq) <= bw
    return float(Y[sel].max()) if np.any(sel) else -300.0

def harmonics(y1, sr, f0, k=5):
    f, Y = spectrum(y1, sr)
    return [level_at(f, Y, f0 * i, max(3.0, f0 * 0.002)) for i in range(1, k + 1)]

def alias_floor_db(y1, sr, f0, guard=6.0):
    """Energy outside the harmonic series of f0 (and DC), in dB relative to the fundamental: what folded over."""
    f, Y = spectrum(y1, sr)
    p = 10 ** (Y / 10.0)
    harm = np.zeros_like(f, dtype=bool)
    for k in range(1, int(f[-1] // f0) + 1):
        harm |= np.abs(f - k * f0) <= guard
    harm |= f < 40.0
    fund = level_at(f, Y, f0, guard)
    return 10 * np.log10(p[~harm].sum() + 1e-30) - fund

def band_response(fx, sr, freqs, dur=4.0, seed=7, **kw):
    """The magnitude in dB of an effect at freqs, from white noise in and out (Welch PSD ratio)."""
    rng = np.random.default_rng(seed)
    x = (rng.standard_normal((int(dur * sr), 1)) * 0.05).astype(np.float32)
    y = C.as2d(fx(x, sr, **kw))
    f, px = signal.welch(x[:, 0], sr, nperseg=8192)
    _, py = signal.welch(y[:, 0], sr, nperseg=8192)
    r = 10 * np.log10(py / np.maximum(px, 1e-30) + 1e-30)
    return np.interp(freqs, f, r)

def click_ratio(y, ref, sr, idx, win_ms=30.0):
    """The largest second difference of y within win_ms of each edit sample, against the largest second
    difference anywhere in ref (a clean reference of the same material). 1 means the edit is as smooth as the
    material; a hard cut on a sine reads in the hundreds."""
    y1 = C.as2d(y)
    r1 = C.as2d(ref)
    d2y = np.abs(np.diff(y1, 2, axis=0)).max(axis=1)
    d2r = np.abs(np.diff(r1, 2, axis=0)).max(axis=1)
    base = max(d2r.max(), 1e-12)
    W = int(sr * win_ms / 1000.0)
    worst = 0.0
    for i in idx:
        lo, hi = max(0, int(i) - W), min(d2y.shape[0], int(i) + W)
        if hi > lo:
            worst = max(worst, float(d2y[lo:hi].max() / base))
    return worst

def wow_flutter(y1, sr, f0=3150.0):
    """Peak wow (under 6 Hz) and peak flutter (6 to 100 Hz) in percent from a test tone at f0, skipping the edges."""
    f = C.inst_freq(y1, sr, smooth_ms=2.0)
    dev = f / f0 - 1.0
    cut = int(0.3 * sr)
    sos_w = signal.butter(2, 6.0, "lowpass", fs=sr, output="sos")
    sos_f = signal.butter(2, [6.0, 100.0], "bandpass", fs=sr, output="sos")
    w = signal.sosfiltfilt(sos_w, dev)[cut:-cut]
    fl = signal.sosfiltfilt(sos_f, dev)[cut:-cut]
    return 100 * float(np.max(np.abs(w - np.median(w)))), 100 * float(np.max(np.abs(fl)))

def zc_freq(y1, sr):
    """Frequency per sample of a single clean tone from its interpolated zero crossings (half periods)."""
    y1 = np.asarray(y1, dtype=np.float64)
    s = np.signbit(y1)
    i = np.flatnonzero(s[1:] != s[:-1])
    i = i[(y1[i] != y1[i + 1])]
    tz = i + y1[i] / (y1[i] - y1[i + 1])
    if tz.shape[0] < 3:
        return np.zeros_like(y1)
    mid = 0.5 * (tz[1:] + tz[:-1])
    fz = 0.5 * sr / np.diff(tz)
    return np.interp(np.arange(y1.shape[0]), mid, fz)

def xcorr_lag(a1, b1, maxlag):
    """The lag (samples) of b1 against a1 at the cross-correlation peak, within +-maxlag."""
    a1 = np.asarray(a1, dtype=np.float64)
    b1 = np.asarray(b1, dtype=np.float64)
    n = a1.shape[0]
    L = 1 << int(np.ceil(np.log2(2 * n)))
    r = np.fft.irfft(np.conj(np.fft.rfft(a1, L)) * np.fft.rfft(b1, L), L)
    r = np.concatenate([r[-maxlag:], r[:maxlag + 1]])
    return int(np.argmax(r)) - maxlag

def centroid(y1, sr):
    f, p = signal.welch(np.asarray(y1, dtype=np.float64), sr, nperseg=4096)
    return float((f * p).sum() / max(p.sum(), 1e-30))
