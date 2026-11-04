"""The Develop Spaces reverb tank: input diffusion, a 16 line feedback delay network, modulated reads,
per line frequency dependent absorption, an optional pitch shifter in the feedback of four lines (shimmer),
and a freeze that makes the tank lossless and closes its input.

Built from published DSP ideas: the feedback delay network with an orthogonal (Hadamard) matrix and
per line absorption filters matched to a target RT60 (Jot), a diffuser of delays, Hadamard mixes and
polarity flips ahead of the tank, and the two head crossfaded delay line pitch shifter.
"""
import numpy as np
from numba import njit

N = 16

@njit(cache=True, inline="always")
def _hermite(buf, mask, pos):
    ip = int(np.floor(pos))
    f = pos - ip
    xm1 = buf[(ip - 1) & mask]
    x0 = buf[ip & mask]
    x1 = buf[(ip + 1) & mask]
    x2 = buf[(ip + 2) & mask]
    c1 = 0.5 * (x1 - xm1)
    c2 = xm1 - 2.5 * x0 + 2.0 * x1 - 0.5 * x2
    c3 = 0.5 * (x2 - xm1) + 1.5 * (x0 - x1)
    return ((c3 * f + c2) * f + c1) * f + x0

@njit(cache=True, inline="always")
def _lagrange6(buf, mask, pos):
    ip = int(np.floor(pos))
    f = pos - ip
    acc = 0.0
    for k in range(-2, 4):
        c = 1.0
        for j in range(-2, 4):
            if j != k:
                c *= (f - j) / (k - j)
        acc += c * buf[(ip + k) & mask]
    return acc

@njit(cache=True, inline="always")
def _wht16(v):
    h = 1
    while h < 16:
        for i in range(0, 16, 2 * h):
            for j in range(i, i + h):
                a = v[j]
                b = v[j + h]
                v[j] = a + b
                v[j + h] = a - b
        h *= 2
    for i in range(16):
        v[i] *= 0.25

@njit(cache=True)
def _run(inp, n_out, in_l, in_r, dif_del, dif_sign, line_len, mod_depth, mod_inc, mod_ph,
         fb_b, fb_a, out_l, out_r, K, s_amt, fifth, w_oct, w_fifth, aa, frz0, frz1, ramp, sgain):
    n_in = inp.shape[0]
    S = dif_del.shape[0]
    dmax = 1
    for s in range(S):
        for i in range(16):
            if dif_del[s, i] + 2 > dmax:
                dmax = dif_del[s, i] + 2
    dl = 1
    while dl < dmax:
        dl *= 2
    dmask = dl - 1
    dbuf = np.zeros((S, 16, dl))
    lmax = 1.0
    for i in range(16):
        v = line_len[i] + mod_depth[i] + 8.0
        if v > lmax:
            lmax = v
    bl = 1
    while bl < lmax:
        bl *= 2
    bmask = bl - 1
    buf = np.zeros((16, bl))
    wmax = w_oct
    if w_fifth > wmax:
        wmax = w_fifth
    pl = 1
    while pl < wmax + 16:
        pl *= 2
    pmask = pl - 1
    pbuf = np.zeros((4, pl))
    nq = aa.shape[0]
    aas = np.zeros((4, nq, 2))
    ph_o = np.zeros(4)
    ph_f = np.zeros(4)
    for k in range(4):
        ph_o[k] = (0.25 * k) % 1.0
        ph_f[k] = (0.25 * k + 0.125) % 1.0
    r_oct = 2.0
    r_fifth = 1.5
    inc_o = (r_oct - 1.0) / w_oct
    inc_f = (r_fifth - 1.0) / w_fifth

    z = np.zeros(16)
    st = np.zeros(16)
    v = np.zeros(16)
    d = np.zeros(16)
    ph = mod_ph.copy()
    out = np.zeros((n_out, 2))
    w = 0
    dw = 0
    pw = 0
    frz = 0.0
    dfrz = 1.0 / ramp if ramp > 0 else 1.0
    for n in range(n_out):
        if frz0 >= 0 and n >= frz0 and n < frz1:
            frz = min(1.0, frz + dfrz)
        else:
            frz = max(0.0, frz - dfrz)
        gate = 1.0 - frz
        if n < n_in:
            xl = inp[n, 0] * gate
            xr = inp[n, 1] * gate
        else:
            xl = 0.0
            xr = 0.0
        for i in range(16):
            d[i] = in_l[i] * xl + in_r[i] * xr
        for s in range(S):
            for i in range(16):
                dbuf[s, i, dw] = d[i]
                d[i] = dbuf[s, i, (dw - dif_del[s, i]) & dmask]
            _wht16(d)
            for i in range(16):
                d[i] *= dif_sign[s, i]
        dw = (dw + 1) & dmask
        yl = 0.0
        yr = 0.0
        for i in range(16):
            dd = line_len[i] + mod_depth[i] * np.sin(ph[i])
            ph[i] += mod_inc[i]
            if ph[i] > 6.283185307179586:
                ph[i] -= 6.283185307179586
            o = _hermite(buf[i], bmask, w - dd)
            b = fb_b[i] + (1.0 - fb_b[i]) * frz
            a = fb_a[i] * (1.0 - frz)
            st[i] = b * o + a * st[i]
            z[i] = st[i]
            yl += out_l[i] * z[i]
            yr += out_r[i] * z[i]
        out[n, 0] = yl
        out[n, 1] = yr
        if K > 0 and s_amt > 0.0:
            for k in range(K):
                xin = z[k]
                for q in range(nq):
                    b0 = aa[q, 0]
                    b1 = aa[q, 1]
                    b2 = aa[q, 2]
                    a1 = aa[q, 4]
                    a2 = aa[q, 5]
                    yq = b0 * xin + aas[k, q, 0]
                    aas[k, q, 0] = b1 * xin - a1 * yq + aas[k, q, 1]
                    aas[k, q, 1] = b2 * xin - a2 * yq
                    xin = yq
                pbuf[k, pw] = xin
                so = 0.0
                sf = 0.0
                for hd in range(2):
                    p = ph_o[k] + 0.5 * hd
                    if p >= 1.0:
                        p -= 1.0
                    g = np.sin(3.141592653589793 * p)
                    so += g * g * _lagrange6(pbuf[k], pmask, pw - 3.0 - w_oct * (1.0 - p))
                    if fifth > 0.0:
                        p2 = ph_f[k] + 0.5 * hd
                        if p2 >= 1.0:
                            p2 -= 1.0
                        g2 = np.sin(3.141592653589793 * p2)
                        sf += g2 * g2 * _lagrange6(pbuf[k], pmask, pw - 3.0 - w_fifth * (1.0 - p2))
                ph_o[k] += inc_o
                if ph_o[k] >= 1.0:
                    ph_o[k] -= 1.0
                ph_f[k] += inc_f
                if ph_f[k] >= 1.0:
                    ph_f[k] -= 1.0
                sa = s_amt * gate
                z[k] = np.sqrt(1.0 - sa) * z[k] + np.sqrt(sa) * sgain * ((1.0 - fifth) * so + fifth * sf)
            pw = (pw + 1) & pmask
        for i in range(16):
            v[i] = z[i]
        _wht16(v)
        for i in range(16):
            buf[i, w & bmask] = v[i] + d[i]
        w += 1
    return out

def _coprime_lengths(lo, hi, rng):
    """16 distinct prime lengths spread geometrically between lo and hi samples, with a small jitter."""
    def is_prime(k):
        if k < 2:
            return False
        if k % 2 == 0:
            return k == 2
        r = int(k ** 0.5) + 1
        for p in range(3, r, 2):
            if k % p == 0:
                return False
        return True
    base = np.geomspace(lo, hi, N)
    out = []
    for b in base:
        k = int(round(b * (1.0 + 0.04 * (rng.random() - 0.5))))
        while not is_prime(k) or k in out:
            k += 1
        out.append(k)
    rng.shuffle(out)
    return np.array(out, dtype=np.float64)

def _absorb(m, sr, t_dc, t_ny, t_mid, f_mid=1000.0):
    """Jot's one pole absorption filter for a line of m samples: H(z) = b / (1 - a z^-1).

    The Nyquist gain is set by t_ny; the DC gain is solved so the gain at f_mid gives RT60 t_mid.
    Returns (b, a).
    """
    g_ny = 10 ** (-3.0 * m / (sr * t_ny))
    g_mid = 10 ** (-3.0 * m / (sr * t_mid))
    w = 2 * np.pi * f_mid / sr

    def mag(g_dc):
        a = (g_dc - g_ny) / (g_dc + g_ny)
        b = g_dc * (1 - a)
        return abs(b / (1 - a * np.exp(-1j * w)))

    lo, hi = g_mid, 0.9999999
    if t_dc is not None:
        g_dc = min(10 ** (-3.0 * m / (sr * t_dc)), hi)
    else:
        if mag(hi) < g_mid:
            g_dc = hi
        else:
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                if mag(mid) < g_mid:
                    lo = mid
                else:
                    hi = mid
            g_dc = 0.5 * (lo + hi)
    a = (g_dc - g_ny) / (g_dc + g_ny)
    b = g_dc * (1 - a)
    return b, a

def predicted_rt60(line_len, fb_b, fb_a, sr, freqs):
    """The RT60 the absorption filters predict at each frequency (mean over lines)."""
    out = []
    for f in freqs:
        w = 2 * np.pi * f / sr
        ts = []
        for m, b, a in zip(line_len, fb_b, fb_a):
            g = abs(b / (1 - a * np.exp(-1j * w)))
            ts.append(-3.0 * m / (sr * np.log10(g)))
        out.append(float(np.mean(ts)))
    return np.array(out)

def _sign_vectors(rng):
    h = np.array([[1.0]])
    while h.shape[0] < N:
        h = np.block([[h, h], [h, -h]])
    rows = rng.permutation(N)
    return h, rows

def design(sr, decay=4.0, hf_ratio=0.45, size=1.0, line_ms=(30.0, 95.0), diff_ms=45.0, stages=4,
           mod_ms=0.6, mod_hz=(0.12, 0.9), seed=0):
    """Draw a deterministic tank design. Returns a dict of arrays for _run and predicted_rt60."""
    rng = np.random.default_rng(seed)
    lo = line_ms[0] * 1e-3 * sr * size
    hi = line_ms[1] * 1e-3 * sr * size
    L = _coprime_lengths(lo, hi, rng)
    t_ny = max(0.05, decay * hf_ratio)
    bs = np.zeros(N)
    as_ = np.zeros(N)
    for i, m in enumerate(L):
        bs[i], as_[i] = _absorb(m + 0.0, sr, None, t_ny, decay)
    S = int(stages)
    dd = np.zeros((S, N), dtype=np.int64)
    sg = np.zeros((S, N))
    total = diff_ms * 1e-3 * sr * size
    w = np.array([2.0 ** s for s in range(S)])
    span = total * w / w.sum()
    for s in range(S):
        dd[s] = (rng.random(N) * span[s]).astype(np.int64) + 1
        sg[s] = np.where(rng.random(N) < 0.5, -1.0, 1.0)
    h, rows = _sign_vectors(rng)
    in_l = h[rows[0]] / np.sqrt(N)
    in_r = h[rows[1]] / np.sqrt(N)
    out_l = h[rows[2]] / np.sqrt(N)
    out_r = h[rows[3]] / np.sqrt(N)
    depth = mod_ms * 1e-3 * sr * (0.6 + 0.8 * rng.random(N))
    rate = np.exp(rng.uniform(np.log(mod_hz[0]), np.log(mod_hz[1]), N))
    inc = 2 * np.pi * rate / sr
    ph0 = rng.uniform(0, 2 * np.pi, N)
    return dict(line_len=L, fb_b=bs, fb_a=as_, dif_del=dd, dif_sign=sg, in_l=in_l, in_r=in_r,
                out_l=out_l, out_r=out_r, mod_depth=depth, mod_inc=inc, mod_ph=ph0)

def biquad_lowpass(fc, sr, q):
    w = 2 * np.pi * fc / sr
    al = np.sin(w) / (2 * q)
    c = np.cos(w)
    b0 = (1 - c) / 2
    b1 = 1 - c
    b2 = (1 - c) / 2
    a0 = 1 + al
    a1 = -2 * c
    a2 = 1 - al
    return np.array([b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0])

def biquad_highpass(fc, sr, q):
    w = 2 * np.pi * fc / sr
    al = np.sin(w) / (2 * q)
    c = np.cos(w)
    a0 = 1 + al
    return np.array([(1 + c) / 2 / a0, -(1 + c) / a0, (1 + c) / 2 / a0, 1.0, -2 * c / a0, (1 - al) / a0])

def render(x2, sr, n_out, dz, shimmer=0.0, fifth=0.0, win_ms=70.0, freeze=None, ramp_ms=40.0, sgain=1.1547005,
           hp_hz=150.0):
    """Run the tank on stereo float64 input x2 for n_out samples. freeze is (start, end) in samples or None.

    sgain 1/sqrt(0.75) restores the average power the sin squared head windows lose on a diffuse tail;
    with the 150 Hz highpass in the shifted path the loop decays at every setting tried (decay 4 to 30 s,
    shimmer 0.3 to 1, fifth 0 and 0.5).
    """
    from scipy.signal import ellip
    aa = np.vstack([ellip(8, 0.1, 75, 0.40, output="sos"), biquad_highpass(hp_hz, sr, 0.7071068)[None, :]])
    K = 4 if shimmer > 0 else 0
    f0, f1 = (-1, -1) if freeze is None else (int(freeze[0]), int(freeze[1]))
    return _run(np.ascontiguousarray(x2, dtype=np.float64), int(n_out), dz["in_l"], dz["in_r"], dz["dif_del"],
                dz["dif_sign"], dz["line_len"], dz["mod_depth"], dz["mod_inc"], dz["mod_ph"], dz["fb_b"],
                dz["fb_a"], dz["out_l"], dz["out_r"], K, float(shimmer), float(fifth),
                float(win_ms * 1e-3 * sr), float(win_ms * 1.13 * 1e-3 * sr), aa, f0, f1,
                float(ramp_ms * 1e-3 * sr), float(sgain))
