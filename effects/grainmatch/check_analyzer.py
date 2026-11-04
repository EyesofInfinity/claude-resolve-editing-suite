"""Checks of the grain analyzer on synthetic frames with known grain. MIT License.

Each case builds frames of a picture (smooth shading, a sky ramp, optional texture the grain must not be confused
with) plus grain of known strength per band, size, colour correlation and frame-to-frame hold, then reads it back.
usage: python -I check_analyzer.py
"""
import os, sys, time
import numpy as np
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grainlib as gl

fails = count = 0

def ok(name, cond, info):
    global fails, count
    count += 1
    print(("pass " if cond else "FAIL ") + name + " " + info, flush=True)
    if not cond:
        fails += 1

def field(shape, s, rng):
    return gl.gaussian_field(shape, s, rng)

def picture(H, W, texture, rng):
    """Display values: a ramp from dark to bright left to right with soft shading, and optional texture patches
    (a band of foliage-like 1/f texture over the middle third)."""
    y, x = np.mgrid[0:H, 0:W].astype(np.float64)
    base = 0.06 + 0.86 * x / W + 0.03 * np.sin(y / 90) + 0.02 * np.cos(x / 130)
    img = np.stack([base * 0.95, base, base * 1.03], -1)
    if texture:
        t = np.zeros((H, W))
        for s, a in ((1.0, 0.5), (2.5, 0.8), (6, 1.0), (15, 1.2)):
            t += a * field((H, W), s, rng)
        t = t / t.std() * 0.06
        m = (y > H / 3) & (y < 2 * H / 3)
        img += (t * m)[..., None]
    return np.clip(img, 0, 1)

def grain_frames(H, W, n, sd_y, sd_c, size_y, size_c, hold, texture, rng, corr_ycb=0.0, pan=0):
    """sd_y, sd_c: functions of display luma giving codes (x 255). pan: the picture moves this many px a frame."""
    big = picture(H, W + pan * n, texture, rng)
    stat = [field((H, W), size_y, rng), field((H, W), size_c, rng), field((H, W), size_c, rng)]
    frames = []
    for t in range(n):
        pic = big[:, pan * t:pan * t + W]
        new = [field((H, W), size_y, rng), field((H, W), size_c, rng), field((H, W), size_c, rng)]
        z = [np.sqrt(hold) * s + np.sqrt(1 - hold) * f for s, f in zip(stat, new)]
        zcb = corr_ycb * z[0] + np.sqrt(1 - corr_ycb ** 2) * z[1] if size_y == size_c else z[1]
        Y = gl.to_ycc(pic)[..., 0]
        ny = sd_y(Y) / 255 * z[0]
        ncb = sd_c(Y) / 255 * zcb
        ncr = sd_c(Y) / 255 * z[2]
        M = gl.ycc_to_rgb_matrix()
        n3 = np.stack([ny, ncb, ncr], -1) @ M.T
        frames.append(np.clip(pic + n3, 0, 1).astype(np.float32))
    return frames

def main():
    rng = np.random.default_rng(11)
    H, W, n = 1080, 1920, 6
    flat = lambda v: (lambda Y: np.full_like(Y, v))
    for size, tex, pan in ((0.0, False, 0), (0.8, False, 3), (1.6, True, 0), (2.4, True, 0), (1.2, True, 3)):
        t0 = time.time()
        fr = grain_frames(H, W, n, flat(3.0), flat(1.5), size, size, 0.0, tex, rng, pan=pan)
        r = gl.analyze(fr)
        sd = [r["bands"][b]["sd"]["Y"] for b in gl.BAND_NAMES]
        sc = [r["bands"][b]["sd"]["Cb"] for b in gl.BAND_NAMES]
        err = max(abs(s / 3.0 - 1) for s in sd)
        errc = max(abs(s / 1.5 - 1) for s in sc)
        ok(f"grain 3 codes (size {size} px, texture {tex}, pan {pan} px a frame) reads back within 5%", err < 0.05,
           f"Y {sd} acf {r['acf']['y1']} gauss size {r['gauss_size_y']} hold {r['hold']} ({time.time() - t0:.1f} s)")
        ok(f"colour grain 1.5 codes (size {size}, texture {tex}, pan {pan}) within 7%", errc < 0.07, f"Cb {sc}")
        ok(f"size {size} px reads back within 0.15 px", abs(r["gauss_size_y"] - size) < 0.15 or (size == 0 and r["gauss_size_y"] < 0.3),
           f"{r['gauss_size_y']}")
    def by_band(a, b, c):
        return lambda Y: np.sqrt(gl.tents(Y) @ np.array([a * a, b * b, c * c]))
    fr = grain_frames(H, W, n, by_band(4, 2.5, 1.5), by_band(2, 1.2, 0.6), 1.0, 1.0, 0.0, True, rng)
    r = gl.analyze(fr)
    sd = [r["bands"][b]["sd"]["Y"] for b in gl.BAND_NAMES]
    ok("band strengths 4, 2.5, 1.5 read back within 6%", all(abs(s / t - 1) < 0.06 for s, t in zip(sd, (4, 2.5, 1.5))),
       f"Y {sd} Cr {[r['bands'][b]['sd']['Cr'] for b in gl.BAND_NAMES]}")
    fr = grain_frames(H, W, n, flat(3.0), flat(1.5), 1.0, 1.0, 0.5, False, rng)
    r = gl.analyze(fr)
    m = r["bands"]["mids"]["sd"]["Y"]
    ok("hold 0.5 reads back within 0.06 and the moving grain at 2.12 codes", abs(r["hold"] - 0.5) < 0.06 and abs(m / 2.1213 - 1) < 0.05,
       f"hold {r['hold']} moving {m} still {r['static_sd_y']}")
    fr = grain_frames(H, W, n, flat(3.0), flat(3.0), 1.0, 1.0, 0.0, False, rng, corr_ycb=0.6)
    r = gl.analyze(fr)
    ok("Y to Cb correlation 0.6 reads back within 0.05", abs(r["corr"]["Y_Cb"] - 0.6) < 0.05, json_s(r["corr"]))
    tex = picture(H, W, False, rng)
    t = sum(a * field((H, W), s, rng) for s, a in ((1.0, 0.5), (2.5, 0.8), (6, 1.0), (15, 1.2)))
    busy = [np.clip(tex + (t / t.std() * 0.08)[..., None] + 0.5 / 255 * rng.standard_normal((H, W, 1)), 0, 1).astype(np.float32)
            for _ in range(4)]
    r = gl.analyze(busy)
    m = r["bands"]["mids"]["sd"]["Y"]
    ok("still texture everywhere: only the moving grain (0.5 codes) is read", abs(m / 0.5 - 1) < 0.08,
       f"mids {m} hold {r['hold']} notes {r['notes']}")
    big = picture(H, W + 40, False, rng)
    t = sum(a * field((H, W + 40), s, rng) for s, a in ((1.0, 0.5), (2.5, 0.8), (6, 1.0), (15, 1.2)))
    pic = np.clip(big + (t / t.std() * 0.08)[..., None], 0, 1)
    pan = [(pic[:, 5 * k:5 * k + W] + 0.5 / 255 * rng.standard_normal((H, W, 1))).astype(np.float32) for k in range(4)]
    r = gl.analyze(pan)
    ok("moving texture everywhere is flagged", any("upper bound" in s or "no band" in s or "too few" in s for s in r["notes"]),
       f"mids {r['bands']['mids']['sd']['Y'] if r['bands'] else None} notes {r['notes']}")
    print(f"{count - fails} of {count} pass")
    sys.exit(1 if fails else 0)

def json_s(d):
    import json
    return json.dumps(d)

if __name__ == "__main__":
    main()
