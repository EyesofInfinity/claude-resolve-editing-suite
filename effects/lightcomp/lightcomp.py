"""Develop Light Comp: generated light composited into the plate, as one real source in the scene seen through
the plate's own lens, film and air.

Generated light can look like a sticker. A sticker is light laid over the picture: in front of everything, sharper, cleaner and brighter
than anything the camera saw, lighting nothing. Here the light is placed in the scene instead:

- depth: the light stands at a depth (`at`); what the depth pass puts nearer covers it, and it is spread as everything
  at that depth is spread in this plate (its softness measured from the plate's own edges at that depth, by the
  re-blur ratio of Zhuo and Sim 2011; past about a pixel the spread is the lens's aperture, Develop Depth's planes).
- it lights the scene: surfaces near it in the frame and in depth are brightened by the light times their own colour
  (multiplied, so black stays black and a dark trunk takes little), and the edges of things standing in front of it
  that face it take a rim.
- the plate's optics: the light enters through the plate's own tone (its black floor stays, its scale is the plate's
  black to white, and it shoulders into the plate's own clipped white per channel, so no light is brighter or whiter
  than the plate's own highlights); the plate's colour cast tints it; the plate's grain is laid over what it adds, at
  the strength the plate's own grain has at the new brightness, the same size and the same colour correlation.
- air: in a hazy plate (the dark channel of its far scene) the light reaches the camera dimmed by the air between and
  the rest scattered round it in a wide glow.

A lens light (`kind="lens"`: a flare, a glare, a glow) happens inside the lens, not in the scene: it is not covered
pixel by pixel and lights nothing, but it dims as its source is covered, and takes the plate's tone, cast, sensor
softness and grain.

Pictures are HxWx3 uint8 Rec.709 (gamma 2.4 display values); depth HxW float 0 (far) to 1 (near); the light layer is
linear CHW. Every mix is in linear light. Amount 0 returns the plate exactly. MIT License.
"""
import math
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "depth"))
import depthfx as dx

DEV = dx.DEV
LUMA = dx.LUMA
smoothstep = dx.smoothstep

def luma(t):
    return dx.luma(t)

def lin_f(disp):
    """float display values (CHW tensor) -> linear."""
    return disp.clamp(0, 1) ** dx.GAMMA

def disp_f(t):
    return t.clamp(0, 1) ** (1.0 / dx.GAMMA)

def sobel(y):
    """Gradient (gx, gy) of HxW by the Sobel pair, divided by 8 so a unit ramp reads 1 a pixel."""
    k = torch.tensor([[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]], device=y.device) / 8.0
    p = F.pad(y[None, None], (1, 1, 1, 1), mode="replicate")
    gx = F.conv2d(p, k.view(1, 1, 3, 3))[0, 0]
    gy = F.conv2d(p, k.t().contiguous().view(1, 1, 3, 3))[0, 0]
    return gx, gy

SOBEL_FLOOR = 0.74
REBLUR = 1.5
NO_GRAIN = 1e-5

def edge_blur(y):
    """Blur sigma (px) at the plate's edges by the re-blur ratio: an edge blurred by s has a gradient peak C / s; blurred
    again by s0 it has C / sqrt(s^2 + s0^2), so s = s0 / sqrt(R^2 - 1). Returns (sigma map, edge mask)."""
    gx, gy = sobel(y)
    g1 = torch.sqrt(gx * gx + gy * gy)
    bx, by = sobel(dx.gblur(y, REBLUR))
    g2 = torch.sqrt(bx * bx + by * by)
    peak = (g1 >= F.max_pool2d(g1[None, None], 5, 1, 2)[0, 0] - 1e-6)
    edge = peak & (g1 > 0.05)
    R = (g1 / g2.clamp(min=1e-5)).clamp(min=1.0005)
    s = REBLUR / torch.sqrt(R * R - 1)
    s = torch.sqrt((s * s - SOBEL_FLOOR ** 2).clamp(min=0.0))
    return s, edge

class Plate:
    """What a clip's picture says about its camera, measured once over a few of its frames so it holds still through
    the clip: tone (black, white), colour cast, softness by depth, grain by brightness, haze."""

    def __init__(self, frames, depths, bins=10):
        """frames: list of HxWx3 uint8 (the picture only, no bars); depths: matching HxW float (near 1)."""
        L = [dx.lin(f) for f in frames]
        D = [dx.dep(d) for d in depths]
        allp = torch.cat([l.reshape(3, -1)[:, ::7] for l in L], 1)
        self.black = torch.quantile(allp, 0.001, dim=1)
        self.white = torch.quantile(allp, 0.9995, dim=1).clamp(min=0.2)
        y = LUMA[0] * allp[0] + LUMA[1] * allp[1] + LUMA[2] * allp[2]
        lo, hi = torch.quantile(y, 0.3), torch.quantile(y, 0.97)
        sel = (y > lo) & (y < hi)
        m = allp[:, sel].mean(1) if int(sel.sum()) > 100 else allp.mean(1)
        self.cast = m / max(1e-4, float(LUMA[0] * m[0] + LUMA[1] * m[1] + LUMA[2] * m[2]))
        edges = [[] for _ in range(bins)]
        for l, d in zip(L, D):
            yd = disp_f(luma(l))
            s, e = edge_blur(yd)
            b = (d * bins).long().clamp(0, bins - 1)
            for k in range(bins):
                v = s[e & (b == k)]
                if v.numel():
                    edges[k].append(v)
        med = []
        for k in range(bins):
            v = torch.cat(edges[k]) if edges[k] else torch.zeros(0, device=DEV)
            med.append(float(v.median()) if v.numel() >= 40 else float("nan"))
        med = np.array(med)
        ok = ~np.isnan(med)
        cz = (np.arange(bins) + 0.5) / bins
        self.blur_z = cz
        self.blur_s = np.interp(cz, cz[ok], med[ok]) if ok.any() else np.full(bins, 0.6)
        self.sharp = float(np.min(self.blur_s))
        nb = 12
        acc = [[] for _ in range(nb)]
        lag, cr = [], []
        for l in L:
            d = disp_f(l)
            res = d - dx.gblur(d, 1.0)
            yb = luma(dx.gblur(d, 2.0))
            gx, gy = sobel(yb)
            flat = torch.sqrt(gx * gx + gy * gy) < 0.004
            ry = luma(res)
            B = 16
            hb, wb = ry.shape[0] // B * B, ry.shape[1] // B * B
            pool = lambda t: F.avg_pool2d(t[None, None, :hb, :wb], B)[0, 0].flatten()
            m1, m2 = pool(ry), pool(ry * ry)
            bstd = torch.sqrt((m2 - m1 * m1).clamp(min=0))
            bflat = pool(flat.float()) > 0.9
            bl = (pool(yb) * nb).long().clamp(0, nb - 1)
            for k in range(nb):
                v = bstd[bflat & (bl == k)]
                if v.numel():
                    acc[k].append(v)
            fm = flat[:, :-1] & flat[:, 1:]
            if int(fm.sum()) > 500:
                a, c = ry[:, :-1][fm], ry[:, 1:][fm]
                if float(a.std()) > NO_GRAIN and float(c.std()) > NO_GRAIN:
                    lag.append(float(((a - a.mean()) * (c - c.mean())).mean() / (a.std() * c.std() + 1e-9)))
                chans = [res[i][flat] for i in range(3)]
                pairs = [torch.corrcoef(torch.stack([chans[i], chans[j]]))[0, 1] for i, j in ((0, 1), (1, 2))
                         if float(chans[i].std()) > NO_GRAIN and float(chans[j].std()) > NO_GRAIN]
                pairs = [v for v in pairs if np.isfinite(float(v))]
                if len(pairs) == 2:
                    cr.append(float(0.5 * (pairs[0] + pairs[1])))
                elif pairs:
                    cr.append(float(pairs[0]))
        sig = []
        for k in range(nb):
            v = torch.cat(acc[k]) if acc[k] else torch.zeros(0, device=DEV)
            sig.append(float(torch.quantile(v, 0.25)) if v.numel() >= 12 else float("nan"))
        sig = np.array(sig)
        ok = ~np.isnan(sig)
        cz = (np.arange(nb) + 0.5) / nb
        self.noise_y = cz
        self.noise_res = np.interp(cz, cz[ok], sig[ok]) if ok.any() else np.zeros(nb)
        self.noise_res = np.where(cz > float(disp_f(self.white.max())), 0.0, self.noise_res)
        self.lag = float(np.median(lag)) if lag else 0.0
        self.rho = float(np.clip(np.median(cr), 0, 1)) if cr else 0.8
        self.grain_size, self.res_gain = _grain_fit(self.lag)
        hz = []
        for l, d in zip(L, D):
            dd = disp_f(l)
            dc = -F.max_pool2d(-dd.min(0).values[None, None], 15, 1, 7)[0, 0]
            far = d <= torch.quantile(d.flatten()[::5], 0.15)
            air = disp_f(dx.air_colour(l, d)).min()
            b0 = float(disp_f(self.black).min())
            v = float((dc[far].median() - b0) / max(0.05, float(air) - b0))
            if np.isfinite(v):
                hz.append(v)
        self.haze_raw = float(np.median(hz)) if hz else 0.0
        self.haze = float(smoothstep(torch.tensor(0.25), torch.tensor(0.75), torch.tensor(self.haze_raw)))

    def blur_at(self, z):
        return float(np.interp(z, self.blur_z, self.blur_s))

    def grain_at(self, y):
        """The grain's strength (display, as a Gaussian field of unit std before the residual) at display luma y."""
        yy = y.clamp(0, 1)
        t = torch.tensor(self.noise_res, device=y.device, dtype=torch.float32)
        pos = (yy * len(self.noise_res) - 0.5).clamp(0, len(self.noise_res) - 1)
        i0 = pos.floor().long().clamp(0, len(self.noise_res) - 1)
        i1 = (i0 + 1).clamp(max=len(self.noise_res) - 1)
        f = pos - i0.float()
        return (t[i0] * (1 - f) + t[i1] * f) / self.res_gain

    def summary(self):
        return {"black": [round(float(v), 4) for v in self.black], "white": [round(float(v), 3) for v in self.white],
                "cast": [round(float(v), 3) for v in self.cast], "sharp_px": round(self.sharp, 2),
                "blur_by_depth": [round(float(v), 2) for v in self.blur_s], "grain_size": self.grain_size,
                "grain_lag1": round(self.lag, 3), "grain_rho": round(self.rho, 3),
                "grain_res": [round(float(v), 4) for v in self.noise_res], "haze": round(self.haze, 3),
                "haze_raw": round(self.haze_raw, 3)}

_GRAIN_FITS = {}

def _grain_field(h, w, size, gen):
    n = torch.randn(1, h, w, device=DEV, generator=gen)
    if size > 0.05:
        n = dx.gblur(n, size)
    return n[0] / n.std().clamp(min=1e-6)

def _grain_fit(lag):
    """The grain's blur size whose 1 px residual has the plate's lag-1 correlation, and that residual's std for a unit
    field (so the plate's residual std converts to the field's own)."""
    if not _GRAIN_FITS:
        g = torch.Generator(device=DEV).manual_seed(99)
        for s in (0.0, 0.3, 0.45, 0.6, 0.75, 0.9, 1.1, 1.4, 1.8):
            n = _grain_field(256, 256, s, g)[None]
            r = (n - dx.gblur(n, 1.0))[0]
            a, c = r[:, :-1].flatten(), r[:, 1:].flatten()
            _GRAIN_FITS[s] = (float(((a - a.mean()) * (c - c.mean())).mean() / (a.std() * c.std())), float(r.std()))
    best = min(_GRAIN_FITS, key=lambda s: abs(_GRAIN_FITS[s][0] - lag))
    return best, _GRAIN_FITS[best][1]

def grain(plate, h, w, frame, seed=0):
    """A unit grain field the size and colour correlation of the plate's, new each frame (deterministic)."""
    g = torch.Generator(device=DEV).manual_seed(int(seed) * 100003 + int(frame) * 7919 + 17)
    mono = _grain_field(h, w, plate.grain_size, g)
    ch = torch.stack([_grain_field(h, w, plate.grain_size, g) for _ in range(3)])
    a, b = math.sqrt(plate.rho), math.sqrt(1 - plate.rho)
    return a * mono[None] + b * ch

def shoulder(x, white, knee=0.7):
    """Identity below knee * white, then easing into white (per channel), never past it."""
    w = white.view(3, 1, 1)
    k = knee * w
    over = (x - k).clamp(min=0)
    return torch.where(x > k, k + (w - k) * (1 - torch.exp(-over / (w - k))), x)

def spread(E, h, scales, weights):
    return [wt * dx.down_blur(E, s * h) for s, wt in zip(scales, weights)]

def light_defocus(E, sigma, h, scale=None):
    """The light spread as everything at its depth is in this plate: a Gaussian under about a pixel and a half (the
    lens's own softness and the codec), the lens's aperture past it (a disc of radius 2 sigma, Develop Depth's
    planes, its near-clipped cores lifted so they open into discs).

    The lift reads 1.0 linear as clipped and holds everything above it there, so the aperture spreads the layer at its
    own scale (where 1.0 is the DCTL's clip) and the gain goes back on after: scale is what took it above that (the
    comp's gain times amount; None takes the layer's own peak). with the gain inside, gain 1.5 and 3 came
    out of the aperture the same, energy out/in 0.755 and 0.378."""
    if sigma < 0.3:
        return E
    if sigma <= 1.5:
        return dx.gblur(E, sigma * h / 1080.0)
    s = max(1.0, float(E.max()) if scale is None else float(scale))
    zero = torch.zeros(E.shape[1:], device=DEV)
    out = dx.defocus(E / s if s > 1.0 else E, zero, focus=1.0, aperture_px=2.0 * sigma, boost=2.0, far_smooth=0.0)
    return out * s if s > 1.0 else out

def visible(D, at, soft, ramp=0.0):
    """1 where the scene is behind the light's depth, 0 where it stands in front. at is the light's depth at the top of
    the frame; ramp adds to it toward the bottom (a beam from a rig high and far landing on a floor nearer)."""
    h, w = D.shape
    z = at + ramp * (torch.arange(h, device=DEV, dtype=torch.float32).view(h, 1) / h)
    return smoothstep(z + soft, z - soft, D), z

def confidence(P, h, reach=0.1):
    """Where the depth pass can be believed: within reach (of the height) of picture detail. The AI map invents depth
    in a featureless dark sky (the moonlit branches: a smooth bowl of depth over the night sky cut a laser off
    along an ellipse), and nothing there can cover a light or be lit by it."""
    y = disp_f(luma(P))
    m = dx.box(y, 3)
    sd = torch.sqrt((dx.box(y * y, 3) - m * m).clamp(min=0))
    tex = smoothstep(0.006, 0.02, sd)
    r = max(1, int(reach * h / 4))
    c = F.max_pool2d(F.avg_pool2d(tex[None, None], 4, ceil_mode=True), 2 * r + 1, 1, r)
    c = F.interpolate(c, size=y.shape, mode="bilinear", align_corners=False)[0, 0]
    return dx.down_blur(c[None], 0.05 * h)[0].clamp(0, 1)

def comp(plate_u8, D, E, pl, at=0.5, kind="scene", gain=1.0, spill=1.0, rim=1.0, reach=1.0, occlude=0.03,
         ramp=0.0, defocus_px=-1.0, cast=0.35, grain_amt=1.0, air=-1.0, ambient=0.0, knee=0.7, amount=1.0,
         frame=0, seed=0, parts=None):
    """plate_u8 HxWx3, D HxW tensor (near 1), E the light layer (linear CHW), pl a Plate. Returns HxWx3 uint8.
    at: the light's depth; defocus_px: its blur sigma at 1080 (-1: measured from the plate at that depth); air: the
    haze (-1: measured); ambient: stops on the plate outside the light (0 leaves it). parts: a dict filled with the
    layers for judging."""
    if amount <= 0 or gain <= 0:
        return plate_u8.copy()
    P = dx.lin(plate_u8)
    _, h, w = P.shape
    E = E * (gain * amount)
    cv = pl.cast.clamp(min=0.05) ** cast
    cv = cv / (LUMA[0] * cv[0] + LUMA[1] * cv[1] + LUMA[2] * cv[2])
    E = E * cv.view(3, 1, 1)
    scale = (pl.white - pl.black).clamp(0.4, 1.0).view(3, 1, 1)
    vis, z = visible(D, at, occlude, ramp)
    conf = confidence(P, h)
    rc = max(1, int(round(2.0 * h / 1080.0)))
    cover = F.max_pool2d((1 - vis)[None, None], 2 * rc + 1, 1, rc)
    cover = -F.max_pool2d(-cover, 2 * rc + 1, 1, rc)[0, 0]
    vis = dx.gblur(1 - cover * conf, 0.6 * h / 1080.0)
    lens = kind == "lens"
    haze = pl.haze if air < 0 else air
    if lens:
        sig = pl.sharp if defocus_px < 0 else defocus_px
        Ed = light_defocus(E, sig, h, gain * amount)
        y = dx.down_blur(luma(E)[None], 0.01 * h)[0]
        idx = int(torch.argmax(y))
        cy, cx = idx // w, idx % w
        r = max(2, int(0.012 * h))
        vl, _ = visible(D, at + occlude + 0.01, occlude)
        vl = 1 - (1 - vl) * conf
        vsrc = float(vl[max(0, cy - r):cy + r + 1, max(0, cx - r):cx + r + 1].mean())
        add = Ed * vsrc
        if haze > 0:
            t = math.exp(-1.2 * haze)
            add = add * t + (1 - t) * vsrc * sum(spread(E, h, (0.02, 0.06, 0.15), (0.5, 0.3, 0.2)))
        Y = P * (2.0 ** ambient) + scale * add
        I = torch.zeros_like(P)
        R = torch.zeros_like(P)
    else:
        sig = pl.blur_at(at) if defocus_px < 0 else defocus_px
        beta = -math.log(max(0.05, 1 - 0.6 * haze))
        t = math.exp(-beta * (1 - at))
        Ed = light_defocus(E, sig, h, gain * amount) * t
        Es = (1 - t) * sum(spread(E, h, (0.01, 0.03, 0.08), (0.5, 0.3, 0.2))) if haze > 0 else torch.zeros_like(E)
        vis_s = dx.down_blur(vis[None], 0.03 * h)[0]
        dz = D - z
        front = smoothstep(0.0, occlude * 2 + 0.02, dz)
        I = torch.zeros_like(P)
        for s, wt, dw in ((0.012, 0.35, 0.05), (0.035, 0.30, 0.10), (0.09, 0.22, 0.18), (0.22, 0.13, 0.35)):
            I = I + wt * dx.down_blur(E, s * h) * torch.exp(-(dz / (dw * reach)) ** 2)
        I = I * ((1 - 0.9 * front) * conf * (spill * 6.0))[None]
        Dg = dx.gblur(D, 2.0 * h / 1080.0)
        r3 = max(1, int(round(3.0 * h / 1080.0)))
        dmax = F.max_pool2d(D[None, None], 2 * r3 + 1, 1, r3)[0, 0]
        dmin = -F.max_pool2d(-D[None, None], 2 * r3 + 1, 1, r3)[0, 0]
        step = dmax - dmin
        nr = smoothstep(0.06, 0.15, step) * smoothstep(0.4, 0.8, (D - dmin) / step.clamp(min=1e-4))
        nr = dx.gblur(nr, 0.8 * h / 1080.0)
        gx, gy = sobel(Dg)
        nx, ny = -gx, -gy
        nn = torch.sqrt(nx * nx + ny * ny).clamp(min=1e-6)
        Iw = dx.down_blur(luma(E)[None], 0.05 * h)[0]
        lx, ly = sobel(Iw)
        ln = torch.sqrt(lx * lx + ly * ly).clamp(min=1e-9)
        facing = ((nx * lx + ny * ly) / (nn * ln)).clamp(min=0)
        near_l = smoothstep(-0.08, 0.02, dz)
        Ir = sum(spread(E, h, (0.012, 0.035, 0.09, 0.22), (0.35, 0.30, 0.22, 0.13)))
        R = Ir * (nr * near_l * (0.25 + 0.75 * facing))[None] * (rim * 4.0)
        Y = P * (2.0 ** ambient + I) + (P + 0.03) * R + scale * (Ed * vis[None] + Es * vis_s[None])
    out = P + shoulder(Y, pl.white, knee) - shoulder(P, pl.white, knee)
    d0, d1 = disp_f(P), disp_f(out)
    da_ = disp_f(P + shoulder(P * (2.0 ** ambient), pl.white, knee) - shoulder(P, pl.white, knee)) if ambient != 0 else d0
    ya, y1 = luma(da_), luma(d1)
    kept = pl.grain_at(ya) * (y1.clamp(min=0.02) / ya.clamp(min=0.02)) ** -1.4
    extra = torch.sqrt((pl.grain_at(y1) ** 2 - kept ** 2).clamp(min=0))
    changed = smoothstep(0.0, 2.0 / 255, (d1 - da_).clamp(min=0).amax(0))
    n = grain(pl, h, w, frame, seed) * (extra * changed * grain_amt)[None]
    delta = (d1 - d0 + n) * 255.0
    top = torch.maximum(disp_f(pl.white).view(3, 1, 1) * 255.0, torch.from_numpy(plate_u8).to(DEV).permute(2, 0, 1).float())
    o = (torch.from_numpy(plate_u8).to(DEV).permute(2, 0, 1).float() + delta)
    o = torch.minimum(o, top).clamp(0, 255)
    o = torch.where(delta.abs() < 1e-4, torch.from_numpy(plate_u8).to(DEV).permute(2, 0, 1).float(), o)
    if parts is not None:
        parts.update({"vis": vis, "I": I, "R": R, "Ed": Ed, "sigma": sig, "t": None if lens else t})
    return (o + 0.5).floor().byte().permute(1, 2, 0).cpu().numpy()

def over(plate_u8, E, amount=1.0):
    """The sticker, for judging beside the comp: the same light added over the plate in linear, nothing else."""
    if amount <= 0:
        return plate_u8.copy()
    return dx.disp(dx.lin(plate_u8) + E * amount)
