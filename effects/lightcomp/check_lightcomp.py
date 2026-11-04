"""Checks of Develop Light Comp on synthetic pictures: each would fail if the comp did the wrong thing.
usage: python -I check_lightcomp.py
"""
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lightcomp as lc

dx = lc.dx
H, W = 270, 480
results = []

def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("ok   " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))

def texture(seed=1, lo=0.15, hi=0.7, noise=0.0):
    r = np.random.default_rng(seed)
    base = r.random((H // 6 + 1, W // 6 + 1, 3))
    big = np.kron(base, np.ones((6, 6, 1)))[:H, :W]
    v = lo + (hi - lo) * big + noise * r.standard_normal((H, W, 3))
    return np.clip(255 * v + 0.5, 0, 255).astype(np.uint8)

def flat(v):
    return np.full((H, W, 3), v, np.uint8)

def beam(y=135, width=2.0, level=0.8):
    yy = torch.arange(H, device=dx.DEV, dtype=torch.float32).view(H, 1).expand(H, W)
    b = level * torch.exp(-((yy - y) / width) ** 2)
    return torch.stack([b * 0.2, b, b * 0.6])

def spot(cx, cy, r=6.0, level=1.0):
    yy, xx = torch.meshgrid(torch.arange(H, device=dx.DEV, dtype=torch.float32),
                            torch.arange(W, device=dx.DEV, dtype=torch.float32), indexing="ij")
    s = level * torch.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (r * r))
    return torch.stack([s, s, s])

def depth_lr(near_left=0.9, far=0.1):
    d = np.full((H, W), far, np.float32)
    d[:, : W // 2] = near_left
    return d

def plate_of(img, d):
    return lc.Plate([img], [d])

def main():
    torch.manual_seed(0)
    tex = texture(1)
    d = depth_lr()
    pl = plate_of(tex, d)
    D = dx.dep(d)
    E = beam()

    o = lc.comp(tex, D, E, pl, amount=0.0)
    check("amount 0 returns the plate exactly", np.array_equal(o, tex))
    o = lc.comp(tex, D, E, pl, gain=0.0)
    check("gain 0 returns the plate exactly", np.array_equal(o, tex))
    o = lc.comp(tex, D, torch.zeros_like(E), pl, frame=3)
    check("no light returns the plate exactly", np.array_equal(o, tex), f"max diff {np.abs(o.astype(int) - tex).max()}")

    o = lc.comp(tex, D, E, pl, at=0.5, spill=0.0, rim=0.0, grain_amt=0.0).astype(int)
    band = slice(132, 139)
    dl = np.abs(o[band, 20:W // 2 - 20] - tex[band, 20:W // 2 - 20]).mean()
    dr = np.abs(o[band, W // 2 + 20:W - 20] - tex[band, W // 2 + 20:W - 20]).mean()
    check("nearer depth covers the light", dl < 0.3 and dr > 5, f"change behind the near half {dl:.2f}, in the open {dr:.2f}")
    o2 = lc.comp(tex, dx.dep(np.full((H, W), 0.1, np.float32)), E, pl, at=0.5, spill=0.0, rim=0.0, grain_amt=0.0).astype(int)
    dl2 = np.abs(o2[band, 20:W // 2 - 20] - tex[band, 20:W // 2 - 20]).mean()
    check("the same light with nothing in front shows on both halves", dl2 > 5, f"{dl2:.2f}")
    sky = flat(12)
    psky = plate_of(sky, d)
    o3 = lc.comp(sky, D, E, psky, at=0.5, spill=0.0, rim=0.0, grain_amt=0.0).astype(int)
    dl3 = np.abs(o3[band, 20:W // 2 - 20] - 12).mean()
    check("depth over a featureless field covers nothing", dl3 > 8, f"{dl3:.2f}")

    dim = texture(2, 0.1, 0.8)
    pd = plate_of(dim, np.full((H, W), 0.1, np.float32))
    o = lc.comp(dim, dx.dep(np.full((H, W), 0.1, np.float32)), E * 40.0, pd, at=0.5, frame=1)
    top = np.maximum(np.round(255 * lc.disp_f(pd.white).cpu().numpy()).astype(int)[None, None], dim.astype(int))
    over_by = int((o.astype(int) - top).max())
    check("no light brighter than the plate's clip", over_by <= 0, f"plate white {np.round(255 * lc.disp_f(pd.white).cpu().numpy())}, over by {over_by}")
    check("a hot light reaches the plate's white", int(o[135].max()) >= int(top.min()) - 2, f"{int(o[135].max())}")

    lv = 0.12
    a1 = int(round(255 * lv ** (1 / 2.4)))
    a2 = int(round(255 * (2 * lv) ** (1 / 2.4)))
    img = np.zeros((H, W, 3), np.uint8)
    img[:, :W // 3] = 0
    img[:, W // 3:2 * W // 3] = a1
    img[:, 2 * W // 3:] = a2
    img[::7, ::7] = 40
    img[-12:, -60:] = 255
    dd = np.full((H, W), 0.5, np.float32)
    pa = plate_of(img, dd)
    Es = spot(W // 2, 10, 8, 3.0) + spot(W // 6, 10, 8, 3.0) + spot(5 * W // 6, 10, 8, 3.0)
    o = lc.comp(img, dx.dep(dd), Es, pa, at=0.5, rim=0.0, grain_amt=0.0, spill=1.0, knee=0.99, air=0.0)
    o_ns = lc.comp(img, dx.dep(dd), Es, pa, at=0.5, rim=0.0, grain_amt=0.0, spill=0.0, knee=0.99, air=0.0)
    lo = dx.lin(o)
    li = dx.lin(o_ns)
    rows = slice(40, 70)
    m1 = (lo[1, rows, W // 3 + 10:2 * W // 3 - 10] - li[1, rows, W // 3 + 10:2 * W // 3 - 10])
    m2 = (lo[1, rows, 2 * W // 3 + 10:W - 10] - li[1, rows, 2 * W // 3 + 10:W - 10])
    sel1 = img[rows, W // 3 + 10:2 * W // 3 - 10, 1] == a1
    sel2 = img[rows, 2 * W // 3 + 10:W - 10, 1] == a2
    r = float(m2[torch.from_numpy(sel2).to(dx.DEV)].mean() / m1[torch.from_numpy(sel1).to(dx.DEV)].mean().clamp(min=1e-9))
    blk = img[rows, 10:W // 3 - 10, 1] == 0
    g0 = int((o[rows, 10:W // 3 - 10].astype(int) - o_ns[rows, 10:W // 3 - 10])[blk].max())
    check("spill leaves black black", g0 == 0, f"brightest black pixel after {g0}")
    check("spill multiplies albedo (twice the surface, twice the gain)", 1.7 < r < 2.3, f"ratio {r:.2f}")

    dd2 = dd.copy()
    dd2[:, W // 3:2 * W // 3] = 0.05
    o4 = lc.comp(img, dx.dep(dd2), Es, plate_of(img, dd2), at=0.5, rim=0.0, grain_amt=0.0, knee=0.99, occlude=0.01)
    m1b = (dx.lin(o4)[1, rows, W // 3 + 10:2 * W // 3 - 10] - li[1, rows, W // 3 + 10:2 * W // 3 - 10])
    q = float(m1b[torch.from_numpy(sel1).to(dx.DEV)].mean() / m1[torch.from_numpy(sel1).to(dx.DEV)].mean())
    check("spill falls off in depth", q < 0.3, f"far surface gets {q:.2f} of the near one's light")

    disc = texture(4, 0.2, 0.4)
    yy, xx = np.mgrid[0:H, 0:W]
    inside = (xx - 240) ** 2 + (yy - 135) ** 2 < 60 ** 2
    dd3 = np.where(inside, 0.9, 0.1).astype(np.float32)
    El = spot(325, 135, 8, 6.0)
    pr = plate_of(disc, dd3)
    o = lc.comp(disc, dx.dep(dd3), El, pr, at=0.4, spill=0.0, rim=1.0, grain_amt=0.0).astype(int) - disc.astype(int)
    near_edge = o[125:145, 296:300].mean()
    far_edge = o[125:145, 180:184].mean()
    check("rim on the edge facing the light", near_edge > 0.5 and near_edge > 3 * max(far_edge, 0.1),
          f"facing {near_edge:.2f}, away {far_edge:.2f}")

    El2 = spot(120, 135, 5, 1.0) + 0.05 * spot(120, 135, 80, 1.0)
    pl_l = plate_of(tex, d)
    o_cov = lc.comp(tex, D, El2, pl_l, at=0.5, kind="lens", grain_amt=0.0).astype(int)
    o_open = lc.comp(tex, dx.dep(np.full((H, W), 0.1, np.float32)), El2, pl_l, at=0.5, kind="lens", grain_amt=0.0).astype(int)
    c1 = np.abs(o_cov - tex).mean()
    c2 = np.abs(o_open - tex).mean()
    check("a lens light whose source is covered is gone", c1 < 0.05 * c2 and c2 > 0.5, f"covered {c1:.3f}, open {c2:.3f}")

    base = texture(5, 0.1, 0.3)
    base[-12:, -60:] = 255
    dfar = np.full((H, W), 0.05, np.float32)
    pb = plate_of(base, dfar)
    Ep = spot(240, 135, 3, 1.0)
    clear = dx.lin(lc.comp(base, dx.dep(dfar), Ep, pb, at=0.2, air=0.0, spill=0.0, rim=0.0, grain_amt=0.0)) - dx.lin(base)
    hazy = dx.lin(lc.comp(base, dx.dep(dfar), Ep, pb, at=0.2, air=1.0, spill=0.0, rim=0.0, grain_amt=0.0)) - dx.lin(base)
    core = (slice(130, 141), slice(235, 246))
    ring = lambda t: float(t[:, 80:190, 140:340].sum() - t[:, 120:151, 225:256].sum())
    check("haze dims the core and spreads the light", float(hazy[:, core[0], core[1]].mean()) < 0.8 * float(clear[:, core[0], core[1]].mean())
          and ring(hazy) > 2 * max(ring(clear), 1e-6), f"core {float(hazy[:, core[0], core[1]].mean()):.3f} vs {float(clear[:, core[0], core[1]].mean()):.3f}")

    sig = 0.012
    gp = texture(6, 0.3, 0.32, 0.0).astype(np.float32) / 255.0
    rng = np.random.default_rng(3)
    gn = gp + sig * rng.standard_normal((H, W, 1))
    gimg = np.clip(255 * gn + 0.5, 0, 255).astype(np.uint8)
    gd = np.full((H, W), 0.3, np.float32)
    pg = plate_of(gimg, gd)
    est = float(pg.grain_at(torch.tensor([0.31], device=dx.DEV))[0])
    check("grain measured from the plate", 0.6 * sig < est < 1.5 * sig, f"true {sig}, measured {est:.4f}, size {pg.grain_size}")
    g2 = np.empty((H, W, 1))
    g2[:, :W // 2] = 0.2 + 0.004 * rng.standard_normal((H, W // 2, 1))
    g2[:, W // 2:] = 0.6 + 0.016 * rng.standard_normal((H, W - W // 2, 1))
    g2img = np.clip(255 * np.repeat(g2, 3, 2) + 0.5, 0, 255).astype(np.uint8)
    g2img[-12:, -60:] = 255
    pg2 = plate_of(g2img, gd)
    Ef = torch.zeros((3, H, W), device=dx.DEV)
    Ef[:, :, :W // 2] = 0.6 ** 2.4 - 0.2 ** 2.4
    o = lc.comp(g2img, dx.dep(gd), Ef, pg2, at=0.5, spill=0.0, rim=0.0, air=0.0, frame=5).astype(np.float32) / 255.0
    lit = o[20:-20, 20:W // 2 - 20, 1]
    bright = g2img[20:-20, W // 2 + 20:-20, 1].astype(np.float32) / 255.0
    sl, sb = float(lit.std()), float(bright.std())
    check("the light carries the plate's grain at the new brightness", 0.7 * sb < sl < 1.3 * sb and abs(lit.mean() - bright.mean()) < 0.03,
          f"lit {lit.mean():.3f} grain {sl:.4f}, the plate's bright half {bright.mean():.3f} grain {sb:.4f}")

    yy4, xx4 = np.mgrid[0:H * 4, 0:W * 4] / 4.0
    r4 = np.random.default_rng(1)
    big = np.zeros((H * 4, W * 4))
    for _ in range(40):
        cx, cy, rr = r4.uniform(0, W), r4.uniform(0, H), r4.uniform(6, 30)
        big[(xx4 - cx) ** 2 + (yy4 - cy) ** 2 < rr * rr] = r4.uniform(0.1, 0.9)
    sharp = torch.tensor(big.reshape(H, 4, W, 4).mean((1, 3)), dtype=torch.float32, device=dx.DEV)
    meas = []
    for s in (0.0, 1.0, 2.0, 3.0):
        t = dx.gblur(sharp, s) if s > 0 else sharp
        sg, e = lc.edge_blur(t)
        meas.append(float(sg[e].median()))
    check("edge softness measured (0, 1, 2, 3 px)", meas[0] < 0.4 and abs(meas[1] - 1) < 0.3 and abs(meas[2] - 2) < 0.35
          and abs(meas[3] - 3) < 0.45, ", ".join(f"{m:.2f}" for m in meas))
    soft = np.clip(dx.gblur(sharp, 2.0).cpu().numpy(), 0, 1)
    simg = np.repeat((255 * soft + 0.5).astype(np.uint8)[..., None], 3, 2)
    sd = np.full((H, W), 0.5, np.float32)
    ps = plate_of(simg, sd)
    check("the plate's softness at a depth", 1.4 < ps.blur_at(0.5) < 2.6, f"{ps.blur_at(0.5):.2f} (blurred by 2)")

    Eb = beam(135, 0.7, 1.0)
    o_s = lc.comp(simg, dx.dep(sd), Eb, ps, at=0.6, spill=0.0, rim=0.0, grain_amt=0.0, air=0.0)
    o_k = lc.comp(simg, dx.dep(sd), Eb, ps, at=0.6, spill=0.0, rim=0.0, grain_amt=0.0, air=0.0, defocus_px=0.0)
    w_s = (np.abs(o_s.astype(int) - simg)[..., 1] > 2).sum()
    w_k = (np.abs(o_k.astype(int) - simg)[..., 1] > 2).sum()
    check("the light takes the plate's softness at its depth", w_s > 1.3 * w_k, f"{w_s} px touched against {w_k} kept sharp")

    nt = np.clip(255 * (0.35 + 0.01 * np.random.default_rng(9).standard_normal((H, W, 3))) + 0.5, 0, 255).astype(np.uint8)
    nt[-12:, -60:] = 255
    pn = plate_of(nt, d)
    o1 = lc.comp(nt, D, E, pn, at=0.5, frame=7)
    o2 = lc.comp(nt, D, E, pn, at=0.5, frame=7)
    o3 = lc.comp(nt, D, E, pn, at=0.5, frame=8)
    o4 = lc.comp(tex, D, E, pl, at=0.5, frame=8)
    o5 = lc.comp(tex, D, E, pl, at=0.5, frame=7)
    check("a plate with no grain takes no grain", np.array_equal(o4, o5))
    check("the same frame twice is the same", np.array_equal(o1, o2))
    check("the grain is new each frame", not np.array_equal(o1, o3))

    warm = texture(7, 0.2, 0.6).astype(np.float32)
    warm[..., 2] *= 0.7
    warm = warm.astype(np.uint8)
    pw = plate_of(warm, np.full((H, W), 0.1, np.float32))
    Ew = spot(240, 135, 20, 0.3)
    o = dx.lin(lc.comp(warm, dx.dep(np.full((H, W), 0.1, np.float32)), Ew, pw, at=0.5, spill=0.0, rim=0.0, grain_amt=0.0)) - dx.lin(warm)
    c = o[:, 125:146, 230:251].mean((1, 2))
    check("the plate's cast tints a white light", float(c[2]) < 0.95 * float(c[0]), f"added r {float(c[0]):.3f} b {float(c[2]):.3f}")

    rb = np.random.default_rng(1)
    fr = []
    for k in range(5):
        if k == 0:
            f = np.zeros((H, W, 3), np.uint8)
        else:
            b6 = rb.random((H // 6 + 1, W // 6 + 1, 3))
            f = (255 * (0.1 + 0.7 * np.kron(b6, np.ones((6, 6, 1)))[:H, :W])).astype(np.uint8)
            f = np.clip(f.astype(int) + rb.integers(-3, 4, f.shape), 0, 255).astype(np.uint8)
        fr.append(f)
    dr_ = [np.tile(np.linspace(0, 1, W, dtype=np.float32), (H, 1)) for _ in fr]
    red = np.zeros((H, W, 3), np.uint8)
    red[..., 0] = np.clip(120 + rb.integers(-3, 4, (H, W)), 0, 255)
    for label, frs in (("a black frame", fr), ("a flat grey frame and a pure red one", [flat(90), red] + fr[1:4])):
        pk = lc.Plate(frs, dr_[:len(frs)])
        Ek = torch.zeros((3, H, W), device=dx.DEV)
        Ek[:, 100:110, 200:210] = 2.0
        ok_ = np.isfinite(pk.rho) and np.isfinite(pk.lag)
        o = lc.comp(fr[2], dx.dep(dr_[2]), Ek, pk, at=0.5)
        far_changed = int((o[:50, :100] != fr[2][:50, :100]).sum())
        check(f"a plate measured over {label} keeps a finite grain correlation and leaves the far picture alone",
              ok_ and far_changed == 0, f"rho {pk.rho}, lag {pk.lag}, far pixels changed {far_changed}")

    Eg = torch.zeros((3, H, W), device=dx.DEV)
    Eg[:, 130:133, 100:380] = 1.0
    Eg[:, 60:120, 40:80] = 0.9
    pz = plate_of(tex, np.full((H, W), 0.1, np.float32))
    for sg in (1.6, 3.0):
        eds = {}
        for g in (1.0, 1.5, 3.0):
            pt = {}
            lc.comp(tex, dx.dep(np.full((H, W), 0.1, np.float32)), Eg, pz, at=0.9, gain=g, defocus_px=sg, air=0.0,
                    spill=0.0, rim=0.0, grain_amt=0.0, cast=0.0, parts=pt)
            eds[g] = pt["Ed"]
        e_in = float(Eg.sum())
        ratio = [float(eds[g].sum()) / (g * e_in) for g in (1.0, 1.5, 3.0)]
        lin_err = float((eds[3.0] - 2.0 * eds[1.5]).abs().max() / eds[3.0].abs().max())
        check(f"the light keeps its gain through a {sg} px aperture (energy the same at gain 1, 1.5, 3)",
              max(ratio) - min(ratio) < 0.01 and lin_err < 1e-4,
              f"energy out/in {', '.join(f'{r:.3f}' for r in ratio)}; gain 3 against twice gain 1.5 {lin_err:.1e}")

    import tempfile
    import layers as lay
    keep = lay.CACHE
    try:
        with tempfile.TemporaryDirectory() as td:
            lay.CACHE = td
            a_ = lay.run_dctl(lay.LZ, {"lzMode": 0}, 5, None, None, (64, 36))
            b_ = lay.run_dctl(lay.LZ, {"lzMode": 0}, 5, None, None, (48, 36))
            ok_c, info_c = a_.shape == (36, 64, 3) and b_.shape == (36, 48, 3), f"{a_.shape}, {b_.shape}"
    except Exception as e:
        ok_c, info_c = False, f"{type(e).__name__}: {str(e)[:90]}"
    finally:
        lay.CACHE = keep
    check("the layer cache tells two frame sizes of a light over black apart", ok_c, info_c)

    n_ok = sum(results)
    print(f"{n_ok} of {len(results)} checks pass")
    sys.exit(0 if n_ok == len(results) else 1)

if __name__ == "__main__":
    main()
