"""Shared DSP for Develop Character: shapes, mix and output safety, filters, readers, envelopes, loudness,
pitch tracking and the short-time Fourier transform. Every effect in this family is built on these pieces.

All arrays are float (samples, channels). Effects compute in float64 and hand back float32.
"""
import math

import numpy as np
from numba import njit
from scipy import signal

CEIL_DBTP = -1.2

def as2d(x):
    """float64 (samples, channels) view of x, which may be 1-D (mono) or 2-D."""
    a = np.asarray(x, dtype=np.float64)
    if a.ndim == 1:
        a = a[:, None]
    return a

def to_mono(a):
    return a.mean(axis=1, keepdims=True)

def fit_channels(a, ch):
    """a with ch channels: mono is copied out, stereo to mono is averaged."""
    if a.shape[1] == ch:
        return a
    if a.shape[1] == 1:
        return np.repeat(a, ch, axis=1)
    if ch == 1:
        return to_mono(a)
    return a[:, :ch]

def secs(t, sr):
    return int(round(float(t) * sr))

def as_list(v):
    """A time or a list of times from a number, a list or a comma string."""
    if v is None:
        return []
    if isinstance(v, str):
        return [float(s) for s in v.replace(";", ",").split(",") if s.strip()]
    if np.isscalar(v):
        return [float(v)]
    return [float(s) for s in v]

def db(v):
    return 20.0 * math.log10(max(float(v), 1e-12))

def undb(d):
    return 10.0 ** (float(d) / 20.0)

def true_peak(y, factor=4):
    """Linear true peak with factor x oversampling (polyphase, Kaiser window)."""
    a = as2d(y)
    if a.shape[0] == 0:
        return 0.0
    up = signal.resample_poly(a, factor, 1, axis=0)
    return float(max(np.max(np.abs(up)), np.max(np.abs(a))))

def true_peak_db(y, factor=4):
    return db(true_peak(y, factor))

@njit(cache=True)
def _release(req, rel):
    g = np.empty_like(req)
    cur = 1.0
    for i in range(req.shape[0]):
        r = req[i]
        if r < cur:
            cur = r
        else:
            cur = cur + (r - cur) * rel
            if cur > r:
                cur = r
        g[i] = cur
    return g

def safety_limit(y, sr, ceil_db=CEIL_DBTP, look_ms=2.0, release_ms=120.0):
    """A gentle look-ahead peak limiter on the 4x true peak. Untouched when already under the ceiling."""
    a = as2d(y)
    n = a.shape[0]
    if n == 0:
        return a
    for _ in range(4):
        tp = true_peak(a)
        if tp <= undb(ceil_db):
            return a
        up = np.abs(signal.resample_poly(a, 4, 1, axis=0))[: n * 4]
        if up.shape[0] < n * 4:
            up = np.pad(up, ((0, n * 4 - up.shape[0]), (0, 0)))
        pk = np.maximum(up.reshape(n, 4, -1).max(axis=(1, 2)), np.abs(a).max(axis=1))
        req = np.minimum(1.0, undb(ceil_db - 0.3) / np.maximum(pk, 1e-12))
        L = max(2, int(sr * look_ms / 1000.0))
        from scipy.ndimage import minimum_filter1d
        h = minimum_filter1d(req, size=L + 1, origin=-(L // 2), mode="nearest")
        rel = 1.0 - math.exp(-1.0 / (sr * release_ms / 1000.0))
        g = _release(h, rel)
        c = np.cumsum(np.concatenate([np.ones(L), g]))
        gs = (c[L:] - c[:-L]) / L
        a = a * gs[:n, None]
    tp = true_peak(a)
    if tp > undb(ceil_db):
        a = a * (undb(ceil_db) / tp)
    return a

def finish(x, y, mix=1.0, sr=48000, gain_db=0.0, limit=True):
    """The family's last step: the dry/wet mix, an output gain, and the safety limiter.
    mix 0 hands back x itself, bit for bit, whatever y is."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    xin = np.asarray(x)
    wet = as2d(y) * undb(gain_db)
    dry = as2d(xin)
    n = dry.shape[0]
    if wet.shape[0] != n:
        wet = wet[:n] if wet.shape[0] > n else np.pad(wet, ((0, n - wet.shape[0]), (0, 0)))
    ch = max(dry.shape[1], wet.shape[1])
    m = float(np.clip(mix, 0.0, 1.0))
    out = (1.0 - m) * fit_channels(dry, ch) + m * fit_channels(wet, ch)
    out[~np.isfinite(out)] = 0.0
    if limit:
        out = safety_limit(out, sr)
    out = out.astype(np.float32)
    if xin.ndim == 1 and out.shape[1] == 1:
        out = out[:, 0]
    return out

def sos_filter(a, sos, zero_phase=False):
    if zero_phase:
        return signal.sosfiltfilt(sos, a, axis=0)
    return signal.sosfilt(sos, a, axis=0)

def butter(a, sr, kind, fc, order=2, zero_phase=False):
    nyq = sr / 2.0
    if kind in ("bandpass", "bandstop"):
        lo, hi = fc
        hi = min(hi, nyq * 0.995)
        sos = signal.butter(order, [lo, hi], btype=kind, fs=sr, output="sos")
    else:
        fc = min(fc, nyq * 0.995)
        sos = signal.butter(order, fc, btype=kind, fs=sr, output="sos")
    return sos_filter(a, sos, zero_phase)

def rbj(kind, f0, sr, q=0.707, gain_db=0.0):
    """One RBJ cookbook biquad as an sos row (peak, lowshelf, highshelf, lowpass, highpass, bandpass, notch)."""
    f0 = min(f0, sr * 0.49)
    A = 10.0 ** (gain_db / 40.0)
    w = 2.0 * math.pi * f0 / sr
    cw, sw = math.cos(w), math.sin(w)
    al = sw / (2.0 * q)
    if kind == "peak":
        b = [1 + al * A, -2 * cw, 1 - al * A]
        a = [1 + al / A, -2 * cw, 1 - al / A]
    elif kind == "lowshelf":
        s = 2 * math.sqrt(A) * al
        b = [A * ((A + 1) - (A - 1) * cw + s), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - s)]
        a = [(A + 1) + (A - 1) * cw + s, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - s]
    elif kind == "highshelf":
        s = 2 * math.sqrt(A) * al
        b = [A * ((A + 1) + (A - 1) * cw + s), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - s)]
        a = [(A + 1) - (A - 1) * cw + s, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - s]
    elif kind == "lowpass":
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
        a = [1 + al, -2 * cw, 1 - al]
    elif kind == "highpass":
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
        a = [1 + al, -2 * cw, 1 - al]
    elif kind == "bandpass":
        b = [al, 0.0, -al]
        a = [1 + al, -2 * cw, 1 - al]
    elif kind == "notch":
        b = [1.0, -2 * cw, 1.0]
        a = [1 + al, -2 * cw, 1 - al]
    else:
        raise ValueError(kind)
    return np.array([[b[0] / a[0], b[1] / a[0], b[2] / a[0], 1.0, a[1] / a[0], a[2] / a[0]]])

def sos_chain(*rows):
    return np.concatenate([r for r in rows if r is not None and len(r)], axis=0)

def response(sos, sr, freqs):
    """Magnitude in dB of an sos chain at the given frequencies."""
    _, h = signal.sosfreqz(sos, worN=np.asarray(freqs, dtype=np.float64), fs=sr)
    return 20.0 * np.log10(np.maximum(np.abs(h), 1e-12))

def fir_from_response(freqs, gains_db, sr, taps=511):
    """A linear-phase FIR with the given magnitude (used with mode same, so it adds no delay)."""
    f = np.concatenate([[0.0], np.asarray(freqs, float), [sr / 2.0]])
    g = np.concatenate([[gains_db[0]], np.asarray(gains_db, float), [gains_db[-1]]])
    order = np.argsort(f)
    f, g = f[order], g[order]
    return signal.firwin2(taps, f, 10.0 ** (g / 20.0), fs=sr)

def fir_same(a, h):
    return signal.oaconvolve(a, h[:, None], mode="same", axes=0)

@njit(cache=True)
def _svf(x, fc, q, sr, mode):
    n, ch = x.shape
    out = np.zeros_like(x)
    k = 1.0 / q
    for c in range(ch):
        ic1 = 0.0
        ic2 = 0.0
        for i in range(n):
            f = fc[i]
            if f > sr * 0.49:
                f = sr * 0.49
            if f < 1.0:
                f = 1.0
            g = math.tan(math.pi * f / sr)
            a1 = 1.0 / (1.0 + g * (g + k))
            a2 = g * a1
            a3 = g * a2
            v0 = x[i, c]
            v3 = v0 - ic2
            v1 = a1 * ic1 + a2 * v3
            v2 = ic2 + a2 * ic1 + a3 * v3
            ic1 = 2.0 * v1 - ic1
            ic2 = 2.0 * v2 - ic2
            if mode == 0:
                out[i, c] = v2
            elif mode == 1:
                out[i, c] = v1 * k
            else:
                out[i, c] = v0 - k * v1 - v2
    return out

def svf(a, fc, sr, q=0.707, kind="lowpass"):
    """A state-variable filter (trapezoidal integrators) whose cutoff may change every sample without zipper or
    blow-up. fc: a number or one value per sample."""
    a = np.ascontiguousarray(as2d(a))
    fc = np.broadcast_to(np.asarray(fc, dtype=np.float64), (a.shape[0],)).copy()
    mode = {"lowpass": 0, "bandpass": 1, "highpass": 2}[kind]
    return _svf(a, fc, float(q), float(sr), mode)

@njit(cache=True)
def _onepole_tv(x, fc, sr):
    n, ch = x.shape
    out = np.zeros_like(x)
    for c in range(ch):
        s = 0.0
        for i in range(n):
            g = math.tan(math.pi * min(fc[i], sr * 0.49) / sr)
            G = g / (1.0 + g)
            v = (x[i, c] - s) * G
            lp = v + s
            s = lp + v
            out[i, c] = lp
    return out

def onepole_lp(a, fc, sr):
    a = np.ascontiguousarray(as2d(a))
    fc = np.broadcast_to(np.asarray(fc, dtype=np.float64), (a.shape[0],)).copy()
    return _onepole_tv(a, fc, float(sr))

@njit(cache=True)
def _read(x, pos, rate, zc):
    n, ch = x.shape
    m = pos.shape[0]
    out = np.zeros((m, ch))
    for i in range(m):
        p = pos[i]
        r = abs(rate[i])
        fcut = 1.0
        if r > 0.97:
            fcut = 0.97 / r
        hw = zc / fcut
        k0 = int(math.floor(p - hw)) + 1
        k1 = int(math.floor(p + hw))
        if k1 < 0 or k0 > n - 1:
            continue
        wsum = 0.0
        for k in range(k0, k1 + 1):
            t = k - p
            u = t / hw
            if u <= -1.0 or u >= 1.0:
                continue
            w = 0.42 + 0.5 * math.cos(math.pi * u) + 0.08 * math.cos(2.0 * math.pi * u)
            z = fcut * t
            if abs(z) < 1e-12:
                s = 1.0
            else:
                s = math.sin(math.pi * z) / (math.pi * z)
            h = fcut * s * w
            wsum += h
            if 0 <= k < n:
                for c in range(ch):
                    out[i, c] += h * x[k, c]
        if wsum > 1e-9:
            for c in range(ch):
                out[i, c] /= wsum
    return out

def read_at(a, pos, rate=None, zc=12.0):
    """Read a at fractional sample positions pos with a windowed-sinc kernel whose cutoff falls with the local read
    rate, so a fast read is filtered before it can alias. Positions outside the signal read silence.
    rate: the local |d pos / d n|; derived from pos when omitted."""
    a = np.ascontiguousarray(as2d(a))
    pos = np.ascontiguousarray(np.asarray(pos, dtype=np.float64))
    if rate is None:
        rate = np.abs(np.gradient(pos)) if pos.shape[0] > 1 else np.ones(1)
    rate = np.ascontiguousarray(np.asarray(rate, dtype=np.float64))
    return _read(a, pos, rate, float(zc))

_OS = {}

def os_filter(f):
    """The steep linear-phase filter for f x oversampling: flat to 20 kHz at 48 kHz, 90 dB down by 24 kHz."""
    if f not in _OS:
        _OS[f] = signal.firwin(128 * f + 1, 22000.0 / (24000.0 * f), window=("kaiser", 9.0))
    return _OS[f]

def oversample(a, f):
    return a if f <= 1 else signal.resample_poly(a, f, 1, axis=0, window=os_filter(f))

def undersample(a, f, n):
    if f <= 1:
        return a[:n]
    out = signal.resample_poly(a, 1, f, axis=0, window=os_filter(f))[:n]
    if out.shape[0] < n:
        out = np.pad(out, ((0, n - out.shape[0]), (0, 0)))
    return out

def raised(u):
    """0 to 1 over u in [0, 1] with zero slope at both ends."""
    u = np.clip(u, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * u)

def smooth_noise(n, sr, rate_hz, rng):
    """Zero-mean, unit-peak, band-limited random motion around rate_hz (Gaussian noise through a 2-pole band)."""
    if n <= 0:
        return np.zeros(0)
    m = int(n * 1.1) + int(sr / max(rate_hz, 0.05) * 4)
    w = rng.standard_normal(m)
    lo, hi = max(rate_hz * 0.5, 0.01), rate_hz * 1.6
    sos = signal.butter(2, [lo, hi], btype="bandpass", fs=sr, output="sos")
    v = signal.sosfiltfilt(sos, w)[m - n:]
    pk = np.max(np.abs(v))
    return v / pk if pk > 0 else v

@njit(cache=True)
def _follow(x, atk, rel):
    out = np.empty_like(x)
    s = 0.0
    for i in range(x.shape[0]):
        v = x[i]
        if v > s:
            s += (v - s) * atk
        else:
            s += (v - s) * rel
        out[i] = s
    return out

def coef(ms, sr):
    return 1.0 - math.exp(-1.0 / max(sr * ms / 1000.0, 1e-9))

def follow(v, sr, attack_ms, release_ms):
    """A one-pole peak follower on a non-negative detector signal."""
    return _follow(np.ascontiguousarray(np.asarray(v, dtype=np.float64)), coef(attack_ms, sr), coef(release_ms, sr))

def onsets(a, sr, thresh_db=-30.0, rise_db=9.0, min_gap=0.15):
    """Hit onsets: a fast envelope rising rise_db above a slow one, above thresh_db. Returns times in seconds."""
    d = np.abs(to_mono(as2d(a))[:, 0])
    fast = follow(d, sr, 0.5, 15.0)
    slow = follow(d, sr, 30.0, 60.0)
    fd = 20 * np.log10(fast + 1e-9)
    sd = 20 * np.log10(slow + 1e-9)
    hit = (fd - sd > rise_db) & (fd > thresh_db)
    out, last = [], -1e9
    idx = np.flatnonzero(hit[1:] & ~hit[:-1]) + 1
    for i in idx:
        t = i / sr
        if t - last >= min_gap:
            j = i
            lim = max(0, i - int(0.01 * sr))
            while j > lim and d[j - 1] > 0.1 * fast[i]:
                j -= 1
            out.append(j / sr)
            last = t
    return out

def _k_sos(sr):
    """The BS.1770 K weighting: the high shelf and the high pass, derived for sr from their analog prototypes."""
    f0, G, Q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    K = math.tan(math.pi * f0 / sr)
    Vh = 10.0 ** (G / 20.0)
    Vb = Vh ** 0.4996667741545416
    a0 = 1.0 + K / Q + K * K
    b = [(Vh + Vb * K / Q + K * K) / a0, 2.0 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0]
    a = [1.0, 2.0 * (K * K - 1.0) / a0, (1.0 - K / Q + K * K) / a0]
    f1, Q1 = 38.13547087602444, 0.5003270373238773
    K = math.tan(math.pi * f1 / sr)
    a0 = 1.0 + K / Q1 + K * K
    b2 = [1.0, -2.0, 1.0]
    a2 = [1.0, 2.0 * (K * K - 1.0) / a0, (1.0 - K / Q1 + K * K) / a0]
    return np.array([b + a, b2 + a2])

def lufs(y, sr):
    """Integrated loudness, BS.1770-4 gating (400 ms blocks, 75 % overlap, -70 LUFS and -10 LU gates)."""
    a = as2d(y)
    z = signal.sosfilt(_k_sos(sr), a, axis=0)
    blk, hop = int(0.4 * sr), int(0.1 * sr)
    if a.shape[0] < blk:
        return -70.0
    nb = 1 + (a.shape[0] - blk) // hop
    c = np.concatenate([np.zeros((1, a.shape[1])), np.cumsum(z * z, axis=0)])
    starts = np.arange(nb) * hop
    ms = (c[starts + blk] - c[starts]) / blk
    lk = -0.691 + 10 * np.log10(np.maximum(ms.sum(axis=1), 1e-20))
    g = lk > -70.0
    if not np.any(g):
        return -70.0
    rel = -0.691 + 10 * np.log10(ms[g].sum(axis=1).mean()) - 10.0
    g2 = g & (lk > rel)
    if not np.any(g2):
        return -70.0
    return float(-0.691 + 10 * np.log10(ms[g2].sum(axis=1).mean()))

def match_loudness(y, ref, sr, offset_db=0.0):
    """y scaled to ref's integrated loudness plus offset_db (no change when either is silent)."""
    ly, lr = lufs(y, sr), lufs(ref, sr)
    if ly <= -69.0 or lr <= -69.0:
        return y
    return y * undb(lr - ly + offset_db)

def yin(x1, sr, fmin=40.0, fmax=1000.0, frame=None, hop=None, thresh=0.12):
    """The YIN fundamental estimator (de Cheveigne and Kawahara 2002) on mono x1. Returns times, f0 (0 where
    unvoiced) and the aperiodicity (the dip of the cumulative mean normalised difference, 0 is perfectly periodic)."""
    x1 = np.asarray(x1, dtype=np.float64)
    tmax = int(sr / fmin) + 2
    tmin = max(2, int(sr / fmax))
    W = frame or max(tmax, int(0.025 * sr))
    hop = hop or int(0.005 * sr)
    n = x1.shape[0]
    if n < W + tmax + 1:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    starts = np.arange(0, n - W - tmax, hop)
    L = 1 << int(math.ceil(math.log2(W + tmax)))
    sq = np.concatenate([[0.0], np.cumsum(x1 * x1)])
    f0 = np.zeros(len(starts))
    ap = np.ones(len(starts))
    for i0 in range(0, len(starts), 256):
        st = starts[i0:i0 + 256]
        seg = np.stack([x1[s:s + W + tmax] for s in st])
        a = np.fft.rfft(seg[:, :W], L)
        b = np.fft.rfft(seg, L)
        r = np.fft.irfft(np.conj(a) * b, L)[:, :tmax]
        e0 = (sq[st + W] - sq[st])[:, None]
        tau = np.arange(tmax)
        et = sq[st[:, None] + tau + W] - sq[st[:, None] + tau]
        d = e0 + et - 2.0 * r
        d[:, 0] = 0.0
        cm = np.cumsum(d[:, 1:], axis=1) / np.arange(1, tmax)
        dn = np.ones_like(d)
        dn[:, 1:] = d[:, 1:] / np.maximum(cm, 1e-12)
        for j in range(len(st)):
            row = dn[j]
            cand = np.flatnonzero(row[tmin:tmax - 1] < thresh)
            if cand.size:
                t = tmin + cand[0]
                while t + 1 < tmax - 1 and row[t + 1] < row[t]:
                    t += 1
            else:
                t = tmin + int(np.argmin(row[tmin:tmax - 1]))
            v = row[t]
            if 1 <= t < tmax - 1:
                den = row[t - 1] - 2 * row[t] + row[t + 1]
                off = 0.5 * (row[t - 1] - row[t + 1]) / den if abs(den) > 1e-12 else 0.0
            else:
                off = 0.0
            ap[i0 + j] = v
            f0[i0 + j] = sr / (t + off) if v < 0.35 else 0.0
    times = (starts + W / 2.0) / sr
    return times, f0, ap

def inst_freq(x1, sr, smooth_ms=4.0):
    """Instantaneous frequency of a single tone from its analytic signal, lightly smoothed."""
    z = signal.hilbert(np.asarray(x1, dtype=np.float64))
    ph = np.unwrap(np.angle(z))
    f = np.gradient(ph) * sr / (2 * np.pi)
    L = max(1, int(sr * smooth_ms / 1000.0))
    k = np.ones(L) / L
    return np.convolve(f, k, mode="same")

def stft(x1, n_fft=2048, hop=512):
    """Hann-windowed STFT of mono x1, padded by n_fft on both sides. Returns (frames, bins)."""
    w = np.hanning(n_fft + 1)[:-1]
    p = np.pad(np.asarray(x1, dtype=np.float64), (n_fft, n_fft + hop))
    nf = 1 + (p.shape[0] - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(nf)[:, None]
    return np.fft.rfft(p[idx] * w, axis=1)

def istft(X, n, n_fft=2048, hop=512):
    """Weighted overlap-add inverse of stft(), length n."""
    w = np.hanning(n_fft + 1)[:-1]
    fr = np.fft.irfft(X, n_fft, axis=1) * w
    nf = fr.shape[0]
    L = n_fft + hop * (nf - 1)
    out = np.zeros(L)
    norm = np.zeros(L)
    for i in range(nf):
        out[i * hop:i * hop + n_fft] += fr[i]
        norm[i * hop:i * hop + n_fft] += w * w
    out /= np.maximum(norm, 1e-8)
    return out[n_fft:n_fft + n]

def cepstral_envelope(mag, lifter):
    """Smooth spectral envelope per frame: the real cepstrum kept below lifter quefrency samples."""
    logm = np.log(np.maximum(mag, 1e-9))
    c = np.fft.irfft(logm, axis=1)
    nfft = c.shape[1]
    c[:, lifter:nfft - lifter + 1] = 0.0
    return np.exp(np.fft.rfft(c, axis=1).real)

def true_envelope(mag, lifter, iters=12):
    """The true envelope (Robel and Rodet 2005): the cepstral envelope raised, pass by pass, until it rides on the
    harmonic peaks instead of averaging the gaps between them."""
    A = np.log(np.maximum(mag, 1e-9))
    nfft = 2 * (A.shape[1] - 1)
    V = A
    cur = A.copy()
    for _ in range(iters):
        c = np.fft.irfft(cur, nfft, axis=1)
        c[:, lifter:nfft - lifter + 1] = 0.0
        V = np.fft.rfft(c, axis=1).real
        cur = np.maximum(A, V)
    return np.exp(V)

def pv_stretch(x1, factor, n_fft=2048, hop=256):
    """Phase-vocoder time stretch of mono x1 by factor (2 = twice as long), with identity phase locking around
    spectral peaks (Laroche and Dolson 1999)."""
    x1 = np.asarray(x1, dtype=np.float64)
    if abs(factor - 1.0) < 1e-9:
        return x1.copy()
    ha = hop
    hs = hop * factor
    X = stft(x1, n_fft, ha)
    nf, nb = X.shape
    mag, ph = np.abs(X), np.angle(X)
    omega = 2 * np.pi * np.arange(nb) * ha / n_fft
    out_ph = np.zeros(nb)
    Y = np.zeros_like(X)
    prev = ph[0]
    acc = ph[0].copy()
    for i in range(nf):
        if i > 0:
            dphi = ph[i] - prev - omega
            dphi -= 2 * np.pi * np.round(dphi / (2 * np.pi))
            acc = acc + (omega + dphi) * (hs / ha)
            prev = ph[i]
        m = mag[i]
        pk = np.flatnonzero((m[1:-1] > m[:-2]) & (m[1:-1] >= m[2:])) + 1
        if pk.size:
            mid = (pk[1:] + pk[:-1]) // 2
            owner = pk[np.searchsorted(mid, np.arange(nb), side="right")]
            out_ph = acc[owner] + (ph[i] - ph[i][owner])
        else:
            out_ph = acc
        Y[i] = m * np.exp(1j * out_ph)
    w = np.hanning(n_fft + 1)[:-1]
    fr = np.fft.irfft(Y, n_fft, axis=1) * w
    L = int(math.ceil(n_fft + hs * (nf - 1))) + 2
    out = np.zeros(L)
    norm = np.zeros(L)
    for i in range(nf):
        s = int(round(i * hs))
        out[s:s + n_fft] += fr[i]
        norm[s:s + n_fft] += w * w
    out /= np.maximum(norm, 1e-3 * norm.max())
    start = int(round(n_fft * factor))
    return out[start:start + int(round(x1.shape[0] * factor))]

def pitch_shift(x1, ratio, sr, formants=False, lifter_ms=None, n_fft=2048):
    """Pitch of mono x1 times ratio, same length. formants: hold the spectral envelope of the original so a voice
    keeps its size."""
    x1 = np.asarray(x1, dtype=np.float64)
    n = x1.shape[0]
    if abs(ratio - 1.0) < 1e-9:
        return x1.copy()
    st = pv_stretch(x1, ratio, n_fft=n_fft, hop=n_fft // 8)
    pos = np.arange(n) * ratio
    y = read_at(st, pos, np.full(n, ratio))[:, 0]
    if not formants:
        return y
    hop = n_fft // 4
    X = stft(x1, n_fft, hop)
    Y = stft(y, n_fft, hop)
    if lifter_ms:
        lif = max(4, int(sr * lifter_ms / 1000.0))
    else:
        _, f0, _ = yin(x1[:: 2], sr / 2.0, 60.0, 500.0)
        fm = float(np.median(f0[f0 > 0])) if np.any(f0 > 0) else 150.0
        lif = int(np.clip(0.75 * sr / (fm * max(1.0, ratio)), 40, 400))
    ex = true_envelope(np.abs(X), lif)
    ey = true_envelope(np.abs(Y), lif)
    g = np.clip(ex / np.maximum(ey, 1e-9), 0.05, 20.0)
    return istft(Y * g, n, n_fft, hop)
