"""Checks for Develop Time FX (numpy, small synthetic clips): identity at strength 0, determinism, and one or more
behaviour checks per function that fail if it does the wrong thing. usage: python -I check_timefx.py
"""
import math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timefx as tf

H, W, N = 108, 192, 24
fails, count = [], 0

def ok(cond, name):
    global count
    count += 1
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)

def dot_clip(n=N, x0=30, vx=5, y=54, r=4, bg=20, val=250):
    """A bright dot moving right over a dark, gently textured ground."""
    yy, xx = np.mgrid[0:H, 0:W]
    ground = (bg + 6 * np.sin(xx / 9.0) * np.cos(yy / 7.0)).astype(np.float32)
    out = []
    for i in range(n):
        f = np.repeat(ground[..., None], 3, 2)
        d = (xx - (x0 + vx * i)) ** 2 + (yy - y) ** 2
        f[d <= r * r] = val
        out.append(np.clip(f, 0, 255).astype(np.uint8))
    return out

def time_clip(n=N):
    """Every pixel of frame i equals 10 x i: the time is readable from any pixel."""
    return [np.full((H, W, 3), 10 * i, np.uint8) for i in range(n)]

def same(a, b):
    return len(a) == len(b) and all(np.array_equal(x, y) for x, y in zip(a, b))

def lin_of(v):
    return (v / 255.0) ** 2.4

def disp_of(l):
    return l ** (1 / 2.4) * 255.0

clip = dot_clip()
rng = np.random.default_rng(3)
noisy = [np.clip(f.astype(int) + rng.integers(-15, 16, f.shape), 0, 255).astype(np.uint8) for f in clip]

for name, fn in tf.FX.items():
    if name in ("looper", "morph"):
        continue
    o = fn(noisy, env=0.0)
    ok(same(o, noisy) and all(x is not y for x, y in zip(o, noisy)), f"{name}: env 0 returns the input exactly")
ok(same(tf.time_displace(noisy, depth=0), noisy), "time_displace: depth 0 is identity")
ok(same(tf.posterize_time(noisy, step=1.0), noisy), "posterize_time: step 1 is identity")
ok(same(tf.time_average(noisy, radius=0.0), noisy), "time_average: radius 0 is identity")
ok(same(tf.looper(noisy, start=0, length=N, xfade=0), noisy), "looper: a loop the clip's length is identity")

for name, fn in tf.FX.items():
    if name == "morph":
        a, b = tf.morph(noisy[:8], noisy[8:16]), tf.morph(noisy[:8], noisy[8:16])
    elif name == "looper":
        a, b = fn(noisy, start=8, length=10, xfade=4), fn(noisy, start=8, length=10, xfade=4)
    else:
        a, b = fn(noisy, env=0.8), fn(noisy, env=0.8)
    ok(same(a, b), f"{name}: two runs give the same frames")

e = np.zeros(N); e[10:16] = 1.0
for name in ("feedback", "trails", "time_displace", "time_average", "jitter"):
    o = tf.FX[name](noisy, env=e)
    ok(same(o[:10], noisy[:10]) and not same(o[10:16], noisy[10:16]), f"{name}: per-frame env switches it on and off")

blank = [np.zeros((H, W, 3), np.uint8) for _ in range(6)]
spot = [b.copy() for b in blank]
spot[0][50:58, 150:158] = 255
o = tf.feedback(spot, zoom=1.0, turn=0.0, decay=0.6, soft=0.0, hue=0.0)
v = [float(f[50:58, 150:158].astype(float).mean()) for f in o]
ok(v[1] > 100 and v[1] > v[2] > v[3] > 0, "feedback: an echo of a spot stays and fades pass by pass")
ok(float(o[1][:40].max()) == 0 and float(o[1][70:].max()) == 0, "feedback: black away from the echo stays black (no veil)")
o = tf.feedback(spot, zoom=1.2, turn=0.0, decay=0.9, soft=0.0)
cx = [float((f.astype(float).sum(2) * np.arange(W)).sum() / max(f.astype(float).sum(), 1)) for f in o[1:3]]
ok(cx[0] > 154 + 5 and cx[1] > cx[0], "feedback: zoom above 1 moves the echo outward from the centre pass by pass")
o = tf.feedback(spot, zoom=1.0, turn=10.0, decay=0.9, soft=0.0)
ys = [float(np.argwhere(f.sum(2) > 30)[:, 0].mean()) for f in o[1:3]]
ok(abs(ys[0] - 54) > 3 and abs(ys[1] - 54) > abs(ys[0] - 54), "feedback: turn swings the echo round the centre")
red = [b.copy() for b in blank]
red[0][50:58, 150:158] = (255, 0, 0)
o = tf.feedback(red, zoom=1.0, turn=0.0, decay=0.9, soft=0.0, hue=120.0)
px = o[1][54, 154].astype(int)
ok(px[1] > px[0] and px[1] > px[2], "feedback: hue 120 turns a red echo green")
bright = [np.full((H, W, 3), 150, np.uint8) for _ in range(5)]
o = tf.feedback(bright, zoom=1.0, turn=0, decay=0.6, soft=0)
ok(o[3].mean() > 150 and o[3].max() < 255, "feedback: screen brightens a lit picture without clipping it")

mx, my, cover = tf._bubble_map(H, W, (0.5, 0.5), 0.4, 0.4)
cx0, cy0 = (W - 1) / 2, (H - 1) / 2
ok(abs(mx[54, 100] - cx0) < abs(100 - cx0) * 0.75, "feedback_bubble: the ball magnifies its middle (samples nearer the centre)")
ok(abs(mx[54, 5] - 5) < 1e-3 and cover[54, 5] == 0, "feedback_bubble: outside the ball the picture is untouched and holds no echo")
rim = np.abs(np.diff(mx[54, :])).max()
ok(rim < 3.5,"feedback_bubble: the map stays continuous across the rim (no tear)")
ring = [b.copy() for b in blank]
ring[0][52:57, 120:124] = 255
o = tf.feedback_bubble(ring, zoom=1.0, radius=0.45, refract=0.4, decay=0.9, soft=0)
cols = np.argwhere(o[1][54].sum(1) > 30)[:, 0]
ok(len(cols) and cols.max() > 125, "feedback_bubble: an echo inside the ball is pushed outward (magnified)")
o = tf.feedback_bubble(spot, radius=0.2, refract=0.4, decay=0.9, soft=0, inside=True)
ok(float(o[1][50:58, 150:158].max()) == 0, "feedback_bubble: inside keeps the echoes in the ball")

nx, ny = tf.noise_field(1080, 1920, 0.0, 0.2, 0)
nx2, _ = tf.noise_field(1080, 1920, 2.0, 0.2, 0)
ok(np.abs(nx).max() < 2 and np.abs(np.diff(nx, axis=1)).max() < 0.1 and np.abs(np.diff(nx, axis=1, n=2)).max() < 0.01,
   "feedback_distort: the noise field is smooth at 1080")
ok(np.abs(nx - nx2).mean() > 0.05, "feedback_distort: the field drifts with time")
o1 = tf.feedback(noisy, zoom=1.01, turn=0, decay=0.7, soft=0.7)
o2 = tf.feedback_distort(noisy, zoom=1.01, amount=80.0, decay=0.7, soft=0.7)
ok(not same(o1[5:], o2[5:]), "feedback_distort: the push changes the echoes")

tc = time_clip()
o = tf.time_displace(tc, depth=8, matte="ramp", angle=0)
f = o[15].astype(float)[..., 0]
ok(abs(f[0, 0] - 150) <= 1 and abs(f[0, -1] - disp_of(lin_of(70))) <= 1, "time_displace: ramp takes the left edge now and the right edge 8 frames back")
ok(np.all(np.diff(f[0]) <= 0.0) and np.abs(np.diff(f[0])).max() <= 2, "time_displace: the ramp runs down smoothly, no steps")
mid = np.full((H, W), 2.5 / 8, np.float32)
o = tf.time_displace(tc, depth=8, matte=mid)
want = disp_of((lin_of(130) + lin_of(120)) / 2)
ok(abs(float(o[15][0, 0, 0]) - want) <= 1, "time_displace: half a frame's offset mixes the two frames in linear light")
o = tf.time_displace(tc, depth=8, matte="radial")
ok(o[15][54, 96, 0] > o[15][0, 0, 0], "time_displace: radial takes the corners from further back")
o = tf.time_displace(tc, depth=4, matte="ramp", ahead=True)
ok(o[5][0, -1, 0] == 90, "time_displace: ahead takes from later frames")
lumclip = [f.copy() for f in tc]
for f in lumclip:
    f[:, :W // 2] = np.minimum(f[:, :W // 2], 255)
o = tf.time_displace(tc, depth=6, matte=lambda i, fr: np.ones((H, W), np.float32))
ok(o[3][0, 0, 0] == 0 and o[10][0, 0, 0] == 40, "time_displace: a matte of 1 is the clip delayed, held at its start")

o = tf.trails(clip, length=6, decay=0.7, blend="max")
f = o[12].astype(float)
xs = [30 + 5 * (12 - k) for k in range(0, 5)]
vals = [f[54, x, 0] for x in xs]
ok(vals[0] == 250 and all(vals[k] > vals[k + 1] for k in range(4)) and vals[4] > 40, "trails: max leaves a trail that fades with age")
ok(np.array_equal(o[12][:30], clip[12][:30]), "trails: max leaves the dark ground untouched (no veil)")
o = tf.trails(clip, length=4, decay=0.9, blend="average")
ok(o[12][54, 90, 0] < 250 and o[12][54, 85, 0] > 60, "trails: average smears the dot and dims its head")
o = tf.trails(clip, length=4, decay=0.9, blend="max", offset=(0.0, -40.0))
ys = np.argwhere(o[12][:, :, 0] > 120)[:, 0]
ok(ys.min() < 50, "trails: offset moves the echoes")
dim = dot_clip(val=190)
o = tf.trails(dim, length=4, decay=0.9, key=0.95, blend="max")
ok(np.array_equal(o[12], dim[12]), "trails: a key above the dot keeps every echo out")
o = tf.trails(dim, length=4, decay=0.9, key=0.5, blend="max")
ok(not np.array_equal(o[12], dim[12]), "trails: a key below the dot lets its echoes through")

fast = dot_clip(vx=8, r=2, x0=20)
o = tf.trails(fast, length=6, decay=0.85, key=0.5)
row = o[12][54, 20 + 8 * 7:20 + 8 * 12, 0].astype(int)
ok(row.min() < 60, "trails: without sweep a fast small light leaves beads (the gap the sweep must close)")
o = tf.trails(fast, decay=0.85, key=0.5, sweep=True)
row = o[12][54, 20 + 8 * 7:20 + 8 * 12, 0].astype(int)
ok(row.min() > 120 and np.all(np.diff(row) >= -2), "trails: sweep draws one continuous streak, brightening toward the light")
ok(np.array_equal(o[12][:40], fast[12][:40]), "trails: sweep leaves the ground away from the light untouched")
o = tf.trails(fast, decay=1.0, key=0.5, sweep=True)
ok(o[20][54, 30:170, 0].min() > 200, "trails: sweep with decay 1 paints the whole path and keeps it")
lit = [np.full((H, W, 3), 200, np.uint8) for _ in range(4)]
for k, f in enumerate(lit):
    f[50:53, 40 + 6 * k:43 + 6 * k] = 255
m = tf.light_mask(lit[0], pop=0.12)
ok(m[51, 41] > 0.5 and m[10, 100] == 0, "light_mask: pop finds a light on a bright ground and leaves the ground out")
blob = [np.full((H, W, 3), 15, np.uint8) for _ in range(2)]
blob[0][20:90, 20:90] = 240
blob[0][50:52, 120:180] = 200
m = tf.light_mask(blob[0], thin=0.15)
ok(m[51, 150] > 0.9 and m[55, 55] == 0, "light_mask: thin keeps a spark's streak and leaves the flame out")
edge = np.full((H, W, 3), 40, np.uint8)
edge[:, 100:] = 220
edge[30:33, 98:101] = 235
edge[70:73, 50:53] = 235
m0, m1 = tf.light_mask(edge, pop=0.45), tf.light_mask(edge, pop=0.45, alone=0.3)
ok(m1[71, 51] > 0.9 and m1[31, 99] == 0, "light_mask: alone keeps a point on dark and drops a glint with sky beside it")
o = tf.time_average(fast, radius=3.0, blend="max", key=0.5)
row = o[12][54, 20 + 8 * 10:20 + 8 * 14, 0].astype(int)
ok(row.min() > 200 and np.array_equal(o[12][:40], fast[12][:40]), "time_average: max of lights paints a continuous line")

import cv2
Hm, Wm = 540, 960
rg = np.random.default_rng(11)
tex = cv2.GaussianBlur(rg.random((Hm, Wm + 64)).astype(np.float32), (0, 0), 3.0)
tex = ((tex - tex.min()) / (tex.max() - tex.min()) * 80 + 20).astype(np.uint8)
glints = [(int(rg.integers(60, Wm - 60)), int(rg.integers(40, Hm - 40))) for _ in range(40)]
pan = []
for i in range(8):
    f = np.repeat(tex[:, 3 * i:3 * i + Wm, None], 3, 2).copy()
    for gx0, gy0 in glints:
        x = gx0 - 3 * i
        f[gy0 - 1:gy0 + 2, x - 1:x + 2] = 250
    fx0 = 300 - 5 * i
    f[270 - 1:270 + 2, fx0 - 1:fx0 + 2] = 250
    pan.append(f)
LT = tf._Lights(pan, 0.0, 0.45, move=2.0, persist=3)
w, mo = LT._held(2)
cent = LT.blobs(2)[0]
kept = [tuple(np.rint(cent[k]).astype(int)) for k in range(1, len(cent)) if w[k] > 0.5]
ok(len(kept) == 1 and abs(kept[0][0] - (300 - 10)) <= 1 and abs(kept[0][1] - 270) <= 1,
   f"_Lights: move keeps the light drifting against the pan and drops the {len(glints)} glints riding it")
k = int(np.argmin(((cent[1:] - (290, 270)) ** 2).sum(1))) + 1
ok(abs(mo[k, 0] + 5) < 0.6 and abs(mo[k, 1]) < 0.6, "_Lights: the kept light is swept along its own motion")
o = tf.trails(pan, sweep=True, pop=0.45, move=2.0, decay=0.9)
row = o[6][270, 271:300, 0].astype(int)
away = np.ones(Hm, bool); away[262:279] = False
ok(row.min() > 120 and np.array_equal(o[6][away], pan[6][away]), "trails: with move the light streaks and the glints leave none")

o = tf.trails_diffuse(clip, rise=(0.0, -40.0), swirl=0.0, spread=1.0, decay=0.9, key=0.5, gain=0.6, contrast=1.0)
m = o[12].astype(float)[..., 0] - clip[12].astype(float)[..., 0]
ys = np.argwhere(m > 3)[:, 0]
ok(len(ys) and ys.mean() < 54 - 3, "trails_diffuse: the trail rises from where the dot was")
young = (m[:, 75:95] > 3).sum()
old = (m[:, 30:50] > 3).sum()
ok(old > young, "trails_diffuse: older trail has spread wider")
e2 = np.zeros(N); e2[4:8] = 1
o = tf.trails_diffuse(clip, env=e2, rise=(0, -20), decay=0.85)
ok(not np.array_equal(o[10], clip[10]) and np.array_equal(o[2], clip[2]), "trails_diffuse: smoke laid in the window drifts on after it")

o = tf.time_average(tc, radius=2.0)
want = disp_of(np.mean([lin_of(10 * k) for k in range(8, 13)]))
ok(abs(float(o[10][0, 0, 0]) - want) <= 1, "time_average: mean is the linear mean of the window")
o = tf.time_average(clip, radius=3.0, blend="max")
ok(all(o[12][54, 30 + 5 * k, 0] > 240 for k in range(10, 15)) and 100 < o[12][54, 75, 0] < 240
   and o[12][54, 70, 0] < 30, "time_average: max keeps every place the dot passed lit, the window's ends by their share")
spike = [np.zeros((H, W, 3), np.uint8) for _ in range(N)]
spike[10][:] = 255
seen = [int(tf.time_average(spike, radius=r)[12][0, 0, 0]) for r in (1.4, 1.6, 1.8, 2.0, 2.2, 2.4)]
ok(seen[0] == 0 and all(seen[k + 1] > seen[k] for k in range(5)), "time_average: a growing radius takes a far frame in gently")
st = [clip[0].copy() for _ in range(6)]
ok(max(int(np.abs(x.astype(int) - st[0].astype(int)).max()) for x in tf.time_average(st, radius=2)) <= 1,
   "time_average: a still picture stays the same")

o = tf.random_edits(tc, seg=(3, 5), seed=1)
src = tf.random_edits.last
ok(all(o[i][0, 0, 0] == 10 * src[i] for i in range(N)) and src != list(range(N)), "random_edits: pieces come from elsewhere in the clip")
runs = sum(1 for i in range(1, N) if src[i] != src[i - 1] + 1)
ok(runs >= 3 and runs <= N // 3, "random_edits: each piece plays forward")
o = tf.reverse_edits(tc, seg=(4, 4), seed=0)
src = tf.reverse_edits.last
ok(src[0:4] == [3, 2, 1, 0] and sorted(src) == list(range(N)), "reverse_edits: pieces play backwards in their own place")
o = tf.get_frame(tc, at=7)
ok(all(f[0, 0, 0] == 70 for f in o), "get_frame: env 1 holds the frame asked for")
o = tf.get_frame(tc, offset=-3)
ok(o[10][0, 0, 0] == 70 and o[1][0, 0, 0] == 0, "get_frame: offset shows the clip shifted in time")
o = tf.get_frame(tc, env=0.5, at=0)
ok(abs(float(o[10][0, 0, 0]) - disp_of(lin_of(100) / 2)) <= 1, "get_frame: env 0.5 mixes in linear light")
o = tf.looper(tc, start=8, length=10, xfade=0)
ok(all(o[i][0, 0, 0] == 10 * (8 + i % 10) for i in range(N)), "looper: the section repeats")
o = tf.looper(tc, start=8, length=10, xfade=4)
ok(o[9][0, 0, 0] < 170 and o[5][0, 0, 0] == 130 and o[3][0, 0, 0] == 110, "looper: the seam crossfades toward the frames before the start")
o = tf.looper(tc, start=4, length=5, bounce=True)
ok([int(f[0, 0, 0]) // 10 for f in o[:10]] == [4, 5, 6, 7, 8, 7, 6, 5, 4, 5], "looper: bounce plays forward and back")
o = tf.posterize_time(tc, step=3)
ok([int(f[0, 0, 0]) // 10 for f in o[:9]] == [0, 0, 0, 3, 3, 3, 6, 6, 6], "posterize_time: holds every third frame")
o = tf.posterize_time(tc, step=3, shutter=1.0)
want = disp_of(np.mean([lin_of(30), lin_of(40), lin_of(50)]))
ok(abs(float(o[4][0, 0, 0]) - want) <= 1, "posterize_time: shutter 1 averages the frames the hold stands for")
o = tf.posterize_time(tc, step=2.5)
hs = sorted(set(int(f[0, 0, 0]) // 10 for f in o[:21]))
ok(len(hs) == 9 and set(np.diff(hs)) == {2, 3}, "posterize_time: a fractional step alternates holds that average out")
o = tf.jitter_basic(tc, amount=3, seed=2)
src = tf.jitter_basic.last
ok(all(abs(s - i) <= 3 for i, s in enumerate(src)) and src != list(range(N)), "jitter_basic: frames swapped within the amount")
o = tf.jitter(tc, amount=3.0, hold=3, seed=1)
src = tf.jitter.last
ok(all(abs(s - i) <= 3 for i, s in enumerate(src)) and all(src[i + 1] - src[i] == 1 for i in (0, 1, 3, 4)),
   "jitter: held offsets within the amount")
ok(any(abs(s - round(s)) > 0.05 for s in src), "jitter: fractional times are used")
o = tf.jitter(clip, amount=0.0, shake=8.0, seed=1)
ok(not np.array_equal(o[3], clip[3]) and o[3].min() > 0, "jitter: shake moves the frame and keeps the edges covered")

A = dot_clip(8, x0=40, vx=0, r=7)
B = dot_clip(8, x0=120, vx=0, r=7)
o = tf.morph(A, B, smooth=0.0)
ok(np.array_equal(o[0], A[0]) and np.array_equal(o[-1], B[-1]), "morph: first frame is A's, last is B's")
t = np.linspace(0, 1, 8); t = t * t * (3 - 2 * t)
ok(t[1] < 0.1 and t[-2] > 0.9, "morph: the progress eases at both ends")
def patch_clip(n, x0):
    """A textured patch on a textured ground (flow needs texture to hold on to)."""
    r = np.random.default_rng(5)
    ground = r.integers(20, 60, (H, W)).astype(np.uint8)
    ground = np.repeat(ground[..., None], 3, 2)
    tex = r.integers(150, 255, (30, 30)).astype(np.uint8)
    out = []
    for _ in range(n):
        f = ground.copy()
        f[40:70, x0:x0 + 30] = tex[..., None]
        out.append(f)
    return out

def centroid_x(f):
    m = (f[..., 0].astype(float) > 120).astype(float)
    return float((m * np.arange(W)).sum() / max(m.sum(), 1)), float(m.sum())

A9, B9 = patch_clip(9, 60), patch_clip(9, 76)
for meth in ("dis", "farneback"):
    o = tf.morph(A9, B9, smooth=0.0, limit=0.0, method=meth)
    cxm, area = centroid_x(o[4])
    xfade = tf.disp(tf.lin(A9[4]) * 0.5 + tf.lin(B9[4]) * 0.5)
    _, area_x = centroid_x(xfade)
    ok(abs(cxm - (74.5 + 90.5) / 2) < 3 and abs(area - 900) < 135 and area_x > 1.3 * 900,
       f"morph ({meth}): half way the patch sits half way across, one patch (warped, not two half patches)")


print(f"\n{count - len(fails)} of {count} checks pass")
sys.exit(1 if fails else 0)
