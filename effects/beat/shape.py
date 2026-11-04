"""The envelope engine of beat.h in Python, line for line, from the same packed tables: the reference the
DCTL is checked against (check.mjs), the curve the renderers' --link takes (link_curve), and the frame list of the
hits a demo should show. MIT License.
"""
import math

import numpy as np

def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)

class Engine:
    def __init__(self, packed):
        self.meta = packed["meta"]
        self.lists = [packed["beat"] or [0.0], packed["hit"] or [0.0], packed["kick"] or [0.0]]
        self.curve = packed["curve"] or [0.0]

    @staticmethod
    def fe(v, fps):
        return math.floor(math.floor(v / 128.0) * fps / 100.0 + 0.5)

    def last(self, s, n, tf, fps):
        lo, hi, r = 0, n - 1, -1
        L = self.lists[s]
        while lo <= hi:
            m = (lo + hi) >> 1
            if self.fe(L[m], fps) <= tf:
                r, lo = m, m + 1
            else:
                hi = m - 1
        return r

    @staticmethod
    def passes(s, v, src, min_tier, accent):
        pay = v - 128.0 * math.floor(v / 128.0)
        tier = pay - 4.0 * math.floor(pay / 4.0)
        if tier < min_tier - 0.5:
            return 0.0
        if s == 0:
            bar = math.floor(pay / 4.0) - 8.0 * math.floor(pay / 32.0)
            bs = math.floor(pay / 32.0)
            if src == 1 and bar > 0.5:
                return 0.0
            return (1.0 if bar < 0.5 else 1.0 - accent) * (0.8 + 0.2 * bs / 3.0)
        down = math.floor(pay / 4.0) - 2.0 * math.floor(pay / 8.0)
        hs = math.floor(pay / 8.0)
        return (1.0 if down > 0.5 else 1.0 - accent) * (0.35 + 0.65 * hs / 15.0)

    @staticmethod
    def after(dt, s, shape, rel):
        if shape == 0:
            return s * math.exp(-2.302585 * dt / rel)
        if shape == 1:
            return s * (1.0 - smooth(0.0, rel, dt))
        return s * math.exp(-2.302585 * dt / 1.5)

    @staticmethod
    def before(d, s, shape, atk, rel):
        ln = rel if shape == 2 else atk
        if ln <= 0.0 or d >= ln:
            return 0.0
        u = 1.0 - d / ln
        return s * u * u

    @staticmethod
    def finish(duck, near, shape, fps):
        if shape != 1:
            return duck
        return (1.0 - duck) * (1.0 - smooth(2.0 * fps, 4.0 * fps, near))

    def event_env(self, src, tf, fps, shape, atk, rel, accent, min_tier):
        s = 0 if src < 2 else src - 1
        n = int(self.meta[s])
        if n <= 0:
            return 0.0
        i = self.last(s, n, tf, fps)
        e, near, found = 0.0, 1e9, 0
        L = self.lists[s]
        j = i
        while j >= 0 and j > i - 32 and found < 3:
            st = self.passes(s, L[j], src, min_tier, accent)
            if st > 0.001:
                dt = tf - self.fe(L[j], fps)
                if found == 0:
                    near = dt
                e = max(e, self.after(dt, st, shape, rel))
                found += 1
            j -= 1
        for j in range(i + 1, min(n, i + 33)):
            st = self.passes(s, L[j], src, min_tier, accent)
            if st > 0.001:
                d = self.fe(L[j], fps) - tf
                near = min(near, d)
                e = max(e, self.before(d, st, shape, atk, rel))
                break
        return self.finish(e, near, shape, fps)

    def grid_env(self, src, tf, fps, bpm, meter, shape, atk, rel, accent, min_tier):
        spb = 60.0 / bpm
        pf = fps * spb
        gap = 0.5 if min_tier > 2.5 else (0.36 if min_tier > 1.5 else (0.25 if min_tier > 0.5 else 0.125))
        stride = meter if src == 1 else 1.0
        k = 0
        while k < 6 and stride * spb < gap - 0.0001:
            stride *= 2.0
            k += 1
        kb = math.floor(tf / (pf * stride))
        if math.floor(kb * stride * pf + 0.5) > tf:
            kb -= 1
        if math.floor((kb + 1) * stride * pf + 0.5) <= tf:
            kb += 1
        e, near = 0.0, 1e9
        for k in range(3):
            nb = (kb - k) * stride
            if nb < 0:
                break
            fe = math.floor(nb * pf + 0.5)
            bar = nb - meter * math.floor(nb / meter)
            st = 1.0 if bar < 0.5 else 1.0 - accent
            if k == 0:
                near = tf - fe
            if st > 0.001:
                e = max(e, self.after(tf - fe, st, shape, rel))
        nn = (kb + 1) * stride
        if nn >= 0:
            fe = math.floor(nn * pf + 0.5)
            bar = nn - meter * math.floor(nn / meter)
            st = 1.0 if bar < 0.5 else 1.0 - accent
            near = min(near, fe - tf)
            if st > 0.001:
                e = max(e, self.before(fe - tf, st, shape, atk, rel))
        return self.finish(e, near, shape, fps)

    @staticmethod
    def band(v, b):
        lo = math.floor(v / 65536.0)
        mi = math.floor(v / 256.0) - 256.0 * lo
        hi = v - 65536.0 * lo - 256.0 * mi
        return (lo if b == 0 else (mi if b == 1 else hi)) / 255.0

    def curve_at(self, b, tsec):
        n = int(self.meta[3])
        if n <= 0 or tsec < 0:
            return 0.0
        x = tsec * self.meta[4]
        if x >= n - 1.0:
            return 0.0 if x > n else self.band(self.curve[n - 1], b)
        i = int(math.floor(x))
        f = x - math.floor(x)
        return self.band(self.curve[i], b) * (1 - f) + self.band(self.curve[i + 1], b) * f

    def env(self, frame, start_s=0.0, nudge=0.0, fps=24.0, src=0, shape=0, atk=0.0, rel=6.0, accent=0.4,
            min_tier=1.0, bpm=0.0, floorv=0.25):
        tf = frame - math.floor(start_s * fps + 0.5) - nudge
        rl = max(rel, 0.5)
        if src >= 4:
            v = self.curve_at(src - 4, tf / fps)
            e = min(1.0, max(0.0, (v - floorv) / max(0.001, 1.0 - floorv)))
            if shape == 1:
                e = 0.0 if (tf < 0 or tf / fps > self.meta[7]) else 1.0 - e
            if shape == 2:
                e = e * e
        elif bpm > 0.5 or self.meta[7] <= 0.0:
            e = self.grid_env(src, tf, fps, bpm if bpm > 0.5 else 120.0, max(1.0, self.meta[6]), shape, atk, rl,
                              accent, min_tier)
        else:
            e = self.event_env(src, tf, fps, shape, atk, rl, accent, min_tier)
        return 0.0 if e < 0.004 else min(1.0, max(0.0, e))

def tier_for(rate, bright):
    t = 0.0 if rate >= 7.99 else (1.0 if rate >= 3.99 else (2.0 if rate >= 2.77 else 3.0))
    return max(t, 2.0) if bright else t

SOURCES = {"beats": 0, "downbeats": 1, "hits": 2, "low": 3, "bass": 4, "mids": 5, "highs": 6}
SHAPES = {"hit": 0, "pump": 1, "swell": 2}

def from_sliders(engine, sliders, frames):
    """The envelope a Develop Beat with these slider values gives on these timeline frames."""
    s = sliders
    fps = s.get("btFps", 24.0)
    mode = int(s.get("btMode", 0) + 0.5)
    bright = mode in (0, 3, 4, 5)
    tier = tier_for(s.get("btRate", 4.0), bright)
    return np.array([engine.env(f, s.get("btStart", 0.0), s.get("btNudge", 0.0), fps, int(s.get("btSource", 0) + 0.5),
                                int(s.get("btShape", 0) + 0.5), s.get("btAttack", 0.0) * fps / 1000.0,
                                s.get("btRelease", 250.0) * fps / 1000.0, s.get("btAccent", 40.0) / 100.0, tier,
                                s.get("btBpm", 0.0), s.get("btFloor", 25.0) / 100.0) for f in frames])
