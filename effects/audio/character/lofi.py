"""Develop Character: lo-fi. Vinyl, cassette, sample-rate and bit reduction, and the memory look.

Vinyl crackle is what it is on a record: a Poisson stream of tiny impulses (dust in the groove, static, micro
scratches) that the stylus and cartridge ring as short band-passed clicks, plus rarer, larger pops with a low thump.
Rumble is the turntable's low-frequency mechanical noise, mostly vertical, so mostly in the side channel. The band
limits are those of a cutting lathe and a worn stylus: low end summed to mono and rolled off, the top rolled off.
"""
import math

import numpy as np
from scipy import signal

import common as C
import tape as T

def _impulses(n, sr, rate_hz, rng, alpha=2.2):
    """A sparse train: Poisson arrival times, heavy-tailed (Pareto) sizes, random signs."""
    k = rng.poisson(rate_hz * n / sr)
    out = np.zeros(n)
    if k == 0 or n == 0:
        return out
    idx = rng.integers(0, n, k)
    amp = (rng.pareto(alpha, k) + 1.0) * rng.choice([-1.0, 1.0], k)
    np.add.at(out, idx, amp)
    return out

def crackle_layer(n, sr, crackle, dust, seed):
    """Stereo surface noise at unit scale: crackle (dense, small, bright) and dust (sparse pops with a body)."""
    rng = np.random.default_rng([int(seed), 303])
    out = np.zeros((n, 2))
    if crackle > 0:
        rate = 30.0 + 600.0 * crackle ** 2
        for c in range(2):
            imp = _impulses(n, sr, rate * 0.7, rng)
            out[:, c] += 0.010 * imp
        shared = _impulses(n, sr, rate * 0.3, rng) * 0.010
        out += shared[:, None]
        out = C.sos_filter(out, C.sos_chain(C.rbj("bandpass", 2800.0, sr, 0.9), C.rbj("highpass", 900.0, sr, 0.7)))
    if dust > 0:
        rate = 0.3 + 3.0 * dust
        pops = _impulses(n, sr, rate, rng, alpha=1.6) * 0.05
        pan = rng.random()
        body = C.sos_filter(pops[:, None], C.rbj("bandpass", 180.0, sr, 1.2))[:, 0] * 2.5
        snap = C.sos_filter(pops[:, None], C.rbj("bandpass", 1800.0, sr, 0.8))[:, 0]
        p = body + snap
        out[:, 0] += p * (0.6 + 0.4 * pan)
        out[:, 1] += p * (1.0 - 0.4 * pan)
    return out

def vinyl(x, sr, crackle=0.4, dust=0.3, rumble=0.3, wear=0.4, warp=0.12, hiss_db=-66.0, level_db=-30.0, seed=0,
          mix=1.0, gain_db=0.0):
    """A record. crackle, dust, rumble, wear: 0 to 1. warp: peak speed deviation in percent at the 33 1/3 rpm
    rotation rate. level_db: crackle peak scale relative to full scale."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.fit_channels(C.as2d(x), 2)
    n = a.shape[0]
    mid, side = (a[:, :1] + a[:, 1:]) / 2, (a[:, :1] - a[:, 1:]) / 2
    side = C.butter(side, sr, "highpass", 150.0, order=2)
    a = np.concatenate([mid + side, mid - side], axis=1)
    top = 18000.0 - 9000.0 * wear
    y = C.butter(a, sr, "highpass", 25.0 + 15.0 * wear, order=2)
    y = C.butter(y, sr, "lowpass", top, order=2)
    y = C.sos_filter(y, C.rbj("peak", 4500.0, sr, 0.8, -1.5 * wear))
    if warp > 0:
        rng = np.random.default_rng([int(seed), 304])
        t = np.arange(n) / sr
        rot = 100.0 / 3.0 / 60.0
        dev = warp / 100.0 * (0.85 * np.sin(2 * np.pi * rot * t + rng.random() * 6.283)
                              + 0.15 * np.sin(4 * np.pi * rot * t + rng.random() * 6.283))
        y = T.apply_wow(y, sr, dev)
    surface = crackle_layer(n, sr, crackle, dust, seed) * C.undb(level_db + 30.0)
    if rumble > 0:
        rng = np.random.default_rng([int(seed), 305])
        r = C.butter(rng.standard_normal((n, 1)), sr, "lowpass", 30.0, order=2)
        r = r / max(np.sqrt(np.mean(r ** 2)), 1e-12) * C.undb(-52.0) * rumble
        surface += np.concatenate([r, -r * 0.8], axis=1)
    if hiss_db > -150:
        surface += T.hiss(n, 2, sr, hiss_db, seed)
    surface = C.butter(surface, sr, "lowpass", top, order=1)
    return C.finish(x, y + surface, mix, sr, gain_db)

def _dropouts(n, sr, amount, seed):
    """Oxide flaws: brief losses of contact, 10 to 60 ms, 2 to 12 dB, with smooth edges."""
    rng = np.random.default_rng([int(seed), 306])
    g = np.zeros(n)
    k = rng.poisson(amount * 0.6 * n / sr)
    for _ in range(k):
        c = rng.integers(0, max(n, 1))
        L = int(sr * (0.01 + 0.05 * rng.random()))
        depth = 2.0 + 10.0 * rng.random() * amount
        idx = np.arange(max(0, c - L), min(n, c + L))
        g[idx] = np.maximum(g[idx], depth * C.raised(1.0 - np.abs(idx - c) / L))
    return g

def cassette(x, sr, drive=4.0, wow=0.12, flutter=0.10, hiss_db=-54.0, dropout=0.3, azimuth_us=12.0, quality=0.5,
             seed=0, mix=1.0, gain_db=0.0):
    """A consumer cassette at 1 7/8 ips, no noise reduction. quality 0 is a worn ferric tape in a cheap deck,
    1 is a good chrome tape. dropout: 0 to 1. azimuth_us: the replay head's tilt as a time skew between channels."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.fit_channels(C.as2d(x), 2)
    n = a.shape[0]
    spacing = 0.55 - 0.3 * quality
    y = T._magnetise(a, sr, drive, 0.45 - 0.2 * quality, 0.15, 4)
    bump, h, _ = T.replay_response(1.875, sr, 1.1, spacing, bump_db=2.0)
    y = C.fir_same(C.sos_filter(y, bump), h)
    y = C.butter(y, sr, "highpass", 35.0, order=2)
    if dropout > 0:
        g = _dropouts(n, sr, dropout, seed)
        lo = C.butter(y, sr, "lowpass", 2500.0, order=1)
        hf = y - lo
        y = lo * (10 ** (-0.25 * g / 20.0))[:, None] + hf * (10 ** (-g / 20.0))[:, None]
    if wow > 0 or flutter > 0:
        y = T.apply_wow(y, sr, T.wow_flutter_curve(n, sr, wow, flutter, seed, wow_hz=0.7, flutter_hz=9.0))
    if azimuth_us > 0:
        d = azimuth_us * 1e-6 * sr
        y[:, 1] = C.read_at(y[:, 1:], np.arange(n) - d, np.ones(n))[:, 0]
    if hiss_db > -150:
        y = y + T.hiss(n, 2, sr, hiss_db + 4.0 * (0.5 - quality), seed, h)
    return C.finish(x, y, mix, sr, gain_db)

def _hold(a, sr, rate, rng_phase=0.0):
    """Sample and hold at rate: every output sample takes the most recent sample of the slow clock."""
    n = a.shape[0]
    step = sr / float(rate)
    k = np.floor((np.arange(n) + rng_phase) / step) * step - rng_phase
    idx = np.clip(np.round(k).astype(np.int64), 0, n - 1)
    return a[idx]

def quantize(a, bits, dither=True, law="linear", seed=0):
    q = 2.0 ** (float(bits) - 1.0)
    rng = np.random.default_rng([int(seed), 307])
    if law == "mulaw":
        mu = 255.0
        z = np.sign(a) * np.log1p(mu * np.minimum(np.abs(a), 1.0)) / math.log1p(mu)
        if dither:
            z = z + (rng.random(a.shape) - rng.random(a.shape)) / q
        z = np.round(z * q) / q
        return np.sign(z) * (np.expm1(np.abs(z) * math.log1p(mu)) / mu)
    z = a
    if dither:
        z = z + (rng.random(a.shape) - rng.random(a.shape)) / q
    return np.round(z * q) / q

def bitcrush(x, sr, rate=12000.0, bits=10, filters="vintage", dither=False, law="linear", seed=0, mix=1.0,
             gain_db=0.0):
    """Sample-rate and bit reduction. filters: clean (a steep anti-alias filter at the new Nyquist, then a proper
    reconstruction: the band limit of a good converter with no aliasing), vintage (gentle filters either side of a
    sample and hold: some fold-over and some images, as early samplers), none (raw sample and hold: full aliasing and
    imaging). law: linear or mulaw (the telephone companding curve)."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    n = a.shape[0]
    nyq = rate / 2.0
    if filters == "clean":
        lo = C.butter(a, sr, "lowpass", 0.45 * rate, order=8)
        z = _resample(lo, sr, rate)
        z = quantize(z, bits, dither, law, seed)
        y = _resample(z, rate, sr)[:n]
        if y.shape[0] < n:
            y = np.pad(y, ((0, n - y.shape[0]), (0, 0)))
        y = C.butter(y, sr, "lowpass", 0.45 * rate, order=8)
    elif filters == "vintage":
        lo = C.butter(a, sr, "lowpass", 0.9 * nyq, order=2)
        z = quantize(_hold(lo, sr, rate), bits, dither, law, seed)
        y = C.butter(z, sr, "lowpass", 1.1 * nyq, order=3)
    else:
        y = quantize(_hold(a, sr, rate), bits, dither, law, seed)
    return C.finish(x, y, mix, sr, gain_db)

def _ratio(a, b):
    from fractions import Fraction
    f = Fraction(float(b) / float(a)).limit_denominator(1000)
    return f.numerator, f.denominator

def _resample(a, sr_in, sr_out):
    up, down = _ratio(sr_in, sr_out)
    return signal.resample_poly(a, up, down, axis=0)

def memory(x, sr, amount=0.7, seed=0, mix=1.0, gain_db=0.0):
    """A faded memory: a narrowed, warm, band-limited copy on a worn cassette with a soft record surface, its tone
    drifting slowly darker and back. amount: 0 to 1."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.fit_channels(C.as2d(x), 2)
    n = a.shape[0]
    am = float(np.clip(amount, 0.0, 1.0))
    mid, side = (a[:, :1] + a[:, 1:]) / 2, (a[:, :1] - a[:, 1:]) / 2
    a = np.concatenate([mid + side * (1 - 0.7 * am), mid - side * (1 - 0.7 * am)], axis=1)
    y = C.butter(a, sr, "highpass", 90.0 + 110.0 * am, order=2)
    y = C.sos_filter(y, C.rbj("peak", 900.0, sr, 0.7, 2.0 * am))
    rng = np.random.default_rng([int(seed), 308])
    drift = 0.5 + 0.5 * C.smooth_noise(n, sr, 0.15, rng)
    fc = 7000.0 * (1.0 - 0.45 * am) * (0.75 + 0.25 * drift)
    y = C.svf(y, fc, sr, 0.6, "lowpass")
    y = cassette(y.astype(np.float32), sr, drive=3.0 + 3.0 * am, wow=0.08 + 0.25 * am, flutter=0.05 + 0.08 * am,
                 hiss_db=-60.0 + 8.0 * am, dropout=0.4 * am, quality=0.6 - 0.4 * am, seed=seed)
    y = vinyl(y, sr, crackle=0.25 * am, dust=0.15 * am, rumble=0.0, wear=0.6, warp=0.0, hiss_db=-200.0, seed=seed)
    y = C.match_loudness(C.as2d(y), C.as2d(x), sr, -1.5 * am)
    return C.finish(x, y, mix, sr, gain_db)
