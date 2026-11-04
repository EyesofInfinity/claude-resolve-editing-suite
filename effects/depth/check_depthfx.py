"""Checks of Develop Depth on synthetic pictures: each would fail if the effect did the wrong thing.
usage: python -I check_depthfx.py
"""
import math
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import depthfx as dx

H, W = 270, 480
rng = np.random.default_rng(7)
results = []

def check(name, ok, detail=""):
    results.append(ok)
    print(("ok   " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))

def texture(seed=1, lo=0.1, hi=0.8):
    r = np.random.default_rng(seed)
    base = r.random((H // 6 + 1, W // 6 + 1, 3))
    big = np.kron(base, np.ones((6, 6, 1)))[:H, :W]
    return (255 * (lo + (hi - lo) * big)).astype(np.uint8)

def L(u8):
    return dx.lin(u8)

def D(a):
    return dx.dep(a)

def u8(t):
    return dx.disp(t).astype(np.int32)

img = texture()
depth_ramp = np.tile(np.linspace(0, 1, W, dtype=np.float32), (H, 1))

for name, fn, kw in (("defocus", dx.defocus, {"amount": 0}), ("defocus aperture 0", dx.defocus, {"aperture_px": 0}),
                     ("haze", dx.haze, {"amount": 0}), ("haze density 0", dx.haze, {"density": 0}),
                     ("zglow", dx.zglow, {"amount": 0})):
    out = fn(L(img), D(depth_ramp), **kw)
    check(f"{name}: off returns the input exactly", bool(torch.equal(out, L(img))))

flat = np.full((H, W), 0.4, np.float32)
out = u8(dx.defocus(L(img), D(flat), focus=0.4, aperture_px=40))
check("defocus: a scene all at focus is unchanged", int(np.abs(out - img).max()) <= 1, f"largest {np.abs(out - img).max()}")

grey = np.full((H, W, 3), 140, np.uint8)
steps = (np.floor(np.tile(np.linspace(0, 6, W, endpoint=False), (H, 1))) / 6).astype(np.float32)
steps[H // 3:2 * H // 3, W // 3:W // 2] = 0.95
for gauss in (False, True):
    out = u8(dx.defocus(L(grey), D(steps), focus=0.5, aperture_px=60, gauss=gauss))
    check(f"defocus{' (gauss)' if gauss else ''}: flat grey through stepped depth stays flat",
          int(np.abs(out - 140).max()) <= 1, f"range {out.min()} to {out.max()}")

bg = texture(3)
subj = np.zeros((H, W), np.float32)
subj[90:180, 180:300] = 0.7
scene = bg.copy()
scene[90:180, 180:300] = 200
out = dx.disp(dx.defocus(L(scene), D(subj), focus=0.7, aperture_px=30, boost=0)).astype(np.float64)
inside = np.abs(out[95:175, 185:295] - scene[95:175, 185:295]).max()
check("defocus: an in-focus subject keeps every pixel", inside <= 1, f"largest {inside}")
ring = np.concatenate([out[90:180, 160:178].ravel(), out[90:180, 302:320].ravel()])
far_ref = dx.disp(dx.defocus(L(bg), D(np.zeros((H, W), np.float32)), focus=0.7, aperture_px=30, boost=0))
ref = np.concatenate([far_ref[90:180, 160:178].ravel(), far_ref[90:180, 302:320].ravel()]).astype(np.float64)
check("defocus: no dark rim round a sharp subject", abs(ring.mean() - ref.mean()) < 4,
      f"rim {ring.mean():.1f}, backdrop alone {ref.mean():.1f}")

near = np.zeros((H, W), np.float32) + 0.3
near[100:170, 200:280] = 1.0
scene2 = bg.copy()
scene2[100:170, 200:280] = 30
out = dx.disp(dx.defocus(L(scene2), D(near), focus=0.3, aperture_px=40, boost=0)).astype(np.int32)
check("defocus: the scene far from a blurred near object is untouched",
      int(np.abs(out[:, :120] - scene2[:, :120]).max()) <= 1)
spread = out[135, 195:200].mean() < scene2[135, 195:200].astype(np.int32).mean() - 5
check("defocus: a near object's blur spreads over what is behind it", bool(spread))

pt = np.full((H, W, 3), 20, np.uint8)
pt[135, 240] = 255
out = dx.defocus(L(pt), D(np.zeros((H, W), np.float32)), focus=0.6, aperture_px=40, rim=0)
ys, xs = np.nonzero(dx.disp(out)[..., 1] > 22)
r_meas = (xs.max() - xs.min() + 1) / 2
r_want = 40 * 0.6 * H / 1080
check("defocus: a far point light becomes a disc of the expected radius", abs(r_meas - r_want) <= 1.5,
      f"radius {r_meas:.1f}, expected {r_want:.1f}")
out6 = dx.disp(dx.defocus(L(pt), D(np.zeros((H, W), np.float32)), focus=0.6, aperture_px=40, blades=6, roundness=0, rim=0))
ys6, xs6 = np.nonzero(out6[..., 1] > 22)
check("defocus: six blades give a hexagon (fewer pixels than the circle)", len(xs6) < 0.95 * len(xs),
      f"{len(xs6)} against {len(xs)}")
lit = dx.disp(dx.defocus(L(pt), D(np.zeros((H, W), np.float32)), focus=0.6, aperture_px=40, rim=0, boost=3))
dim = dx.disp(dx.defocus(L(pt), D(np.zeros((H, W), np.float32)), focus=0.6, aperture_px=40, rim=0, boost=0))
check("defocus: a clipped light is lifted before the blur (brighter disc)", lit[135, 240, 1] > dim[135, 240, 1] + 3,
      f"{lit[135, 240, 1]} against {dim[135, 240, 1]}")

tex = texture(5)
bright = texture(5, 0.1, 1.0)
zero = D(np.zeros((H, W), np.float32))
for name, tx_ in (("texture", tex), ("texture reaching white", bright)):
    out = dx.defocus(L(tx_), zero, focus=0.8, aperture_px=40, boost=0)
    m0, m1 = float(L(tx_).mean()), float(out.mean())
    check(f"defocus: mean light kept within 1% (boost 0, {name})", abs(m1 - m0) / m0 < 0.01, f"{m0:.4f} to {m1:.4f}")
lb = L(bright)
over = float((lb > dx.KNEE).float().mean())
out = dx.defocus(lb, zero, focus=0.8, aperture_px=40, boost=3)
m0, m1, ml = float(lb.mean()), float(out.mean()), float(dx.lift(lb, 3).mean())
check("defocus: boost 3 brightens a texture's lights, by no more than the lift adds", over > 0.1 and m1 > 1.05 * m0 and m1 <= ml * 1.002,
      f"{over:.2f} over the knee; mean {m0:.4f} to {m1:.4f}, the lifted source {ml:.4f}")
fl_hi = L(np.full((H, W, 3), 240, np.uint8))
out = dx.defocus(fl_hi, zero, focus=0.8, aperture_px=40, boost=3)
err = float((out - fl_hi).abs().max())
check("defocus: a flat field over the knee comes back as itself through boost 3", float(fl_hi.min()) > dx.KNEE and err < 1e-4,
      f"{float(fl_hi.min()):.3f} linear, largest change {err:.1e}")

t = torch.linspace(0, 1, 1001, device=dx.DEV)
check("lift and press undo each other", float((dx.press(dx.lift(t, 3), 3) - t).abs().max()) < 1e-5)

img_h = texture(9)
d_h = np.zeros((H, W), np.float32)
d_h[:, W // 2:] = 1.0
out = dx.haze(L(img_h), D(d_h), density=2.0, colour=(0.5, 0.5, 0.5), glow=0)
farpart = out[:, :, :W // 2]
check("haze: the near half is untouched", float((out[:, :, W // 2:] - L(img_h)[:, :, W // 2:]).abs().max()) < 1e-6)
check("haze: the far half lies close to the air", float((farpart - 0.5).abs().mean()) < 0.02,
      f"mean distance {float((farpart - 0.5).abs().mean()):.4f}")
o_r = dx.haze(L(grey), D(np.full((H, W), 0.5, np.float32)), density=0.5, colour=(1, 1, 1), glow=0, blue=0.6)
check("haze: blue thins faster than red (white air reads cool first)", float(o_r[2].mean()) > float(o_r[0].mean()))
dk = dx.haze(L(np.full((H, W, 3), 10, np.uint8)), D(d_h), density=2.0, glow=0)
check("haze: a dark scene's own air keeps it dark (no grey veil)", float(dk.max()) <= float(L(np.full((1, 1, 3), 10, np.uint8)).max()) + 1e-6)

lights = np.full((H, W, 3), 30, np.uint8)
lights[58:63, 118:123] = 255
lights[58:63, 358:363] = 255
dg = np.zeros((H, W), np.float32)
dg[:, W // 2:] = 1.0
out = dx.disp(dx.zglow(L(lights), D(dg), amount=1.0, where="far", at=0.5, width=0.1)).astype(np.int32)
check("zglow: a far light glows", out[60, 135, 1] > 31, f"{out[60, 135, 1]}")
check("zglow: a near light does not", out[60, 375, 1] <= 31, f"{out[60, 375, 1]}")
check("zglow: dark areas far from any light stay put", int(np.abs(out[200:, :] - 30).max()) <= 1)

a_, b_ = L(texture(11)), L(texture(12))
dw = D(depth_ramp)
check("depth_wipe: a at 0, b at 1", bool(torch.equal(dx.depth_wipe(a_, b_, dw, 0.0), a_)) and
      bool(torch.equal(dx.depth_wipe(a_, b_, dw, 1.0), b_)))
c02 = float((dx.depth_wipe(a_, b_, dw, 0.02) - a_).abs().mean())
c98 = float((dx.depth_wipe(a_, b_, dw, 0.98) - b_).abs().mean())
check("depth_wipe: eases (mean change under 0.005 at 0.02 and 0.98)", c02 < 0.005 and c98 < 0.005,
      f"{c02:.5f}, {c98:.5f}")
mid = dx.depth_wipe(a_, b_, dw, 0.5, blur=0)
near_b = float((mid[:, :, -40:] - b_[:, :, -40:]).abs().mean())
far_a = float((mid[:, :, :40] - a_[:, :, :40]).abs().mean())
check("depth_wipe: the near side turns first", near_b < 0.01 and far_a < 0.01, f"{near_b:.4f}, {far_a:.4f}")

H2, W2 = 803, 1920
img2 = dx.lin(np.full((H2, W2, 3), 128, np.uint8))
img2[:, 380:420, 900:960] = 1.0
d2 = dx.dep(np.tile(np.linspace(0, 1, W2, dtype=np.float32), (H2, 1)))
for name, fn, kw in (("zglow size 2.6 grow 2", dx.zglow, {"size": 2.6, "grow": 2.0}),
                     ("haze glow_size 0.35", dx.haze, {"glow_size": 0.35})):
    try:
        o = fn(img2, d2, **kw)
        ok_, info = bool(torch.isfinite(o).all()), f"range {float(o.min()):.3f} to {float(o.max()):.3f}"
    except Exception as e:
        ok_, info = False, f"{type(e).__name__}: {str(e)[:80]}"
    check(f"{name} runs on an 803-row picture", ok_, info)
fl = torch.full((3, 40, 60), 0.3, device=dx.DEV)
try:
    fe = float((dx.gblur(fl, 50.0) - 0.3).abs().max())
except Exception as e:
    fe = float("inf")
check("gblur wider than the frame keeps a flat field flat", fe < 1e-6, f"{fe:.1e}")

def gblur_before(t, sigma):
    """gblur as it was, for the bit-for-bit check below."""
    if sigma < 0.3:
        return t
    r = int(math.ceil(sigma * 3))
    x = torch.arange(-r, r + 1, device=dx.DEV, dtype=torch.float32)
    g = torch.exp(-x * x / (2 * sigma * sigma))
    g = g / g.sum()
    two = t.dim() == 2
    v = (t[None] if two else t)[:, None]
    v = F.conv2d(F.pad(v, (r, r, 0, 0), mode="reflect"), g.view(1, 1, 1, -1))
    v = F.conv2d(F.pad(v, (0, 0, r, r), mode="reflect"), g.view(1, 1, -1, 1))
    v = v[:, 0]
    return v[0] if two else v

import torch.nn.functional as F
tx = L(texture(13))
worst = 0.0
for sg in (0.5, 1.0, 3.0, 12.0, 44.0, 89.0):
    worst = max(worst, float((dx.gblur(tx, sg) - gblur_before(tx, sg)).abs().max()),
                float((dx.gblur(tx[1], sg) - gblur_before(tx[1], sg)).abs().max()))
check("gblur unchanged where its mirror fitted the frame (bit for bit)", worst == 0.0, f"largest {worst:.1e}")

try:
    import importlib.util
    _sp = importlib.util.spec_from_file_location("depth_apply", os.path.join(os.path.dirname(os.path.abspath(__file__)), "apply.py"))
    dap = importlib.util.module_from_spec(_sp)
    _sp.loader.exec_module(dap)
    y0b, y1b = 30, 240
    fa_ = texture(21, 0.5, 0.9)
    fb_ = texture(22, 0.5, 0.9)
    for f_ in (fa_, fb_):
        f_[:y0b] = 0
        f_[y1b:] = 0
    da_ = depth_ramp.copy()
    db_ = depth_ramp[:, ::-1].copy()
    got = dap.wipe_frame(fa_, fb_, da_, db_, 0.5, (y0b, y1b), (y0b, y1b), refine=0, blur=8.0)
    ref = dx.disp(dx.depth_wipe(L(fa_[y0b:y1b]), L(fb_[y0b:y1b]), dx.despeckle(D(da_[y0b:y1b])), 0.5,
                                depth_b=dx.despeckle(D(db_[y0b:y1b])), blur=8.0)).astype(np.int32)
    old = dx.disp(dx.depth_wipe(L(fa_), L(fb_), dx.despeckle(D(da_)), 0.5, depth_b=dx.despeckle(D(db_)), blur=8.0)).astype(np.int32)
    edge = int(np.abs(got[y0b:y0b + 4].astype(np.int32) - ref[:4]).max())
    bars = int(max(got[:y0b].max(), got[y1b:].max()))
    same = dx.disp(dx.depth_wipe(L(fa_[y0b:y1b]), L(fb_[y0b:y1b]), dx.despeckle(D(da_[y0b:y1b])), 0.5,
                                 depth_b=dx.despeckle(D(db_[y0b:y1b])), blur=8.0 * H / (y1b - y0b))).astype(np.int32)
    old_dark = float((same[:4] - old[y0b:y0b + 4]).mean())
    ok_w = edge == 0 and bars == 0 and np.array_equal(got[y0b:y1b].astype(np.int32), ref)
    info_w = f"edge rows off by {edge}, bars up to {bars}; the whole-frame wipe darkened the edge rows by {old_dark:.1f} codes"
    try:
        dap.run_wipe(["a.mp4", "o.mp4", "--fx", "depth_wipe", "--b", "b.mp4", "--strength", "0.5"], "a.mp4", "o.mp4", 0.0,
                     24.0, 18, {}, 0.0)
        refused = "no message"
    except SystemExit as e:
        refused = str(e.code)
    except Exception as e:
        refused = f"{type(e).__name__}"
    ok_r = "strength" in refused and "transition" in refused
except Exception as e:
    ok_w, ok_r, info_w, refused = False, False, f"{type(e).__name__}: {str(e)[:80]}", ""
check("depth_wipe inside the picture: bars black, edge rows as on the picture alone", ok_w, info_w)
check("depth_wipe refuses --strength, --in, --out", ok_r, refused[:90])

def _paths_under(env, local_json):
    import importlib.util
    import json
    import tempfile
    keys = ("DEVELOP_MATERIAL_ROOT", "DEVELOP_CATALOG", "DEVELOP_LOCAL")
    old = {k: os.environ.get(k) for k in keys}
    td = tempfile.mkdtemp()
    try:
        for k in keys:
            os.environ.pop(k, None)
        os.environ.update(env)
        os.environ["DEVELOP_LOCAL"] = os.path.join(td, "local.json")
        if local_json is not None:
            json.dump(local_json, open(os.environ["DEVELOP_LOCAL"], "w"))
        here = os.path.dirname(os.path.abspath(__file__))
        sp = importlib.util.spec_from_file_location("depth_pass_paths", os.path.join(here, "depth_pass.py"))
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        return dap.ta_catalog(), m.CATALOG
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

try:
    tail = ("catalog.csv",)
    moved = _paths_under({"DEVELOP_MATERIAL_ROOT": "D:/footage"}, {"material_root": "E:/local"})
    local = _paths_under({}, {"material_root": "E:/local"})
    direct = _paths_under({}, {"catalog": "E:/index.csv"})
    none = _paths_under({}, None)
    want_m, want_l = os.path.join("D:/footage", *tail), os.path.join("E:/local", *tail)
    ok_p = (moved == (want_m, want_m) and local == (want_l, want_l) and direct == ("E:/index.csv",) * 2
            and none == (None, None))
    info_p = f"env {moved[0]}; local {local[0]}; catalog {direct[0]}; neither {none[0]}"
except Exception as e:
    ok_p, info_p = False, f"{type(e).__name__}: {str(e)[:80]}"
check("the footage index: the environment, then develop.local.json, else none (apply.py, depth_pass.py)", ok_p, info_p)

o1 = dx.defocus(L(img), D(depth_ramp), focus=0.5, aperture_px=30)
o2 = dx.defocus(L(img), D(depth_ramp), focus=0.5, aperture_px=30)
check("defocus is deterministic", float((o1 - o2).abs().max()) < 1e-5)

print(f"{sum(results)} of {len(results)} checks pass")
sys.exit(0 if all(results) else 1)
