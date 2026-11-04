"""Impulse responses synthesised from room acoustics. No recorded IR is read or shipped.

Shoebox rooms (cathedral, cave, small room): early reflections from an image source model of a box with
per wall, per octave absorption, frequency dependent scattering (specular share (1 - s)^order), air
absorption, and jittered image positions (irregular walls break the box's flutter). The late tail is
noise with the image model's own statistics: echo density rising as 4 pi c^3 t^2 / V until it is
Gaussian, energy 4 pi c / V per second relative to the direct sound at 1 m, decaying per octave band at
the Eyring RT60 of the room's materials plus air (Eyring with 4mV). The tail fades in as the scattered
share 1 - (1 - s)^n(t) grows, with n(t) = c t / (4V/S) reflections so far. Two receivers 0.3 m apart:
each band's tails share a common part with the diffuse field coherence sinc(k d), so the lows stay mono
compatible and the highs are decorrelated.

Night forest: single scattering from randomly placed trunks (no parallel surfaces, so no flutter), with
foliage attenuation rising with frequency, then a sparse multiple scattering tail that never turns
Gaussian. Plate: dense from the first sample, bending wave dispersion (high bands arrive first), a long
bright decay. Spring: two to four helical springs in the frequency domain, each a round trip delay with a
spectrally stretched allpass cascade (the chirp, low frequencies first), loss per trip and a 4.5 kHz band
limit.
"""
import numpy as np
from scipy.signal import butter, sosfiltfilt

C = 343.0
BANDS = np.array([63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000], dtype=float)
EDGES = np.sqrt(BANDS[:-1] * BANDS[1:])
AIR_DB_KM = np.array([0.1, 0.4, 1.0, 1.9, 3.7, 9.7, 32.8, 117.0, 380.0])
AIR_M = AIR_DB_KM / 4343.0

def band_split(x, sr):
    """Zero phase complementary Butterworth tree (4th order low and high pass at each edge, run forward and
    backward, so |LP|^2 + |HP|^2 = 1 with zero phase): the bands sum back to x."""
    rest = np.asarray(x, dtype=np.float64)
    out = []
    for fe in EDGES:
        if fe >= 0.45 * sr:
            break
        lo = sosfiltfilt(butter(4, fe, "lowpass", fs=sr, output="sos"), rest, axis=0)
        hi = sosfiltfilt(butter(4, fe, "highpass", fs=sr, output="sos"), rest, axis=0)
        out.append(lo)
        rest = hi
    out.append(rest)
    while len(out) < len(BANDS):
        out.append(np.zeros_like(rest))
    return out

def eyring(V, walls, Sw):
    """Eyring RT60 per band with air absorption. walls: list of absorption arrays, Sw: their areas."""
    S = float(np.sum(Sw))
    a = np.sum([s * np.asarray(w) for s, w in zip(Sw, walls)], axis=0) / S
    return 0.161 * V / (-S * np.log(1 - a) + 4 * AIR_M * V)

def _interp_bands(vals, f):
    lf = np.log(np.maximum(f, 1.0))
    return np.interp(lf, np.log(BANDS), np.asarray(vals, dtype=float))

PRESETS = {
    "cathedral": dict(kind="shoebox", dims=(62.0, 26.0, 30.0), src=(14.0, 13.0, 2.0), rcv=(38.0, 12.4, 1.7),
                      spread=1.6, spacing=0.3,
                      walls=[[0.10, 0.10, 0.11, 0.11, 0.12, 0.13, 0.14, 0.15, 0.15]] * 4 +
                            [[0.12, 0.14, 0.17, 0.18, 0.19, 0.19, 0.19, 0.19, 0.19],
                             [0.08, 0.08, 0.08, 0.09, 0.10, 0.11, 0.12, 0.12, 0.12]],
                      scatter=0.45, jitter=0.35, er_ms=320.0, diffuse=10.0),
    "cave": dict(kind="shoebox", dims=(31.0, 14.0, 9.5), src=(6.0, 6.0, 1.6), rcv=(19.0, 8.5, 1.7),
                 spread=1.0, spacing=0.3,
                 walls=[[0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16]] * 6,
                 scatter=0.7, jitter=0.6, er_ms=200.0, diffuse=6.0),
    "small_room": dict(kind="shoebox", dims=(4.6, 3.8, 2.7), src=(1.2, 1.5, 1.5), rcv=(3.3, 2.4, 1.2),
                       spread=0.6, spacing=0.2,
                       walls=[[0.10, 0.10, 0.09, 0.08, 0.07, 0.07, 0.07, 0.07, 0.07]] * 4 +
                             [[0.04, 0.08, 0.24, 0.57, 0.69, 0.71, 0.73, 0.73, 0.73],
                              [0.15, 0.15, 0.10, 0.06, 0.04, 0.04, 0.05, 0.05, 0.05]],
                       scatter=0.3, jitter=0.06, er_ms=60.0, diffuse=3.0),
    "night_forest": dict(kind="forest", radius=85.0, density=0.035, src_dist=12.0, height=1.6, spacing=0.3,
                         rt=[1.5, 1.4, 1.3, 1.2, 1.0, 0.8, 0.55, 0.38, 0.28],
                         scatter=[0.06, 0.09, 0.13, 0.18, 0.22, 0.25, 0.26, 0.26, 0.26],
                         foliage_db_m=[0.002, 0.004, 0.008, 0.015, 0.03, 0.05, 0.08, 0.12, 0.18],
                         tail_rate=(250.0, 1200.0, 1800.0)),
    "plate": dict(kind="plate", rt=[1.4, 1.8, 2.3, 2.6, 2.8, 2.7, 2.4, 2.0, 1.4], disp_ms_1k=3.0),
    "spring": dict(kind="spring", trips=[0.0405, 0.0466, 0.0433, 0.0497], stages=60, coef=0.6, stretch=4,
                   rt_low=2.6, rt_high=1.4, band=(90.0, 4500.0)),
}

def targets(preset, decay=1.0):
    """The RT60 per band (BANDS) the preset is built to, scaled by decay."""
    p = PRESETS[preset]
    if p["kind"] == "shoebox":
        return targets_from(p, decay)
    if p["kind"] in ("forest", "plate"):
        return np.array(p["rt"], dtype=float) * decay
    f = BANDS
    t = p["rt_low"] + (p["rt_high"] - p["rt_low"]) * np.clip(np.log(f / 200.0) / np.log(4000 / 200.0), 0, 1)
    return t * decay

def _receivers(rcv, spacing):
    r = np.array(rcv, dtype=float)
    return [r + np.array([0.0, -spacing / 2, 0.0]), r + np.array([0.0, spacing / 2, 0.0])]

def _sources(src, spread, n_in):
    s = np.array(src, dtype=float)
    if n_in == 1:
        return [s]
    return [s + np.array([0.0, -spread / 2, 0.0]), s + np.array([0.0, spread / 2, 0.0])]

def _image_er(p, src, rcv, sr, n_fft, t_end, img_seed, d_ref):
    """Early reflections by the image source model, built in the frequency domain (exact fractional
    delays). Returns the time signal (n_fft) with time 0 at the direct sound."""
    Lx, Ly, Lz = p["dims"]
    walls = np.asarray(p["walls"], dtype=float)
    R = np.sqrt(1.0 - walls)
    sc = p["scatter"] * np.array([0.25, 0.35, 0.5, 0.7, 0.85, 1.0, 1.0, 1.0, 1.0])
    spec = np.sqrt(1.0 - sc)
    dmax = d_ref + C * t_end
    rng = np.random.default_rng(img_seed)
    f = np.fft.rfftfreq(n_fft, 1 / sr)
    H = np.zeros(f.size, dtype=np.complex128)
    nx = int(dmax / (2 * Lx)) + 2
    ny = int(dmax / (2 * Ly)) + 2
    nz = int(dmax / (2 * Lz)) + 2
    amps, taus = [], []
    for ix in range(-nx, nx + 1):
        for px in (0, 1):
            X = 2 * ix * Lx + (1 - 2 * px) * src[0]
            cx0, cx1 = abs(ix - px), abs(ix)
            for iy in range(-ny, ny + 1):
                for py in (0, 1):
                    Y = 2 * iy * Ly + (1 - 2 * py) * src[1]
                    cy0, cy1 = abs(iy - py), abs(iy)
                    for iz in range(-nz, nz + 1):
                        for pz in (0, 1):
                            Z = 2 * iz * Lz + (1 - 2 * pz) * src[2]
                            cz0, cz1 = abs(iz - pz), abs(iz)
                            order = cx0 + cx1 + cy0 + cy1 + cz0 + cz1
                            if order == 0:
                                continue
                            pos = np.array([X, Y, Z])
                            pos = pos + rng.normal(0.0, p["jitter"] * order, 3) if p["jitter"] > 0 else pos
                            d = float(np.linalg.norm(pos - rcv))
                            if d > dmax:
                                continue
                            a = (R[0] ** cx0) * (R[1] ** cx1) * (R[2] ** cy0) * (R[3] ** cy1) * \
                                (R[4] ** cz0) * (R[5] ** cz1) * spec ** order
                            a = a * np.exp(-0.5 * AIR_M * d) / d
                            amps.append(a)
                            taus.append((d - d_ref) / C)
    amps = np.array(amps)
    taus = np.array(taus)
    keep = taus > 0
    amps, taus = amps[keep], taus[keep]
    lf = np.log(np.maximum(f, 1.0))
    lb = np.log(BANDS)
    for s in range(0, taus.size, 128):
        a = amps[s:s + 128]
        t = taus[s:s + 128]
        A = np.stack([np.interp(lf, lb, row) for row in a])
        H += np.sum(A * np.exp(-2j * np.pi * f[None, :] * t[:, None]), axis=0)
    return np.fft.irfft(H, n_fft), (taus.min() if taus.size else 0.0)

def _excitation(n, sr, t0, V, rng, lam_max=12000.0, rate=None, diffuse=1.0):
    """Unit variance noise whose echo density follows the room: Poisson arrivals at rate
    diffuse x 4 pi c^3 t^2 / V (t from emission, t0 is the direct sound time; diffuse counts the extra
    arrivals scattering surfaces make out of each specular one) until lam_max, then Gaussian. rate=(r0, slope, cap) gives
    a linear rate that never turns Gaussian (forest)."""
    t = t0 + np.arange(n) / sr
    e = np.zeros(n)
    if rate is not None:
        r0, k, cap = rate
        lam = np.minimum(r0 + k * (t - t0), cap)
        u = rng.random(n)
        hit = u < lam / sr
        e[hit] = rng.choice([-1.0, 1.0], int(hit.sum())) * np.sqrt(sr / lam[hit])
        return e
    lam = diffuse * 4 * np.pi * C ** 3 * t ** 2 / V
    sparse = lam < lam_max
    u = rng.random(n)
    hit = sparse & (u < lam / sr)
    e[hit] = rng.choice([-1.0, 1.0], int(hit.sum())) * np.sqrt(sr / np.maximum(lam[hit], 1e-9))
    g = rng.standard_normal(n)
    w = np.clip((lam - lam_max / 3) / (lam_max * 2 / 3), 0, 1)
    return np.sqrt(1 - w) * e + np.sqrt(w) * g

def _octave(x, sr, fc, order=6):
    lo = fc / np.sqrt(2)
    hi = min(fc * np.sqrt(2), 0.45 * sr)
    return sosfiltfilt(butter(order, [lo, hi], "bandpass", fs=sr, output="sos"), x, axis=0)

def _per_f(vals, f, log_values=True):
    """A band table (BANDS) as a smooth function of frequency: interpolated in log frequency (and in log
    value for RT60s), held flat past the end bands."""
    lf = np.log(np.maximum(f, 1.0))
    v = np.asarray(vals, dtype=float)
    if log_values:
        return np.exp(np.interp(lf, np.log(BANDS), np.log(v)))
    return np.interp(lf, np.log(BANDS), v)

def _stft(x, W):
    H = W // 4
    n = x.size
    xp = np.zeros(n + 2 * W + H)
    xp[W:W + n] = x
    K = (n + W) // H + 1
    win = np.hanning(W + 1)[:W]
    idx = np.arange(K)[:, None] * H + np.arange(W)[None, :]
    return np.fft.rfft(xp[idx] * win, axis=1), (np.arange(K) * H - W / 2) / 1.0

def _istft(X, n, W):
    H = W // 4
    K = X.shape[0]
    win = np.hanning(W + 1)[:W]
    fr = np.fft.irfft(X, n=W, axis=1) * win
    out = np.zeros(K * H + W)
    for k in range(K):
        out[k * H:k * H + W] += fr[k]
    return out[W:W + n] / 1.5

def _tv_tail(excs, sr, gain, rho, W=1024):
    """Shape noise with a time varying spectral gain (an STFT filter: periodic Hann in and out at 75
    percent overlap, which sums to 1.5). excs = (shared, private for receiver 0, private for receiver 1);
    gain(t_seconds (K,), f (F,)) gives the amplitude gain (K, F); rho (F,) is the inter receiver
    coherence. Returns the two receivers' tails."""
    n = excs[0].size
    S = [_stft(e, W) for e in excs]
    tk = S[0][1] / sr
    f = np.fft.rfftfreq(W, 1 / sr)
    G = gain(tk, f)
    r = np.sqrt(np.clip(rho, 0, 1))[None, :]
    q = np.sqrt(1 - np.clip(rho, 0, 1))[None, :]
    return [_istft(G * (q * S[1 + o][0] + r * S[0][0]), n, W) for o in range(2)]

def _shoebox(p, sr, n_in, decay, rng):
    Lx, Ly, Lz = p["dims"]
    V = Lx * Ly * Lz
    S = 2 * (Lx * Ly + Lx * Lz + Ly * Lz)
    T = targets_from(p, decay)
    t_len = 1.15 * T.max() + 0.05
    n = int(t_len * sr)
    srcs = _sources(p["src"], p["spread"], n_in)
    rcvs = _receivers(p["rcv"], p["spacing"])
    t_er = p["er_ms"] * 1e-3
    n_fft = 1 << int(np.ceil(np.log2((t_er + 0.08) * sr)))
    mfp = 4 * V / S
    sc = p["scatter"] * np.array([0.25, 0.35, 0.5, 0.7, 0.85, 1.0, 1.0, 1.0, 1.0])
    h = np.zeros((n, n_in, 2))
    fade_n = int(0.012 * sr)
    i_er = int(t_er * sr)
    lvl = np.sqrt(4 * np.pi * C / (V * sr))
    rho = _coherence_f(p["spacing"], np.fft.rfftfreq(1024, 1 / sr))
    for i, s in enumerate(srcs):
        d_ref = float(np.linalg.norm(s - np.array(p["rcv"])))
        t0 = d_ref / C
        ex = [_excitation(n, sr, t0, V, rng, diffuse=p["diffuse"]) for _ in range(3)]
        img_seed = int(rng.integers(1 << 31))
        ers = []
        t_first = 1.0
        for o, r in enumerate(rcvs):
            er, tf = _image_er(p, s, r, sr, n_fft, t_er + 0.015, img_seed, d_ref)
            t_first = min(t_first, tf)
            er_t = np.zeros(n)
            m = min(n, n_fft)
            er_t[:m] = er[:m]
            ramp = 0.5 + 0.5 * np.cos(np.pi * np.clip((np.arange(n) - i_er) / fade_n, 0, 1))
            ers.append(er_t * ramp)

        def gain(tk, f, t0=t0, t_first=t_first):
            Tf = _per_f(T, f)[None, :]
            sf = _per_f(sc, f, log_values=False)[None, :]
            t = np.maximum(tk, 0.0)[:, None]
            share = 1.0 - (1.0 - sf) ** (C * (t0 + t) / mfp)
            share = np.where(t < t_first, 0.0, share)
            ramp = 0.5 + 0.5 * np.cos(np.pi * np.clip((t - t_er) / (fade_n / sr), 0, 1))
            share = share + (1.0 - share) * (1.0 - ramp)
            return lvl * np.exp(-6.9078 * (t0 + t) / Tf) * np.sqrt(share)

        tails = _tv_tail(ex, sr, gain, rho)
        for o in range(2):
            h[:, i, o] = ers[o] + tails[o]
    return h

def targets_from(p, decay):
    Lx, Ly, Lz = p["dims"]
    V = Lx * Ly * Lz
    Sw = [Ly * Lz, Ly * Lz, Lx * Lz, Lx * Lz, Lx * Ly, Lx * Ly]
    return eyring(V, p["walls"], Sw) * decay

def _coherence_f(d, f):
    """Diffuse field coherence of two omni receivers d metres apart, sinc(k d), floored at 0."""
    k = 2 * np.pi * np.asarray(f, dtype=float) / C
    return np.clip(np.sinc(k * d / np.pi), 0.0, 1.0)

def _forest(p, sr, n_in, decay, rng):
    T = np.array(p["rt"], dtype=float) * decay
    R = p["radius"]
    t_len = 1.15 * T.max() + 0.6
    n = int(t_len * sr)
    h = np.zeros((n, n_in, 2))
    area = np.pi * R * R
    ntree = int(p["density"] * area)
    trees = rng.uniform(-R, R, (ntree * 2, 2))
    trees = trees[np.hypot(trees[:, 0], trees[:, 1]) < R][:ntree]
    trees = trees[np.hypot(trees[:, 0], trees[:, 1]) > 1.0]
    scat = np.asarray(p["scatter"], dtype=float)
    fol = np.asarray(p["foliage_db_m"], dtype=float)
    rc = np.array([0.0, 0.0])
    t_er = 2 * R / C + 0.1
    n_fft = 1 << int(np.ceil(np.log2((t_er + 0.05) * sr)))
    f = np.fft.rfftfreq(n_fft, 1 / sr)
    lf = np.log(np.maximum(f, 1.0))
    lb = np.log(BANDS)
    rho = _coherence_f(p["spacing"], np.fft.rfftfreq(1024, 1 / sr))
    i0, i1 = int(0.08 * sr), int(0.2 * sr)
    for i in range(n_in):
        side = 0.0 if n_in == 1 else (-1.0 if i == 0 else 1.0)
        src = np.array([p["src_dist"], 1.2 * side])
        d_ref = float(np.hypot(*(src - rc)))
        ex = [_excitation(n, sr, d_ref / C, 1.0, rng, rate=p["tail_rate"]) for _ in range(3)]
        ers = []
        for o in range(2):
            r = rc + np.array([0.0, (o - 0.5) * p["spacing"]])
            d1 = np.hypot(trees[:, 0] - src[0], trees[:, 1] - src[1])
            d2 = np.hypot(trees[:, 0] - r[0], trees[:, 1] - r[1])
            path = d1 + d2
            tau = (path - d_ref) / C
            ok = tau > 0.002
            a = scat[None, :] / (d1[ok, None] * d2[ok, None]) * 10 ** (-fol[None, :] * path[ok, None] / 20)
            a = a * np.exp(-0.5 * AIR_M[None, :] * path[ok, None])
            H = np.zeros(f.size, dtype=np.complex128)
            tk = tau[ok]
            for s in range(0, tk.size, 128):
                A = np.stack([np.interp(lf, lb, row) for row in a[s:s + 128]])
                H += np.sum(A * np.exp(-2j * np.pi * f[None, :] * tk[s:s + 128, None]), axis=0)
            er = np.fft.irfft(H, n_fft)[: min(n, n_fft)]
            i_end = min(er.size, int(t_er * sr))
            k = int(0.05 * sr)
            er[i_end - k:i_end] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(k) / k)
            er[i_end:] = 0.0
            er_t = np.zeros(n)
            er_t[: er.size] = er
            ers.append(er_t)

        def g0(tk, ff):
            t = np.maximum(tk, 0.0)[:, None]
            return np.exp(-6.9078 * t / _per_f(T, ff)[None, :]) * np.clip(t / 0.06, 0, 1)

        raw = _tv_tail(ex, sr, g0, rho)
        scale = np.ones(len(BANDS))
        for b in range(len(BANDS)):
            if BANDS[b] / np.sqrt(2) >= 0.45 * sr:
                continue
            e_er = np.mean([np.mean(_octave(ers[o], sr, BANDS[b])[i0:i1] ** 2) for o in range(2)])
            e_t = np.mean([np.mean(_octave(raw[o], sr, BANDS[b])[i0:i1] ** 2) for o in range(2)]) + 1e-30
            scale[b] = np.sqrt(0.6 * e_er / e_t)

        def g1(tk, ff):
            return g0(tk, ff) * _per_f(scale, ff)[None, :]

        tails = _tv_tail(ex, sr, g1, rho)
        for o in range(2):
            h[:, i, o] = ers[o] + tails[o]
    return h

def _plate(p, sr, n_in, decay, rng):
    T = np.array(p["rt"], dtype=float) * decay
    n = int((1.15 * T.max() + 0.05) * sr)
    h = np.zeros((n, n_in, 2))

    def gain(tk, f):
        Tf = _per_f(T, f)[None, :]
        t0 = p["disp_ms_1k"] * 1e-3 * np.sqrt(1000.0 / np.maximum(f, 60.0))[None, :]
        t = tk[:, None] - t0
        return np.exp(-6.9078 * np.maximum(t, 0) / Tf) * np.clip(t / 0.002, 0, 1)

    for i in range(n_in):
        ex = [rng.standard_normal(n) for _ in range(3)]
        tails = _tv_tail(ex, sr, gain, np.zeros(129), W=256)
        for o in range(2):
            h[:, i, o] = tails[o]
    return h

def T_of_f(preset, f, decay=1.0):
    """The RT60 the preset is built to at frequency f (continuous)."""
    p = PRESETS[preset]
    if p["kind"] == "spring":
        return np.interp(np.log(np.maximum(f, 1.0)), np.log([200.0, 4000.0]),
                         [p["rt_low"], p["rt_high"]]) * decay
    return _per_f(targets(preset, decay), f)

def predicted_octave_rt(preset, fc, sr=48000, decay=1.0, order=6):
    """The T30 an octave band measurement (measure.octave, zero phase order 6) should read on the model's
    late decay: white noise decaying at T(f), weighted by the filter's |H|^4, Schroeder integrated."""
    from scipy.signal import sosfreqz
    f = np.linspace(fc / 4, min(fc * 4, 0.49 * sr), 4000)
    lo = fc / np.sqrt(2)
    hi = min(fc * np.sqrt(2), 0.45 * sr)
    sos = butter(order, [lo, hi], "bandpass", fs=sr, output="sos")
    _, Hf = sosfreqz(sos, worN=f, fs=sr)
    wgt = np.abs(Hf) ** 4
    Tf = T_of_f(preset, f, decay)
    a = 13.8155 / Tf
    t = np.linspace(0, 2 * float(np.max(Tf)), 4000)
    Sch = (wgt[None, :] * np.exp(-a[None, :] * t[:, None]) / a[None, :]).sum(axis=1)
    db = 10 * np.log10(Sch / Sch[0])
    i0 = int(np.argmax(db <= -5))
    i1 = int(np.argmax(db <= -35))
    k, _ = np.polyfit(t[i0:i1], db[i0:i1], 1)
    return float(-60 / k)

def _spring(p, sr, n_in, decay, rng):
    n = int((1.15 * p["rt_low"] * decay + 0.1) * sr)
    n_fft = 1 << int(np.ceil(np.log2(2 * n)))
    f = np.fft.rfftfreq(n_fft, 1 / sr)
    w = 2 * np.pi * f / sr
    a = p["coef"]
    K = p["stretch"]
    zK = np.exp(-1j * K * w)
    A = (a + zK) / (1 + a * zK)
    lo, hi = p["band"]
    bp = 1.0 / np.sqrt(1 + (lo / np.maximum(f, 1e-6)) ** 4) / np.sqrt(1 + (f / hi) ** 8)
    t60 = T_of_f("spring", f, decay)
    h = np.zeros((n, n_in, 2))
    k = 0
    for i in range(n_in):
        for o in range(2):
            T = p["trips"][k % len(p["trips"])]
            k += 1
            G = 10 ** (-3 * T / t60)
            Pr = np.exp(-1j * w * T * sr) * A ** p["stages"] * G
            Ph = np.exp(-1j * w * T * sr / 2) * A ** (p["stages"] // 2) * np.sqrt(G)
            H = bp * Ph / (1 - Pr)
            h[:, i, o] = np.fft.irfft(H, n_fft)[:n]
    return h

def synth(preset, sr=48000, n_in=1, decay=1.0, seed=1):
    """Return the IR as float64 (samples, n_in, 2), normalised so each input's total energy is 1."""
    p = PRESETS[preset]
    rng = np.random.default_rng(seed)
    kind = p["kind"]
    if kind == "shoebox":
        h = _shoebox(p, sr, n_in, decay, rng)
    elif kind == "forest":
        h = _forest(p, sr, n_in, decay, rng)
    elif kind == "plate":
        h = _plate(p, sr, n_in, decay, rng)
    else:
        h = _spring(p, sr, n_in, decay, rng)
    m = h.shape[0]
    k = int(0.03 * m)
    h[m - k:] *= (0.5 + 0.5 * np.cos(np.pi * np.arange(k) / k))[:, None, None]
    for i in range(n_in):
        e = np.sum(h[:, i, :] ** 2)
        h[:, i, :] /= np.sqrt(e / 2.0 + 1e-30)
    return h
