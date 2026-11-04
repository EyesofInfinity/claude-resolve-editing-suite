"""Measurements for judging spaces without ears: RT60, echo density, periodicity, comb peaks,
stereo correlation, clicks, aliasing, loudness and true peak."""
import numpy as np
from scipy.signal import butter, sosfiltfilt, sosfilt
from scipy.special import erfc

from common import true_peak_db, lufs

OCT = [125, 250, 500, 1000, 2000, 4000, 8000]

def octave(x, sr, fc, order=6):
    """Octave band around fc, zero phase. Order 6 Butterworth (steeper than an IEC class 1 filter) so a
    slower neighbour band does not set the late slope of a fast one."""
    lo = fc / np.sqrt(2)
    hi = min(fc * np.sqrt(2), 0.45 * sr)
    sos = butter(order, [lo, hi], "bandpass", fs=sr, output="sos")
    return sosfiltfilt(sos, x, axis=0)

def schroeder_db(h):
    e = np.asarray(h, dtype=np.float64) ** 2
    if e.ndim > 1:
        e = e.sum(axis=1)
    c = np.cumsum(e[::-1])[::-1]
    c = c / (c[0] + 1e-300)
    return 10 * np.log10(c + 1e-300)

def rt60(h, sr, lo_db=-5.0, hi_db=-35.0):
    """RT60 from the Schroeder backward integral, a least squares line from lo_db to hi_db (T30 by default)."""
    s = schroeder_db(h)
    i0 = np.argmax(s <= lo_db)
    i1 = np.argmax(s <= hi_db)
    if i1 <= i0 + 4:
        return float("nan")
    t = np.arange(i0, i1) / sr
    k, _ = np.polyfit(t, s[i0:i1], 1)
    return float(-60.0 / k) if k < 0 else float("nan")

def rt60_bands(h, sr, bands=OCT, hi_db=-35.0):
    return {fc: rt60(octave(h, sr, fc), sr, hi_db=hi_db) for fc in bands if fc < 0.4 * sr}

def echo_density(h, sr, win_ms=20.0, hop_ms=5.0):
    """Abel and Huang normalised echo density profile: 1 means Gaussian (fully diffuse), small means sparse."""
    a = np.asarray(h, dtype=np.float64)
    if a.ndim > 1:
        a = a[:, 0]
    W = int(win_ms * 1e-3 * sr)
    H = int(hop_ms * 1e-3 * sr)
    w = np.hanning(W)
    w /= w.sum()
    ts, ed = [], []
    ref = erfc(1 / np.sqrt(2))
    for s in range(0, a.shape[0] - W, H):
        seg = a[s:s + W]
        sd = np.sqrt(np.sum(w * seg * seg))
        if sd <= 0:
            ts.append((s + W / 2) / sr)
            ed.append(0.0)
            continue
        ed.append(float(np.sum(w * (np.abs(seg) > sd)) / ref))
        ts.append((s + W / 2) / sr)
    return np.array(ts), np.array(ed)

def flatten_decay(seg, sr, env_ms=30.0):
    """Divide a decaying segment by its smoothed RMS envelope so it is stationary."""
    from scipy.ndimage import uniform_filter1d
    e = np.sqrt(uniform_filter1d(seg ** 2, int(env_ms * 1e-3 * sr), mode="nearest")) + 1e-20
    return seg / e

def periodicity(seg, sr, lo_ms=1.0, hi_ms=200.0):
    """Largest autocorrelation of a decay-flattened, spectrally whitened tail at lags lo to hi ms, and of
    its energy envelope (1 ms frames). Whitening (the power spectrum divided by its 1/6 octave smooth)
    keeps a coloured but diffuse tail from reading as periodic. Flutter echo and metallic ringing show as
    a large value; a diffuse tail of one second sits near 0.05."""
    a = np.asarray(seg, dtype=np.float64)
    if a.ndim > 1:
        a = a[:, 0]
    f = flatten_decay(a, sr)
    f = f - f.mean()
    n = 1 << int(np.ceil(np.log2(2 * f.size)))
    F = np.fft.rfft(f, n)
    P = np.abs(F) ** 2
    fr = np.fft.rfftfreq(n, 1 / sr)
    lg = np.log2(np.maximum(fr, 1.0))
    edges = np.arange(lg[1], lg[-1] + 1 / 6, 1 / 6)
    idx = np.clip(np.searchsorted(edges, lg), 0, edges.size)
    sums = np.bincount(idx, weights=P, minlength=edges.size + 1)
    cnt = np.bincount(idx, minlength=edges.size + 1)
    sm = (sums / np.maximum(cnt, 1))[idx]
    Pw = P / (sm + 1e-30)
    Pw[fr < 40.0] = 0.0
    r = np.fft.irfft(Pw, n)[: f.size]
    r /= r[0]
    l0, l1 = int(lo_ms * 1e-3 * sr), int(hi_ms * 1e-3 * sr)
    k = l0 + int(np.argmax(np.abs(r[l0:l1])))
    sig = float(abs(r[k]))
    fr1 = int(1e-3 * sr)
    m = (f.size // fr1) * fr1
    en = (f[:m] ** 2).reshape(-1, fr1).mean(axis=1)
    en = en - en.mean()
    n2 = 1 << int(np.ceil(np.log2(2 * en.size)))
    E = np.fft.rfft(en, n2)
    re = np.fft.irfft(np.abs(E) ** 2, n2)[: en.size]
    re /= re[0] + 1e-30
    j0, j1 = max(2, int(lo_ms)), min(int(hi_ms), en.size - 1)
    kj = j0 + int(np.argmax(re[j0:j1]))
    return dict(sig=sig, sig_lag_ms=1e3 * k / sr, env=float(re[kj]), env_lag_ms=float(kj))

def comb_peaks(seg, sr, f_lo=200.0, f_hi=8000.0):
    """Tail spectrum check: the share of fine spectrum peaks more than 12 dB over the 1/3 octave smoothed
    spectrum. A Gaussian diffuse tail (exponential periodogram) puts about 1.1e-7 of bins there for a
    single periodogram; we average 8 sub segments so the ideal is near zero. Returns the share and the
    largest excess in dB."""
    a = np.asarray(seg, dtype=np.float64)
    if a.ndim > 1:
        a = a[:, 0]
    f = flatten_decay(a, sr)
    M = 8
    L = f.size // M
    P = 0
    for i in range(M):
        s = f[i * L:(i + 1) * L] * np.hanning(L)
        P = P + np.abs(np.fft.rfft(s)) ** 2
    P /= M
    fr = np.fft.rfftfreq(L, 1 / sr)
    sel = (fr >= f_lo) & (fr <= f_hi)
    lp = np.log(P + 1e-30)
    sm = np.empty_like(P)
    for i, fc in enumerate(fr):
        if not sel[i]:
            sm[i] = P[i]
            continue
        b = (fr >= fc / 2 ** (1 / 6)) & (fr <= fc * 2 ** (1 / 6))
        sm[i] = np.mean(P[b])
    ex = 10 * np.log10(P[sel] / sm[sel])
    return dict(share12=float(np.mean(ex > 12.0)), max_db=float(ex.max()), p99_db=float(np.percentile(ex, 99)))

def stereo(seg):
    """Pearson correlation of L and R, and the mono sum level against the mean side energy in dB
    (0 dB fully correlated, -3 dB uncorrelated, very negative means it cancels in mono)."""
    a = np.asarray(seg, dtype=np.float64)
    l, r = a[:, 0], a[:, 1]
    c = float(np.corrcoef(l, r)[0, 1])
    mono = np.mean(((l + r) / 2) ** 2)
    side = np.mean((l * l + r * r) / 2) + 1e-30
    return dict(corr=c, mono_db=float(10 * np.log10(mono / side + 1e-30)))

def stereo_bands(y, sr, t0, t1, bands=OCT):
    """stereo() per octave band of y between t0 and t1 seconds (filtered whole, then cut)."""
    out = {}
    i0, i1 = int(t0 * sr), int(t1 * sr)
    for fc in bands:
        if fc >= 0.4 * sr:
            continue
        out[fc] = stereo(octave(y, sr, fc)[i0:i1])
    return out

def clicks(y, sr, z=40.0):
    """Count of samples whose second difference stands z times over its local median (5 ms), above -60 dBFS."""
    a = np.asarray(y, dtype=np.float64)
    if a.ndim == 1:
        a = a[:, None]
    from scipy.ndimage import median_filter
    tot = 0
    for c in range(a.shape[1]):
        d2 = np.abs(np.diff(a[:, c], 2))
        if d2.size < 10:
            continue
        step = 8
        dec = d2[: (d2.size // step) * step].reshape(-1, step).max(axis=1)
        med = median_filter(dec, size=max(3, int(5e-3 * sr / step)), mode="nearest")
        med = np.repeat(med, step)
        med = np.pad(med, (0, d2.size - med.size), mode="edge")
        hit = (d2 > z * (med + 1e-9)) & (d2 > 1e-3)
        tot += int(np.sum(hit))
    return tot

def tone_level_db(y, sr, f, bw=30.0):
    """Level in dB of the energy within f +/- bw Hz (Hann windowed spectrum, summed power)."""
    a = np.asarray(y, dtype=np.float64)
    if a.ndim > 1:
        a = a.mean(axis=1)
    X = np.abs(np.fft.rfft(a * np.hanning(a.size))) ** 2
    fr = np.fft.rfftfreq(a.size, 1 / sr)
    s = (fr > f - bw) & (fr < f + bw)
    return float(10 * np.log10(X[s].sum() + 1e-30))

def centroid(y, sr):
    a = np.asarray(y, dtype=np.float64)
    if a.ndim > 1:
        a = a.mean(axis=1)
    X = np.abs(np.fft.rfft(a)) ** 2
    fr = np.fft.rfftfreq(a.size, 1 / sr)
    return float(np.sum(fr * X) / (np.sum(X) + 1e-30))

__all__ = ["rt60", "rt60_bands", "echo_density", "periodicity", "comb_peaks", "stereo", "stereo_bands",
           "clicks", "tone_level_db", "centroid", "true_peak_db", "lufs", "octave", "schroeder_db"]
