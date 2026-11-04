"""Develop Character: glitch. Stutter and beat repeat at given times, the tape-glitch scrub and the gate
pattern. Every edit is a short raised-cosine crossfade (fade_ms, default 3 ms), so no edit can step the waveform.
The edits replace audio in place: the timeline keeps running under them, so the material after a stutter is where it
was, in sync with the picture.
"""
import numpy as np

import common as C

def _beat(bpm):
    return 60.0 / float(bpm)

def _fade(L):
    return C.raised((np.arange(L) + 0.5) / L)

def stutter(x, sr, at=1.0, beats=0.25, bpm=120.0, ms=0.0, repeats=8, decay=0.85, pitch=0.0, fade_ms=3.0,
            mix=1.0, gain_db=0.0):
    """Repeat the slice that starts at each time in at (s). Its length: ms when given, else beats at bpm. The slice
    plays repeats times in all (the first is the original), each repeat decay times the last and pitch semitones
    higher (negative is lower). The original resumes after the last repeat."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    n = a.shape[0]
    L = C.secs(ms / 1000.0, sr) if ms > 0 else C.secs(beats * _beat(bpm), sr)
    L = max(L, 8)
    F = min(max(2, C.secs(fade_ms / 1000.0, sr)), L // 2)
    keep = np.ones(n)
    add = np.zeros_like(a)
    fin, fout = _fade(F), _fade(F)[::-1]
    for t in sorted(C.as_list(at)):
        i0 = C.secs(t, sr)
        if i0 >= n or i0 < 0:
            continue
        R = int(repeats)
        if R < 2:
            continue
        b = i0 + L
        e = min(n, i0 + R * L)
        if b >= n:
            continue
        seg = keep[b:min(n, b + F)]
        keep[b:min(n, b + F)] = np.minimum(seg, fout[:len(seg)])
        keep[min(n, b + F):e] = 0.0
        if e < n:
            span = min(F, n - e)
            keep[e:e + span] = np.minimum(keep[e:e + span], fin[:span])
        for i in range(1, R):
            s0 = i0 + i * L
            if s0 >= n:
                break
            m = min(L + F, n - s0)
            r = 2.0 ** (pitch * i / 12.0)
            pos = i0 + np.arange(m) * r
            chunk = C.read_at(a, pos, np.full(m, r))
            w = np.ones(m)
            w[:min(F, m)] = fin[:min(F, m)]
            if m > L:
                w[L:m] = fout[:m - L]
            add[s0:s0 + m] += chunk * (w * decay ** i)[:, None]
    y = a * keep[:, None] + add
    return C.finish(x, y, mix, sr, gain_db)

def beat_repeat(x, sr, start=0.0, end=None, bpm=120.0, interval=1.0, grid=0.125, gate=0.5, chance=1.0, decay=0.9,
                pitch=0.0, seed=0, fade_ms=3.0, mix=1.0, gain_db=0.0):
    """Beat repeat between start and end (s): every interval beats, with probability chance, the next grid beats are
    captured and repeated to fill gate of the interval."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    n = a.shape[0]
    end = n / sr if end is None else float(end)
    rng = np.random.default_rng([int(seed), 501])
    b = _beat(bpm)
    times, t = [], float(start)
    while t < end - 1e-9:
        if rng.random() < chance:
            times.append(t)
        t += interval * b
    reps = max(2, int(round(gate * interval / grid)))
    if not times:
        return C.finish(x, a, mix, sr, gain_db)
    return stutter(x, sr, at=times, beats=grid, bpm=bpm, repeats=reps, decay=decay, pitch=pitch, fade_ms=fade_ms,
                   mix=mix, gain_db=gain_db)

def scrub_offset(n, sr, dur, depth, moves, seed):
    """The drag: a smooth offset in seconds, zero with zero slope at both ends, mostly pulling back."""
    rng = np.random.default_rng([int(seed), 502])
    K = 2 * int(moves) + 1
    pts = rng.uniform(-depth, 0.35 * depth, K)
    pts[0] = 0.0
    pts[-1] = 0.0
    u = np.linspace(0.0, K - 1, n, endpoint=False)
    k = np.minimum(u.astype(int), K - 2)
    f = C.raised(u - k)
    return pts[k] + (pts[k + 1] - pts[k]) * f

def tape_scrub(x, sr, at=1.0, dur=0.6, depth=0.12, moves=3, level=0.6, seed=0, fade_ms=3.0, mix=1.0, gain_db=0.0):
    """A tape-glitch scrub at time at (s) for dur seconds: the tape is dragged back and forth under the head (depth:
    the largest pull in seconds, moves: how many pulls), its pitch and level following the speed, even backwards."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    n = a.shape[0]
    y = a.copy()
    for t in C.as_list(at):
        i0 = C.secs(t, sr)
        L = min(C.secs(dur, sr), n - i0)
        if i0 < 0 or L < 16:
            continue
        off = scrub_offset(L, sr, dur, depth, moves, seed) * sr
        pos = i0 + np.arange(L) + off
        sp = np.gradient(pos)
        g = np.minimum(1.0, np.abs(sp)) ** level
        seg = C.read_at(a, pos, np.abs(sp)) * g[:, None]
        F = min(C.secs(fade_ms / 1000.0, sr), L // 2)
        w = np.ones(L)
        w[:F] = _fade(F)
        w[L - F:] = _fade(F)[::-1]
        y[i0:i0 + L] = y[i0:i0 + L] * (1 - w)[:, None] + seg * w[:, None]
    return C.finish(x, y, mix, sr, gain_db)

def gate_curve(n, sr, pattern="x.x.xx.x", bpm=120.0, step=0.25, start=0.0, end=None, depth=1.0, attack_ms=3.0,
               release_ms=12.0, swing=0.0):
    """The gain of the pattern gate, sample by sample."""
    end = n / sr if end is None else float(end)
    lv = {"x": 1.0, "X": 1.0, "-": 0.5, ".": 0.0, "0": 0.0}
    vals = [lv.get(ch, 1.0) for ch in pattern if not ch.isspace()] or [1.0]
    st = step * _beat(bpm)
    bounds, levels = [], []
    k, t = 0, float(start)
    while t < end - 1e-9:
        bounds.append(t)
        levels.append(1.0 - depth * (1.0 - vals[k % len(vals)]))
        k += 1
        t = start + k * st + (swing * st * 0.5 if k % 2 == 1 else 0.0)
    bounds.append(end)
    levels.append(1.0)
    g = np.ones(n)
    cur = 1.0
    i_start = C.secs(start, sr)
    g[:max(0, i_start)] = 1.0
    for j in range(len(bounds)):
        b = C.secs(bounds[j], sr)
        e = C.secs(bounds[j + 1], sr) if j + 1 < len(bounds) else n
        b, e = max(0, min(b, n)), max(0, min(e, n))
        tgt = levels[j]
        if e <= b:
            continue
        R = C.secs((attack_ms if tgt > cur else release_ms) / 1000.0, sr)
        R = max(1, min(R, e - b))
        g[b:b + R] = cur + (tgt - cur) * _fade(R)
        g[b + R:e] = tgt
        cur = tgt
    return g

def gate_pattern(x, sr, pattern="x.x.xx.x", bpm=120.0, step=0.25, start=0.0, end=None, depth=1.0, attack_ms=3.0,
                 release_ms=12.0, swing=0.0, mix=1.0, gain_db=0.0):
    """A rhythmic gate between start and end (s): one character per step of step beats (x on, - half, . off),
    the pattern looping. Every change is a raised-cosine ramp (attack_ms up, release_ms down)."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    g = gate_curve(a.shape[0], sr, pattern, bpm, step, start, end, depth, attack_ms, release_ms, swing)
    return C.finish(x, a * g[:, None], mix, sr, gain_db)
