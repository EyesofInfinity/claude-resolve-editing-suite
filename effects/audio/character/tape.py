"""Develop Character: tape. Magnetic saturation with hysteresis, head bump and replay losses by tape speed,
wow and flutter, hiss; and the tape stop and tape start ramps.

The magnetic stage solves the Jiles-Atherton model of a ferromagnet (Jiles and Atherton 1986), integrated over the
applied field with fourth-order Runge-Kutta at an oversampled rate. Real tape is recorded with an ultrasonic bias that
pulls the recorded flux onto the anhysteretic curve; `hysteresis` sets how much of the irreversible loop survives
(0 is ideal bias, 1 is a badly under-biased machine). The replay losses are the spacing and gap losses of a replay
head (Wallace's spacing loss, the gap sinc), the head bump a low resonance set by tape speed over the head's contact
length.
"""
import math

import numpy as np
from numba import njit

import common as C

IPS = 0.0254
MS, A_, K_, ALPHA = 3.5e5, 2.2e4, 2.7e4, 1.6e-3

@njit(cache=True)
def _lang(q):
    if abs(q) < 1e-2:
        return q / 3.0 - q * q * q / 45.0
    if abs(q) > 30.0:
        return (1.0 if q > 0 else -1.0) - 1.0 / q
    return 1.0 / math.tanh(q) - 1.0 / q

@njit(cache=True)
def _dlang(q):
    if abs(q) < 5e-2:
        return 1.0 / 3.0 - q * q / 15.0
    if abs(q) > 30.0:
        return 1.0 / (q * q)
    s = math.sinh(q)
    return 1.0 / (q * q) - 1.0 / (s * s)

@njit(cache=True)
def _slope(M, H, d, c, ms, a, k, alpha):
    q = (H + alpha * M) / a
    man = ms * _lang(q)
    dman = ms / a * _dlang(q)
    dm = man - M
    irr = 0.0
    if d * dm > 0.0:
        den = (1.0 - c) * d * k - alpha * dm
        if abs(den) > 1e-9:
            irr = (1.0 - c) * dm / den
    return (irr + c * dman) / (1.0 - c * alpha * dman)

@njit(cache=True)
def _ja(h, c, ms, a, k, alpha):
    n, ch = h.shape
    out = np.zeros_like(h)
    for j in range(ch):
        M = 0.0
        H0 = 0.0
        for i in range(n):
            H1 = h[i, j]
            dH = H1 - H0
            if dH != 0.0:
                d = 1.0 if dH > 0 else -1.0
                k1 = _slope(M, H0, d, c, ms, a, k, alpha)
                k2 = _slope(M + 0.5 * dH * k1, H0 + 0.5 * dH, d, c, ms, a, k, alpha)
                k3 = _slope(M + 0.5 * dH * k2, H0 + 0.5 * dH, d, c, ms, a, k, alpha)
                k4 = _slope(M + dH * k3, H1, d, c, ms, a, k, alpha)
                M = M + dH * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
                if M > ms:
                    M = ms
                elif M < -ms:
                    M = -ms
            out[i, j] = M
            H0 = H1
    return out

def _magnetise(a, sr, drive_db, hysteresis, asym, oversample):
    """Field from signal, the loop, flux back to signal. Unity gain at -18 dBFS (the machine's operating level)."""
    c = 1.0 - 0.75 * float(np.clip(hysteresis, 0.0, 1.0))
    hpk = A_ * C.undb(drive_db)
    bias = float(asym) * 0.6 * A_
    f = int(oversample)

    def run(sig):
        up = C.oversample(sig, f) * hpk + bias
        R = int(0.05 * sr) * max(f, 1)
        lead = C.raised(np.arange(R) / R)[:, None] * up[:1]
        m = _ja(np.ascontiguousarray(np.concatenate([lead, up])), c, MS, A_, K_, ALPHA)
        m = m[R:] - m[R - 1]
        return C.undersample(m, f, sig.shape[0])

    t = np.arange(int(0.06 * sr)) / sr
    ref = (C.undb(-18.0) * np.sin(2 * np.pi * 1000.0 * t))[:, None]
    mr = run(ref)
    tail = slice(int(0.03 * sr), None)
    mr = mr - mr[tail].mean()
    g = np.sqrt(np.mean(ref[tail] ** 2) / max(np.mean(mr[tail] ** 2), 1e-30))
    y = run(a) * g
    return C.butter(y, sr, "highpass", 6.0, order=1)

def replay_response(speed_ips, sr, head_mm=7.0, spacing_um=0.7, gap_um=2.0, bump_db=2.5):
    """(sos for the head bump, FIR for the replay losses, the loss curve in dB on its frequency grid)."""
    v = max(float(speed_ips), 0.3) * IPS
    fb = v / (head_mm * 1e-3)
    bump = C.sos_chain(C.rbj("highpass", 0.45 * fb, sr, 0.6),
                       C.rbj("peak", fb, sr, 1.2, bump_db),
                       C.rbj("peak", 2.2 * fb, sr, 1.6, -0.4 * bump_db))
    f = np.linspace(10.0, sr / 2.0 - 10.0, 400)
    lam = v / f
    spacing = -54.6 * (spacing_um * 1e-6) / lam
    z = math.pi * (gap_um * 1.1e-6) / lam
    gap = 20 * np.log10(np.maximum(np.abs(np.sin(z) / z), 1e-4))
    loss = np.maximum(spacing + gap, -60.0)
    h = C.fir_from_response(f, loss, sr, taps=255)
    return bump, h, (f, loss)

def wow_flutter_curve(n, sr, wow, flutter, seed, wow_hz=0.9, flutter_hz=11.0):
    """The fractional speed deviation: wow and flutter in percent of peak deviation, each reaching its peak once on
    the clip. Deterministic by seed."""
    rng = np.random.default_rng([int(seed), 101])
    t = np.arange(n) / sr
    w = np.zeros(n)
    if wow > 0:
        fw = wow_hz * (0.85 + 0.3 * rng.random())
        cw = 0.65 * np.sin(2 * np.pi * fw * t + rng.random() * 6.283) + 0.35 * C.smooth_noise(n, sr, 1.4, rng)
        w += wow / 100.0 * cw / max(np.max(np.abs(cw)), 1e-12)
    if flutter > 0:
        ff = flutter_hz * (0.85 + 0.3 * rng.random())
        cf = (0.55 * np.sin(2 * np.pi * ff * t + rng.random() * 6.283) + 0.35 * C.smooth_noise(n, sr, 18.0, rng)
              + 0.10 * C.smooth_noise(n, sr, 70.0, rng))
        w += flutter / 100.0 * cf / max(np.max(np.abs(cf)), 1e-12)
    return w

def wow_drift(dev):
    """The read offset in samples for speed 1 + dev: the integral with its linear trend taken out, so the clip
    stays in sync end to end and on average."""
    n = dev.shape[0]
    drift = np.concatenate([[0.0], np.cumsum(dev[:-1])])
    if n > 2:
        tt = np.arange(n)
        drift -= np.polyval(np.polyfit(tt, drift, 1), tt)
    return drift

def apply_wow(a, sr, dev):
    """Play a back at speed 1 + dev."""
    if not np.any(dev):
        return a
    return C.read_at(a, np.arange(a.shape[0]) + wow_drift(dev), 1.0 + dev)

def hiss(n, ch, sr, level_db, seed, fir=None):
    rng = np.random.default_rng([int(seed), 202])
    z = rng.standard_normal((n, ch))
    z = C.sos_filter(z, C.sos_chain(C.rbj("highpass", 250.0, sr, 0.6), C.rbj("highshelf", 4000.0, sr, 0.7, 4.0)))
    if fir is not None:
        z = C.fir_same(z, fir)
    rms = np.sqrt(np.mean(z ** 2)) if n else 1.0
    return z / max(rms, 1e-12) * C.undb(level_db)

def tape(x, sr, drive=6.0, hysteresis=0.3, asym=0.1, speed=15.0, head_mm=7.0, spacing_um=0.7, bump_db=2.5,
         wow=0.08, flutter=0.05, hiss_db=-64.0, oversample=4, seed=0, mix=1.0, gain_db=0.0):
    """Tape machine. drive: dB of record level into the oxide (0 to 18). speed: inches per second (1.875, 3.75,
    7.5, 15, 30). wow, flutter: peak speed deviation in percent. hiss_db: noise RMS in dBFS (-200 for none)."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    n, ch = a.shape
    y = _magnetise(a, sr, drive, hysteresis, asym, oversample)
    bump, h, _ = replay_response(speed, sr, head_mm, spacing_um, bump_db=bump_db)
    y = C.fir_same(C.sos_filter(y, bump), h)
    if wow > 0 or flutter > 0:
        y = apply_wow(y, sr, wow_flutter_curve(n, sr, wow, flutter, seed))
    if hiss_db > -150:
        y = y + hiss(n, ch, sr, hiss_db, seed, h)
    return C.finish(x, y, mix, sr, gain_db)

def speed_curve(u, curve="smooth", start=False):
    """Speed against ramp progress u in [0, 1] for a stop (1 to 0); a start is the stop played backwards."""
    u = np.clip(u, 0.0, 1.0)
    if start:
        u = 1.0 - u
    if curve == "brake":
        s = 1.0 - u
    elif curve == "spin":
        s = (np.exp(-4.0 * u) - math.exp(-4.0)) / (1.0 - math.exp(-4.0))
    else:
        s = 0.5 + 0.5 * np.cos(np.pi * u)
    return s

def tape_stop(x, sr, at=1.0, dur=1.0, curve="smooth", level=0.7, mix=1.0, gain_db=0.0):
    """The transport stops at time at (s): speed falls to zero over dur seconds along curve (smooth, brake, spin),
    pitch falls with it, the level follows speed to the power level, and silence follows."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    n = a.shape[0]
    i0 = min(max(C.secs(at, sr), 0), n)
    L = max(1, C.secs(dur, sr))
    j = np.arange(min(L, n - i0))
    s = speed_curve((j + 0.5) / L, curve)
    pos = i0 + np.concatenate([[0.0], np.cumsum(s[:-1])])
    seg = C.read_at(a, pos, s) * (s ** float(level))[:, None]
    y = np.zeros_like(a)
    y[:i0] = a[:i0]
    y[i0:i0 + len(j)] = seg
    xf = min(C.secs(0.003, sr), len(j))
    if xf > 0:
        w = C.raised(np.arange(xf) / xf)[:, None]
        y[i0:i0 + xf] = (1 - w) * a[i0:i0 + xf] + w * seg[:xf]
    return C.finish(x, y, mix, sr, gain_db)

def tape_start(x, sr, at=1.0, dur=1.0, curve="smooth", level=0.7, mix=1.0, gain_db=0.0):
    """The transport starts from rest at time at (s) and reaches full speed after dur seconds; the read is laid so the
    material is back in sync with the original from at + dur on. Silence before at."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    n = a.shape[0]
    i0 = min(max(C.secs(at, sr), 0), n)
    L = max(1, C.secs(dur, sr))
    i1 = min(i0 + L, n)
    j = np.arange(i1 - i0)
    s = speed_curve((j + 0.5) / L, curve, start=True)
    full = speed_curve((np.arange(L) + 0.5) / L, curve, start=True)
    back = np.cumsum(full[::-1])[::-1]
    pos = (i0 + L) - back[:len(j)]
    seg = C.read_at(a, pos, s) * (s ** float(level))[:, None]
    y = np.zeros_like(a)
    y[i0:i1] = seg
    y[i1:] = a[i1:]
    xf = min(C.secs(0.003, sr), len(j))
    if xf > 0 and i1 < n:
        w = C.raised(np.arange(xf) / xf)[:, None]
        y[i1 - xf:i1] = (1 - w) * seg[-xf:] + w * a[i1 - xf:i1]
    return C.finish(x, y, mix, sr, gain_db)
