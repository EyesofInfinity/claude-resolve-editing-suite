"""Develop Character: the transient shaper.

Attack and sustain by envelope difference. The detector is a trailing running maximum of the rectified signal over
one period of the lowest tone that matters (20 ms covers 50 Hz), lightly smoothed: on any steady tone above 50 Hz it
is flat, so the two followers that read it agree and the gain is exactly 0 dB. Gain moves only when the level
moves: that is what keeps it from pumping. Attack: a fast follower against a slow one, the same release. Sustain: a
long release against a short one, the same attack. Offline, so the gain is applied lookahead_ms early and the first
cycle of a hit is shaped too.
"""
import numpy as np
from scipy.ndimage import maximum_filter1d

import common as C

def shaper_gain(a, sr, attack=6.0, sustain=0.0, attack_ms=20.0, sustain_ms=300.0, window_ms=20.0, lookahead_ms=1.0,
                floor_db=-60.0):
    """The gain in dB per sample (linked across channels)."""
    d = np.max(np.abs(a), axis=1)
    W = max(1, C.secs(window_ms / 1000.0, sr))
    run = maximum_filter1d(d, size=W, origin=(W - 1) // 2, mode="nearest")
    S = max(1, C.secs(0.001, sr))
    c = np.concatenate([[0.0], np.cumsum(run)])
    det = (c[S:] - c[:-S]) / S
    det = np.concatenate([np.full(S - 1, det[0]), det])
    e1 = C.follow(det, sr, 0.5, 80.0)
    e2 = C.follow(det, sr, attack_ms, 80.0)
    e3 = C.follow(det, sr, 0.5, 50.0)
    e4 = C.follow(det, sr, 0.5, sustain_ms)
    eps = 1e-9
    att = np.clip(20 * np.log10((e1 + eps) / (e2 + eps)), 0.0, None)
    sus = np.clip(20 * np.log10((e4 + eps) / (e3 + eps)), 0.0, None)
    g = attack * np.minimum(1.0, att / 6.0) + sustain * np.minimum(1.0, sus / 6.0)
    lvl = 20 * np.log10(det + eps)
    g *= np.clip((lvl - floor_db) / 10.0, 0.0, 1.0)
    B = max(1, C.secs(0.001, sr))
    k = np.ones(B) / B
    g = np.convolve(np.pad(g, (B, B), mode="edge"), k, mode="same")[B:-B]
    la = C.secs(lookahead_ms / 1000.0, sr)
    if la > 0:
        g = np.concatenate([g[la:], np.full(la, g[-1])])
    return g

def transient(x, sr, attack=6.0, sustain=0.0, attack_ms=20.0, sustain_ms=300.0, lookahead_ms=1.0, mix=1.0,
              gain_db=0.0):
    """attack, sustain: dB of boost (positive) or cut (negative) on the hits and on their tails. attack_ms: how long
    a hit counts as its attack. sustain_ms: how long a tail counts as sustain."""
    if float(mix) == 0.0:
        return np.array(x, copy=True)
    a = C.as2d(x)
    g = shaper_gain(a, sr, attack, sustain, attack_ms, sustain_ms, lookahead_ms=lookahead_ms)
    y = a * (10.0 ** (g / 20.0))[:, None]
    return C.finish(x, y, mix, sr, gain_db)
