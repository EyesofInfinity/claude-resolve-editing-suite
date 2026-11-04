"""Develop Character: speakers and voices.

A small loudspeaker is a band-pass: its cone and box cannot move air below the cone's resonance, and the cone
breaks up and beams above a few kHz. Each model below is a transmission band (what the line or broadcast carries),
an amplifier that may clip softly, the speaker's resonances and its band limits, and the cone's own mild, asymmetric
breakup at the end, oversampled 4x. A voice heard through a wall follows the mass law of a partition: transmission
loss rises about 6 dB per octave above the wall's mass-spring resonance, with a dip at the coincidence frequency.

The voices: the ghost (a formant-preserving pitch shift down with a reversed, smeared swell under it), the robot
(a channel vocoder on a band-limited pulse carrier, noise for the unvoiced sounds), the ring modulator, the octaver
and the terminal voice.
"""
import math

import numpy as np
from numba import njit

import common as C
import lofi as LF

MODELS = {
    "radio": dict(band=(180.0, 4500.0), order=2, peaks=[(420.0, 1.4, 5.0), (1800.0, 1.0, 2.0)], drive=6.0,
                  breakup=0.35, noise_db=-52.0, noise_band=(300.0, 5000.0), offset=0.0),
    "telephone": dict(band=(300.0, 3400.0), order=4, peaks=[(1000.0, 0.9, 3.0), (2600.0, 2.0, 3.0)], drive=3.0,
                      breakup=0.25, codec=True, noise_db=-60.0, noise_band=(300.0, 3400.0), offset=-1.0),
    "tv": dict(band=(150.0, 7000.0), order=2, peaks=[(260.0, 1.5, 5.0), (2600.0, 1.8, 4.0)], drive=4.0,
               breakup=0.3, hum_db=-58.0, whine_db=-62.0, noise_db=-200.0, offset=0.0),
    "intercom": dict(band=(350.0, 3200.0), order=3, peaks=[(1200.0, 2.0, 6.0), (2400.0, 3.0, 3.0)], drive=10.0,
                     breakup=0.6, box_ms=2.3, noise_db=-50.0, noise_band=(400.0, 4000.0), offset=0.0),
    "wall": dict(band=(60.0, 6000.0), order=1, peaks=[(85.0, 1.0, 4.0)], drive=0.0, breakup=0.0, wall=True,
                 noise_db=-200.0, offset=-10.0),
}

def _cone(a, sr, drive_db, breakup, f=4):
    """Amplifier soft clip with the cone's asymmetry, unity slope at rest, oversampled f times."""
    if drive_db <= 0 and breakup <= 0:
        return a
    k = C.undb(drive_db)
    b = 0.35 * breakup
    up = C.oversample(a, f)
    y = (np.tanh(k * up + b) - math.tanh(b)) / (k * (1.0 - math.tanh(b) ** 2))
    y = C.undersample(y, f, a.shape[0])
    return C.butter(y, sr, "highpass", 10.0, order=1)

def _wall_sos(sr):
    """Mass law above the mass-spring resonance (about 85 Hz): a first-order fall from 220 Hz, with the coincidence
    dip of a plasterboard leaf near 2.5 kHz letting a little presence through."""
    return C.sos_chain(C.rbj("lowpass", 220.0, sr, 0.55), C.rbj("peak", 2500.0, sr, 1.2, 9.0),
                       C.rbj("highshelf", 4000.0, sr, 0.7, -6.0))

def model_sos(name, sr):
    """The linear part of a model as one sos chain (for the response plots)."""
    m = MODELS[name]
    lo, hi = m["band"]
    import scipy.signal as S
    rows = [S.butter(m["order"], lo, "highpass", fs=sr, output="sos"),
            S.butter(m["order"], min(hi, sr * 0.49), "lowpass", fs=sr, output="sos")]
    rows += [C.rbj("peak", f, sr, q, g) for f, q, g in m["peaks"]]
    if m.get("wall"):
        rows.append(_wall_sos(sr))
    return C.sos_chain(*rows)

def _room_tail(n, sr, seed, decay=0.35):
    """A short diffuse decay (the far room) as an impulse response."""
    rng = np.random.default_rng([int(seed), 401])
    L = int(sr * decay * 1.2)
    t = np.arange(L) / sr
    ir = rng.standard_normal(L) * np.exp(-6.9 * t / decay)
    ir = C.butter(ir[:, None], sr, "lowpass", 2500.0, order=1)[:, 0]
    ir[0] = 0.0
    return ir / np.sqrt(np.sum(ir ** 2))

def speaker(x, sr, model="radio", drive=None, noise_db=None, oversample=4, seed=0, mix=1.0, gain_db=0.0):
    """A voice or sound through a small speaker. model: radio, telephone, tv, intercom, wall. drive: the amplifier's
    dB into its soft clip (each model has its own default). noise_db: the line or static noise (-200 for none)."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    m = MODELS[model]
    a = C.as2d(x)
    n, ch = a.shape
    v = C.to_mono(a)
    rng = np.random.default_rng([int(seed), 402])
    if m.get("wall"):
        from scipy.signal import oaconvolve
        tail = oaconvolve(v[:, 0], _room_tail(n, sr, seed))[:n]
        v = v + 0.45 * tail[:, None] * np.sqrt(np.mean(v ** 2)) / max(np.sqrt(np.mean(tail ** 2)), 1e-12)
    lo, hi = m["band"]
    v = C.butter(v, sr, "highpass", lo, order=m["order"])
    v = C.butter(v, sr, "lowpass", hi, order=m["order"])
    if m.get("codec"):
        v = LF.quantize(LF._resample(v, sr, 8000), 8, dither=False, law="mulaw")
        v = LF._resample(v, 8000, sr)[:n]
        v = np.pad(v, ((0, max(0, n - v.shape[0])), (0, 0)))
        v = C.butter(v, sr, "lowpass", 3500.0, order=6)
    pk = np.max(np.abs(v)) if n else 1.0
    v = v / max(pk, 1e-9) * 0.5
    t = np.arange(n) / sr
    nd = m.get("noise_db", -200.0) if noise_db is None else float(noise_db)
    if nd > -150:
        z = rng.standard_normal((n, 1))
        z = C.butter(z, sr, "bandpass", m.get("noise_band", (300.0, 5000.0)), order=2)
        v = v + z / max(np.sqrt(np.mean(z ** 2)), 1e-12) * C.undb(nd)
    if m.get("hum_db"):
        hum = sum(np.sin(2 * np.pi * 60.0 * h * t) / h for h in (1, 2, 3, 5))
        v[:, 0] += hum * C.undb(m["hum_db"])
    d = m["drive"] if drive is None else float(drive)
    v = _cone(v, sr, d, m["breakup"], int(oversample))
    v = C.sos_filter(v, C.sos_chain(*[C.rbj("peak", f, sr, q, g) for f, q, g in m["peaks"]]))
    if m.get("wall"):
        v = C.sos_filter(v, _wall_sos(sr))
    if m.get("box_ms"):
        dl = int(sr * m["box_ms"] / 1000.0)
        v[dl:] += 0.5 * v[:-dl]
    v = C.butter(v, sr, "highpass", lo, order=2)
    v = C.butter(v, sr, "lowpass", hi, order=2)
    v = C.as2d(C.match_loudness(np.repeat(v, ch, axis=1), a, sr, m["offset"]))[:, :1]
    if m.get("whine_db"):
        v[:, 0] += np.sin(2 * np.pi * 15734.0 * t) * C.undb(m["whine_db"])
    return C.finish(x, np.repeat(v, ch, axis=1), mix, sr, gain_db)

def radio(x, sr, **kw):
    """An AM radio's small speaker."""
    return speaker(x, sr, model="radio", **kw)

def telephone(x, sr, **kw):
    """A telephone: the 300 to 3400 Hz line, an 8 kHz mu-law codec, the earpiece."""
    return speaker(x, sr, model="telephone", **kw)

def old_tv(x, sr, **kw):
    """A tube television's oval speaker, mains hum and the 15.7 kHz line whine of a CRT."""
    return speaker(x, sr, model="tv", **kw)

def intercom(x, sr, **kw):
    """A door or building intercom: a narrow band, a hard-driven paper cone in a tiny box."""
    return speaker(x, sr, model="intercom", **kw)

def wall(x, sr, **kw):
    """A voice heard through a wall from the next room."""
    return speaker(x, sr, model="wall", **kw)

def ghost(x, sr, shift=-5.0, formants=True, double=0.5, smear=1.2, tone=3500.0, seed=0, mix=1.0, gain_db=0.0):
    """A ghost voice: pitch moved by shift semitones with the formants held, over a reversed, smeared double that
    swells into each word. double: the swell's level (0 to 1). smear: its length in seconds."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    n, ch = a.shape
    v = C.to_mono(a)[:, 0]
    main = C.pitch_shift(v, 2.0 ** (shift / 12.0), sr, formants=bool(formants))
    out = np.repeat(main[:, None], 2, axis=1)
    if double > 0:
        from scipy.signal import oaconvolve
        rng = np.random.default_rng([int(seed), 403])
        L = int(sr * smear)
        t = np.arange(L) / sr
        rev = main[::-1]
        sw = np.zeros((n, 2))
        for c in range(2):
            ir = rng.standard_normal(L) * np.exp(-6.9 * t / max(smear, 0.05))
            sw[:, c] = oaconvolve(rev, ir)[:n][::-1]
        sw = C.butter(sw, sr, "lowpass", tone, order=2)
        sw = C.butter(sw, sr, "highpass", 120.0, order=2)
        sw *= np.sqrt(np.mean(main ** 2)) / max(np.sqrt(np.mean(sw ** 2)), 1e-12)
        out += float(double) * sw
    out = out if ch == 2 else C.to_mono(out)
    out = C.match_loudness(out, a, sr)
    return C.finish(x, out, mix, sr, gain_db)

def blit(n, sr, f0):
    """A band-limited pulse train at f0 (every harmonic below Nyquist at equal level, the Dirichlet kernel)."""
    K = int((sr / 2.0 - 100.0) // f0)
    th = 2 * np.pi * f0 * np.arange(n) / sr
    half = np.sin(th / 2.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = np.sin((K + 0.5) * th) / (2.0 * half) - 0.5
    p[np.abs(half) < 1e-9] = K
    return p / K

def robot(x, sr, pitch=110.0, unvoiced=1.0, bright=0.5, mix=1.0, gain_db=0.0):
    """A robot voice: the voice's spectral envelope laid on a buzz at a fixed pitch (Hz), with noise taking over on
    the unvoiced sounds so the consonants stay clear."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    n, ch = a.shape
    v = C.to_mono(a)[:, 0]
    nfft, hop = 2048, 256
    X = C.stft(v, nfft, hop)
    car = blit(n, sr, float(pitch))
    rng = np.random.default_rng(404)
    Cc = C.stft(car, nfft, hop)
    Nn = C.stft(rng.standard_normal(n), nfft, hop)
    lif = int(sr * 0.002)
    ev = C.true_envelope(np.abs(X), lif)
    ec = np.maximum(C.true_envelope(np.abs(Cc), lif), 1e-9)
    en = np.maximum(C.cepstral_envelope(np.abs(Nn), lif), 1e-9)
    f = np.fft.rfftfreq(nfft, 1.0 / sr)
    p = np.abs(X) ** 2
    hf = p[:, f > 3500].sum(axis=1) / np.maximum(p.sum(axis=1), 1e-20)
    u = np.clip((hf - 0.25) / 0.35, 0.0, 1.0)[:, None] * float(unvoiced)
    tilt = (np.maximum(f, 100.0) / 1000.0) ** (0.3 * (bright - 0.5))
    Y = ((1 - u) * Cc / ec + u * Nn / en) * ev * tilt
    y = C.istft(Y, n, nfft, hop)
    y = C.match_loudness(np.repeat(y[:, None], ch, axis=1), a, sr)
    return C.finish(x, y, mix, sr, gain_db)

def ringmod(x, sr, freq=180.0, drift=0.0, rate=0.3, seed=0, mix=1.0, gain_db=0.0):
    """Ring modulation by a sine at freq Hz, computed at twice the rate so the sum tones cannot fold over.
    drift: a slow wander of the carrier in percent."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    n = a.shape[0]
    up = C.oversample(a, 2)
    m = up.shape[0]
    f = np.full(m, float(freq))
    if drift > 0:
        rng = np.random.default_rng([int(seed), 405])
        f *= 1.0 + drift / 100.0 * C.smooth_noise(m, 2 * sr, rate, rng)
    ph = 2 * np.pi * np.cumsum(f) / (2 * sr)
    y = C.undersample(up * np.sin(ph)[:, None] * math.sqrt(2.0), 2, n)
    return C.finish(x, y, mix, sr, gain_db)

@njit(cache=True)
def _divider(v, hi, lo):
    """A Schmitt-triggered flip-flop: +1/-1 toggling once per input cycle, and a second stage toggling once per two."""
    n = v.shape[0]
    q1 = np.empty(n)
    q2 = np.empty(n)
    state = 0
    a = 1.0
    b = 1.0
    for i in range(n):
        if state == 0 and v[i] > hi:
            state = 1
            a = -a
            if a > 0:
                b = -b
        elif state == 1 and v[i] < lo:
            state = 0
        q1[i] = a
        q2[i] = b
    return q1, q2

def octaver(x, sr, down1=0.8, down2=0.0, up1=0.0, dry=1.0, mode="clean", mix=1.0, gain_db=0.0):
    """Octaves under (and over) the input. mode clean: phase-vocoder shifts, polyphonic. mode analog: a flip-flop
    divider on the input's zero crossings, square waves shaped by the input's envelope, monophonic and gritty."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    n, ch = a.shape
    v = C.to_mono(a)[:, 0]
    rms = max(np.sqrt(np.mean(v ** 2)), 1e-12)
    out = dry * a
    if mode == "analog":
        f = 4
        vu = C.oversample(C.butter(v[:, None], sr, "lowpass", 600.0, order=4), f)[:, 0]
        thr = 0.05 * np.max(np.abs(vu))
        q1, q2 = _divider(vu, thr, -thr)
        env = C.follow(np.abs(vu), sr * f, 2.0, 40.0)
        sq = (down1 * q1 + down2 * q2) * env
        sq = C.undersample(sq[:, None], f, n)
        sq = C.butter(sq, sr, "lowpass", 900.0, order=2)
        out = out + sq * (rms / max(np.sqrt(np.mean(sq ** 2)), 1e-12)) * max(down1, down2, 1e-9)
    else:
        for amt, r in ((down1, 0.5), (down2, 0.25), (up1, 2.0)):
            if amt > 0:
                s = C.pitch_shift(v, r, sr)
                out = out + amt * s[:, None]
    return C.finish(x, out, mix, sr, gain_db)

@njit(cache=True)
def _gate(env_db, open_db, close_db, hold, att, rel):
    n = env_db.shape[0]
    g = np.empty(n)
    target = 0.0
    held = 0
    cur = 0.0
    for i in range(n):
        if env_db[i] > open_db:
            target = 1.0
            held = hold
        elif env_db[i] < close_db:
            if held > 0:
                held -= 1
            else:
                target = 0.0
        if target > cur:
            cur += (target - cur) * att
        else:
            cur += (target - cur) * rel
        g[i] = cur
    return g

def gate_gain(v1, sr, thresh_db=-36.0, hyst_db=5.0, hold_ms=25.0, attack_ms=1.0, release_ms=35.0, floor_db=-80.0):
    """A noise gate's gain on mono v1. thresh_db is relative to the loud passages (the 95th percentile envelope)."""
    W = max(1, int(sr * 0.01))
    c = np.concatenate([np.zeros(W), np.cumsum(np.asarray(v1, dtype=np.float64) ** 2)])
    env = np.sqrt(np.maximum(c[W:] - c[:-W], 0.0) / W)
    ref = np.percentile(env, 95) if env.size else 1.0
    ed = 20 * np.log10(env / max(ref, 1e-12) + 1e-12)
    g = _gate(ed, thresh_db, thresh_db - hyst_db, int(sr * hold_ms / 1000.0), C.coef(attack_ms, sr),
              C.coef(release_ms, sr))
    fl = C.undb(floor_db)
    return fl + (1.0 - fl) * g

def terminal(x, sr, cool=0.6, bits=10, rate=32000.0, gate_db=-32.0, width=0.0, mix=1.0, gain_db=0.0):
    """The terminal voice: a cool, slightly bit-reduced, gated read. cool: 0 to 1 (low warmth cut,
    air lift). bits and rate: the reduction. gate_db: the gate's threshold below the loud passages."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    n, ch = a.shape
    v = C.to_mono(a)
    c = float(np.clip(cool, 0.0, 1.0))
    v = C.butter(v, sr, "highpass", 110.0 + 60.0 * c, order=2)
    v = C.sos_filter(v, C.sos_chain(C.rbj("lowshelf", 320.0, sr, 0.7, -4.0 * c),
                                    C.rbj("peak", 2200.0, sr, 1.0, 1.5 * c),
                                    C.rbj("highshelf", 6500.0, sr, 0.7, 3.0 * c)))
    pk = max(np.max(np.abs(v)), 1e-9)
    v = LF.bitcrush((v / pk * 0.7).astype(np.float32), sr, rate=rate, bits=bits, filters="vintage", dither=False)
    v = C.as2d(v) * pk / 0.7
    g = gate_gain(C.to_mono(a)[:, 0], sr, gate_db)
    v = v * g[:, None]
    if ch == 2 and width > 0:
        d = int(sr * 0.0007)
        y = np.concatenate([v, np.concatenate([np.zeros((d, 1)), v[:-d]]) * 1.0], axis=1)
        y = (1 - width) * np.repeat(v, 2, axis=1) + width * y
    else:
        y = np.repeat(v, ch, axis=1)
    y = C.match_loudness(y, a, sr)
    return C.finish(x, y, mix, sr, gain_db)
