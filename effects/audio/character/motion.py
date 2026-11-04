"""Develop Character: motion. The Doppler mover, the riser maker, the sub drop.

The mover is computed from the geometry, never from a pitch curve: a source moving on a straight line past a
listener, each ear at its own place. For every output sample and each ear the emission time is solved exactly (the
retarded time of the moving source, a quadratic for a straight path at constant speed), and the source is read at
that time with the band-limited reader. Pitch by radial velocity, level by inverse distance, the inter-aural delay
and the per-ear Doppler all fall out of that one solve. Air absorption follows ISO 9613-1 (20 C, 50 % humidity) by
distance; the head shadow is the spherical-head model of Brown and Duda (1998).
"""
import math

import numpy as np
from numba import njit

import common as C

SOUND = 343.0
EAR = 0.0875

def air_alpha(f, temp_c=20.0, humidity=50.0):
    """ISO 9613-1 pure-tone atmospheric absorption in dB per metre at one atmosphere."""
    f = np.asarray(f, dtype=np.float64)
    T, T0, T01 = temp_c + 273.15, 293.15, 273.16
    psat = 10.0 ** (-6.8346 * (T01 / T) ** 1.261 + 4.6151)
    h = humidity * psat
    frO = 24.0 + 4.04e4 * h * (0.02 + h) / (0.391 + h)
    frN = (T / T0) ** -0.5 * (9.0 + 280.0 * h * math.exp(-4.170 * ((T / T0) ** (-1.0 / 3.0) - 1.0)))
    return 8.686 * f * f * (1.84e-11 * (T / T0) ** 0.5 + (T / T0) ** -2.5 * (
        0.01275 * math.exp(-2239.1 / T) / (frO + f * f / frO) + 0.1068 * math.exp(-3352.0 / T) / (frN + f * f / frN)))

_FG = np.geomspace(200.0, 24000.0, 400)
_AG = air_alpha(_FG)

def air_cutoff(r, amount=1.0):
    """The frequency at which the air over r metres takes 3 dB (the cutoff of the matched 2-pole low pass)."""
    loss = np.outer(np.asarray(r, dtype=np.float64) * amount, _AG)
    idx = np.argmax(loss >= 3.0, axis=1)
    fc = _FG[idx]
    fc[loss[:, -1] < 3.0] = 24000.0
    return fc

def shadow_alpha(cos_theta, a_min=0.1, th_min=150.0):
    """Brown and Duda's high-frequency gain of the head shadow for an ear at angle theta from its axis."""
    th = np.degrees(np.arccos(np.clip(cos_theta, -1.0, 1.0)))
    return (1.0 + a_min / 2.0) + (1.0 - a_min / 2.0) * np.cos(np.radians(th / th_min * 180.0))

def pass_geometry(n, sr, at, speed, closest, height, direction, ear_x):
    """Emission time (s) and the source-to-ear vector at emission, for each output sample, for one ear at (ear_x, 0).
    The source moves along x at y = closest, z = height, passing x = 0 at time at."""
    v = float(speed) * (1.0 if direction == "lr" else -1.0)
    t = np.arange(n) / sr
    D2 = closest ** 2 + height ** 2
    k = v * at + ear_x
    A = SOUND ** 2 - v ** 2
    B = -2.0 * SOUND ** 2 * t + 2.0 * v * k
    Cq = SOUND ** 2 * t ** 2 - k ** 2 - D2
    disc = np.sqrt(np.maximum(B * B - 4.0 * A * Cq, 0.0))
    tau = (-B - disc) / (2.0 * A)
    qx = v * (tau - at) - ear_x
    r = np.sqrt(qx ** 2 + D2)
    return tau, qx, r

def doppler(x, sr, at=None, speed=40.0, closest=4.0, height=0.0, direction="lr", air=1.0, shadow=1.0, level_db=0.0,
            fill="silence", mix=1.0, gain_db=0.0):
    """A source passing the listener: at (s) is the moment it is nearest (default the middle of the clip), speed in
    m/s (under the speed of sound), closest and height in metres, direction lr (left to right) or rl. air scales the
    absorption, shadow the head shadow (0 to 1). The output is stereo, unity level at the closest point, in sync with
    the input at the closest point. The far ends of a pass hear sound emitted before the clip starts and the clip's
    end arrives late: fill silence leaves those as they are (the physics), fill loop plays the clip around itself
    (for steady beds such as wind or an engine)."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    n = a.shape[0]
    v1 = C.to_mono(a)
    pre = 0
    if fill == "loop":
        F = min(int(sr * 0.06), n // 3)
        pre = n - F
        v1 = loop_extend(v1, 3 * n, sr, xf_ms=60.0)
    at = n / sr / 2.0 if at is None else float(at)
    speed = min(float(speed), 0.9 * SOUND)
    D = math.sqrt(closest ** 2 + height ** 2)
    out = np.zeros((n, 2))
    for c, ex in enumerate((-EAR, EAR)):
        tau, qx, r = pass_geometry(n, sr, at, speed, closest, height, direction, ex)
        pos = (tau + D / SOUND) * sr + pre
        rate = np.abs(np.gradient(pos))
        y = C.read_at(v1, pos, rate)
        y *= (D / r)[:, None]
        if air > 0:
            blk = 64
            rb = r[::blk]
            fc = np.repeat(air_cutoff(rb, air), blk)[:n]
            y = C.svf(y, fc, sr, 0.5, "lowpass")
        if shadow > 0:
            axis = 1.0 if ex > 0 else -1.0
            cos_t = axis * qx / r
            al = 1.0 + shadow * (shadow_alpha(cos_t) - 1.0)
            lp = C.onepole_lp(y, 2.0 * SOUND / EAR / (2 * math.pi), sr)
            y = lp + al[:, None] * (y - lp)
        out[:, c] = y[:, 0]
    out *= C.undb(level_db)
    return C.finish(x, out, mix, sr, gain_db)

@njit(cache=True)
def _fdn(x, lens, g, damp):
    n = x.shape[0]
    N = lens.shape[0]
    maxl = 0
    for i in range(N):
        if lens[i] > maxl:
            maxl = lens[i]
    buf = np.zeros((N, maxl))
    idx = np.zeros(N, dtype=np.int64)
    lp = np.zeros(N)
    out = np.zeros((n, 2))
    o = np.zeros(N)
    for t in range(n):
        s = 0.0
        for i in range(N):
            j = idx[i] - lens[i]
            if j < 0:
                j += maxl
            v = buf[i, j]
            lp[i] = lp[i] + damp * (v - lp[i])
            o[i] = lp[i] * g[i]
            s += o[i]
        s *= 2.0 / N
        l = 0.0
        r = 0.0
        for i in range(N):
            fb = o[i] - s
            buf[i, idx[i]] = x[t] + fb
            idx[i] += 1
            if idx[i] >= maxl:
                idx[i] = 0
            if i % 2 == 0:
                l += o[i]
            else:
                r += o[i]
        out[t, 0] = l
        out[t, 1] = r
    return out

def fdn_reverb(v1, sr, rt60=2.5, damp_hz=6000.0):
    """A plain eight-line feedback delay network (Householder matrix, per-line decay for rt60, a damping pole)."""
    base = np.array([1031, 1327, 1523, 1801, 2053, 2311, 2659, 2903], dtype=np.int64)
    lens = (base * sr / 48000.0).astype(np.int64)
    g = 10.0 ** (-3.0 * lens / (sr * rt60))
    damp = 1.0 - math.exp(-2 * math.pi * damp_hz / sr)
    return _fdn(np.ascontiguousarray(v1, dtype=np.float64), lens, g, damp) * 0.35

def loop_extend(v, need, sr, xf_ms=60.0):
    """v made at least need samples long by looping it with equal-power crossfades at each join."""
    v = np.asarray(v, dtype=np.float64)
    if v.shape[0] >= need:
        return v
    F = min(int(sr * xf_ms / 1000.0), v.shape[0] // 3)
    out = v.copy()
    th = np.linspace(0, np.pi / 2, F) if F > 0 else np.zeros(0)
    while out.shape[0] < need:
        if F > 0:
            tail = out[-F:] * np.cos(th)[:, None] + v[:F] * np.sin(th)[:, None]
            out = np.concatenate([out[:-F], tail, v[F:]])
        else:
            out = np.concatenate([out, v])
    return out

def riser(x, sr, end=None, dur=4.0, src=0.0, semis=12.0, start_semis=-5.0, curve=1.6, lp_from=250.0, lp_to=15000.0,
          hp_from=30.0, hp_to=300.0, verb=0.6, rt60=3.0, ring=0.0, mix=1.0, gain_db=0.0):
    """Any sound made into a riser that lands at end (s; default the end of the clip): over dur seconds its tape
    speed rises from start_semis to semis, a resonant low pass opens from lp_from to lp_to, a high pass climbs, the
    reverb builds to verb and the level swells. ring: seconds the reverb rings past end. src: where in the input the
    material starts. Silence outside the riser."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    n, ch = a.shape
    e = n if end is None else min(n, C.secs(end, sr))
    L = min(C.secs(dur, sr), e)
    b = e - L
    u = (np.arange(L) + 0.5) / L
    sh = u ** curve
    rate = 2.0 ** ((start_semis + (semis - start_semis) * sh) / 12.0)
    pos = np.concatenate([[0.0], np.cumsum(rate[:-1])])
    s0 = min(C.secs(src, sr), n - 1)
    srcv = loop_extend(a[s0:], int(pos[-1]) + 64, sr)
    seg = C.read_at(srcv, pos, rate)
    seg = C.svf(seg, hp_from * (hp_to / hp_from) ** sh, sr, 0.707, "highpass")
    seg = C.svf(seg, lp_from * (lp_to / lp_from) ** sh, sr, 1.3, "lowpass")
    R = C.secs(ring, sr)
    tot = min(L + R, n - b)
    mono = np.zeros(tot)
    mono[:L] = C.to_mono(seg)[:, 0]
    wet = fdn_reverb(mono, sr, rt60)
    wamt = np.zeros(tot)
    wamt[:L] = verb * u ** 1.2
    wamt[L:] = verb
    swell = np.zeros(tot)
    swell[:L] = 0.12 + 0.88 * u ** 1.3
    Fi = min(C.secs(0.02, sr), L // 4)
    swell[:Fi] *= C.raised((np.arange(Fi) + 0.5) / Fi)
    body = np.zeros((tot, ch))
    body[:L] = C.fit_channels(seg, ch)
    y_seg = body * (swell * (1.0 - 0.5 * wamt))[:, None] + C.fit_channels(wet, ch) * (wamt * np.maximum(swell, 0))[:, None]
    if R > 0:
        y_seg[L:] = C.fit_channels(wet[L:], ch) * verb * C.raised(1.0 - np.arange(tot - L) / max(R, 1))[:, None]
    F = min(C.secs(0.012, sr), L // 4)
    y_seg[L - F:L] *= C.raised(1.0 - (np.arange(F) + 0.5) / F)[:, None] if R == 0 else 1.0
    y = np.zeros((n, ch))
    y[b:b + tot] = y_seg
    y = C.match_loudness(y, a, sr)
    return C.finish(x, y, mix, sr, gain_db)

def tune_hit(v1, sr, t, win=0.18, lo=35.0, hi=70.0, default=50.0):
    """The hit's own fundamental from YIN over the window after its onset, folded down by octaves into [lo, hi)."""
    i0 = C.secs(t + 0.005, sr)
    seg = v1[i0:i0 + C.secs(win, sr)]
    if seg.shape[0] < C.secs(0.06, sr):
        return default, 0.0
    seg = C.butter(seg[:, None], sr, "lowpass", 500.0, order=4)[:, 0]
    _, f0, ap = C.yin(seg, sr, fmin=30.0, fmax=500.0, frame=C.secs(0.04, sr))
    ok = f0 > 0
    if not np.any(ok):
        return default, 0.0
    f = float(np.median(f0[ok]))
    while f >= hi:
        f /= 2.0
    while f < lo:
        f *= 2.0
    return f, float(np.mean(ok))

def sub_drop(x, sr, at=None, hz=0.0, drop=-12.0, dur=0.9, decay=0.9, level_db=-4.0, harm=0.25, thresh_db=-30.0,
             mix=1.0, gain_db=0.0):
    """A sub-harmonic sine sweep under each hit: at (s) the hit times, else found by onset. hz: the starting pitch,
    else tuned from the hit by the pitch tracker. drop: the glide in semitones over dur. decay: seconds to -60 dB.
    level_db: the sweep's peak against the hit's peak. harm: soft saturation for small speakers."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    n, ch = a.shape
    v1 = C.to_mono(a)[:, 0]
    times = C.as_list(at) if at is not None and str(at) != "" else C.onsets(a, sr, thresh_db)
    sub = np.zeros(n)
    tunes = []
    for t in times:
        i0 = C.secs(t, sr)
        if i0 >= n:
            continue
        f0 = float(hz) if hz > 0 else tune_hit(v1, sr, t)[0]
        tunes.append(f0)
        L = min(C.secs(dur, sr), n - i0)
        tt = np.arange(L) / sr
        u = tt / max(dur, 1e-6)
        f = f0 * 2.0 ** (drop * (1.0 - (1.0 - u) ** 2) / 12.0)
        ph = 2 * np.pi * np.concatenate([[0.0], np.cumsum(f[:-1])]) / sr
        env = np.exp(-6.9 * tt / max(decay, 1e-3))
        A = min(C.secs(0.004, sr), L)
        env[:A] *= C.raised((np.arange(A) + 0.5) / A)
        E = min(C.secs(0.02, sr), L)
        env[L - E:] *= C.raised(1.0 - (np.arange(E) + 0.5) / E)
        s = np.sin(ph)
        if harm > 0:
            k = 1.0 + 4.0 * harm
            s = np.tanh(k * s) / math.tanh(k)
        pk = np.max(np.abs(v1[i0:i0 + C.secs(0.1, sr)])) if L else 0.0
        sub[i0:i0 + L] += s * env * pk * C.undb(level_db)
    sub_drop.last_tunes = tunes
    y = a + sub[:, None]
    return C.finish(x, y, mix, sr, gain_db)
