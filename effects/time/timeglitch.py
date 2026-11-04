"""Develop time glitches: glitches made of time, rendered over a run of frames. A DCTL sees
one frame, so these work on the frame sequence itself: video tools call them on a cut's
window.

  rgb_split(frames, lag, env)      red from lag frames back, blue from lag ahead, green now; env (0 to 1 per frame)
                                   scales the lag, so the split opens and closes around the cut
  time_slice(frames, bands, lag, env, seed)
                                   the frame cut into horizontal bands, each from its own moment up to lag back
  stutter(frames, hold, seed)      frames frozen and jumped: runs of up to hold frames repeat, then skip ahead
  finish(frames, env, dither)      the Bayer dither (cells of 2 px at 1080) and grain scaled by env, as the other
                                   glitches
frames: a list of HxWx3 uint8 arrays; every function returns a new list of the same length. MIT License.
"""
import numpy as np

def _at(frames, i):
    return frames[min(max(i, 0), len(frames) - 1)]

def rgb_split(frames, lag, env, cut=None):
    """cut: the first frame of the incoming shot; given, the channels never reach across it (reached across,
    red from one shot and blue from the other washed the frame in flat colour)."""
    out = []
    for i, f in enumerate(frames):
        d = int(round(lag * env[i]))
        if d < 1:
            out.append(f)
            continue
        lo, hi = (0, len(frames) - 1) if cut is None else ((0, cut - 1) if i < cut else (cut, len(frames) - 1))
        o = f.copy()
        o[..., 0] = frames[min(max(i - d, lo), hi)][..., 0]
        o[..., 2] = frames[min(max(i + d, lo), hi)][..., 2]
        out.append(o)
    return out

def time_slice(frames, bands, lag, env, seed=0):
    rng = np.random.default_rng(seed)
    H = frames[0].shape[0]
    edges = np.sort(rng.choice(np.arange(8, H - 8), bands - 1, replace=False))
    edges = np.concatenate([[0], edges, [H]])
    offs = rng.integers(0, lag + 1, bands)
    out = []
    for i, f in enumerate(frames):
        if env[i] <= 0:
            out.append(f)
            continue
        o = f.copy()
        for b in range(bands):
            d = int(round(offs[b] * env[i]))
            if d:
                o[edges[b]:edges[b + 1]] = _at(frames, i - d)[edges[b]:edges[b + 1]]
        out.append(o)
    return out

def stutter(frames, hold, seed=0):
    rng = np.random.default_rng(seed)
    out, i = [], 0
    while len(out) < len(frames):
        run = int(rng.integers(1, hold + 1))
        for _ in range(run):
            if len(out) < len(frames):
                out.append(_at(frames, i))
        i += run + int(rng.integers(0, hold + 1))
    return out

def _bayer8():
    m = np.array([[0]])
    while m.shape[0] < 8:
        m = np.block([[4 * m, 4 * m + 2], [4 * m + 3, 4 * m + 1]])
    return (m + 0.5) / 64.0

def finish(frames, env, dither=0.85, grit=0.4, seed=0):
    rng = np.random.default_rng(seed + 77)
    H, W = frames[0].shape[:2]
    cell = max(1, round(2 * H / 1080))
    th = np.kron(_bayer8(), np.ones((cell, cell)))
    th = np.tile(th, (H // th.shape[0] + 1, W // th.shape[1] + 1))[:H, :W, None]
    out = []
    for i, f in enumerate(frames):
        g = env[i]
        if g <= 0:
            out.append(f)
            continue
        x = f.astype(np.float32) / 255.0
        L = (0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2])[..., None]
        x = x + grit * g * 0.16 * (0.35 + 0.65 * L) * (rng.random(x.shape[:2])[..., None] - 0.5)
        d = dither * g
        lv = 32.0 * (1 - d) + 3.0 * d - 1.0
        x = np.floor(np.clip(x, 0, 1) * lv + th) / lv
        out.append(np.clip(x * 255.0 + 0.5, 0, 255).astype(np.uint8))
    return out
