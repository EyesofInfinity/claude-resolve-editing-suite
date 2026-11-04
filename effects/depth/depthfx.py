"""Develop Depth: effects driven by a depth map, built from what a lens and the air do.

A DCTL sees one picture, so these are renderers like Time FX: the picture and Resolve 21's own AI depth map
(depth_pass.py renders it, near white) go in, frame by frame, on the GPU with torch when there is one.

- defocus: a real lens's depth of field. Every point spreads into the shape of the aperture by its distance from the
  focus plane; far planes are filled behind what covers them, so a sharp subject keeps no dark rim; near planes
  spread over what is behind them. Bright points are lifted before the blur (8-bit footage clips its lights) and
  pressed back after, so a light becomes a bright disc and a dark leaf a soft shadow.
- zblur: the same planes with a Gaussian spread: depth blur with no lens shape.
- haze: single scattering in air (Koschmieder): the far picture fades toward the air's own colour, blue a little
  faster than red, and lights are seen through the air with their glow spread around them.
- zglow: a glow of the picture's own lights, held to a range of depth.
- depth_wipe: a transition that peels the outgoing shot away from the camera outward (or from the far plane in).

Pictures are HxWx3 uint8 Rec.709 (gamma 2.4 display values); depth is HxW float 0 (far) to 1 (near). Light is
mixed in linear. Amount 0 returns the input exactly. MIT License.
"""
import math

import numpy as np
import torch
import torch.nn.functional as F

DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
GAMMA = 2.4
LUMA = (0.2126, 0.7152, 0.0722)
RADII = [0.0, 0.75, 1.5, 2.25, 3.0, 4.0, 5.0, 6.25, 7.75, 9.5, 11.5, 14.0, 17.0, 20.5, 24.5, 29.0, 34.5, 41.0, 48.5,
         57.0, 67.0, 78.0, 90.0]

def lin(u8):
    """uint8 HxWx3 -> linear CHW float on the device."""
    t = torch.from_numpy(np.ascontiguousarray(u8)).to(DEV).permute(2, 0, 1).float() / 255.0
    return t.clamp(0, 1) ** GAMMA

def disp(t):
    """linear CHW -> uint8 HxWx3."""
    v = t.clamp(0, 1) ** (1.0 / GAMMA)
    return (v * 255.0 + 0.5).clamp(0, 255).byte().permute(1, 2, 0).cpu().numpy()

def dep(d):
    return torch.from_numpy(np.ascontiguousarray(d, dtype=np.float32)).to(DEV).clamp(0, 1)

def luma(t):
    return LUMA[0] * t[0] + LUMA[1] * t[1] + LUMA[2] * t[2]

def smoothstep(a, b, x):
    u = ((x - a) / (b - a)).clamp(0, 1)
    return u * u * (3 - 2 * u)

KNEE = 0.6

def lift(t, boost, knee=KNEE):
    """Linear light with only its near-clipped part expanded (u = (y - knee) / (1 - knee) -> u / (1 - c u)), so a
    clipped light spreads as the bright thing it was while white snow and sky stay what they are. press() undoes it
    exactly."""
    if boost <= 0:
        return t
    c = min(0.985, boost / (1.0 + boost))
    u = ((t - knee) / (1 - knee)).clamp(0, 1)
    return torch.where(t > knee, knee + (1 - knee) * u / (1 - c * u), t)

def press(t, boost, knee=KNEE):
    if boost <= 0:
        return t
    c = min(0.985, boost / (1.0 + boost))
    u = ((t - knee) / (1 - knee)).clamp(min=0)
    return torch.where(t > knee, knee + (1 - knee) * u / (1 + c * u), t)

def aperture(r, blades=0, rotation=0.0, roundness=1.0, rim=0.0, squeeze=1.0, gauss=False):
    """The spread of one point at radius r px: an aperture of `blades` straight blades (0 = round), its corners
    rounded by `roundness`, brighter toward its rim by `rim` (an over-corrected lens), squeezed in height by `squeeze`
    (an anamorphic oval taller than wide is squeeze < 1). gauss: a Gaussian of the same spread. Sums to 1."""
    if r < 0.5:
        k = torch.zeros(1, 1, device=DEV)
        k[0, 0] = 1.0
        return k
    R = int(math.ceil(r / min(1.0, squeeze) + 2)) if not gauss else int(math.ceil(r * 1.6 + 2))
    y, x = torch.meshgrid(torch.arange(-R, R + 1, device=DEV, dtype=torch.float32),
                          torch.arange(-R, R + 1, device=DEV, dtype=torch.float32), indexing="ij")
    if gauss:
        s = max(r / 2.0, 0.3)
        k = torch.exp(-(x * x + (y * squeeze) ** 2) / (2 * s * s))
        return k / k.sum()
    k = torch.zeros_like(x)
    for sy in range(4):
        for sx in range(4):
            px = x + (sx + 0.5) / 4 - 0.5
            py = (y + (sy + 0.5) / 4 - 0.5) * squeeze
            rho = torch.sqrt(px * px + py * py)
            if blades >= 3:
                a = torch.atan2(py, px) - math.radians(rotation)
                seg = 2 * math.pi / blades
                a = torch.remainder(a, seg) - seg / 2
                poly = math.cos(math.pi / blades) / torch.cos(a)
                rho = rho / (poly + (1 - poly) * roundness)
            inside = (rho <= r).float()
            w = 1.0 + rim * smoothstep(0.55 * r, r, rho)
            k += inside * w
    return k / k.sum()

class Conv:
    """Convolution by FFT for one frame size, kernels cached by their arguments."""

    def __init__(self, h, w, pad):
        self.h, self.w, self.pad = h, w, pad
        self.H, self.W = h + 2 * pad, w + 2 * pad
        self.cache = {}

    def kernel(self, args):
        if args not in self.cache:
            k = aperture(*args)
            K = torch.zeros(self.H, self.W, device=DEV)
            n = k.shape[0] // 2
            K[:k.shape[0], :k.shape[1]] = k
            K = torch.roll(K, shifts=(-n, -n), dims=(0, 1))
            self.cache[args] = (torch.fft.rfft2(K), n)
        return self.cache[args]

    def __call__(self, stack, args):
        """stack: C x h x w. Edges are mirrored, so the frame's edge does not darken."""
        if args[0] < 0.5:
            return stack
        Kf, n = self.kernel(args)
        if n >= self.pad:
            raise ValueError(f"radius {args[0]} needs a pad over {n}")
        p = F.pad(stack[None], (self.pad,) * 4, mode="reflect")[0]
        out = torch.fft.irfft2(torch.fft.rfft2(p) * Kf, s=(self.H, self.W))
        return out[:, self.pad:self.pad + self.h, self.pad:self.pad + self.w]

_convs = {}

def conv_for(h, w, rmax, squeeze=1.0, gauss=False):
    pad = int(math.ceil(rmax / min(1.0, squeeze) * (1.6 if gauss else 1.0) + 4))
    pad = min(pad, h - 1, w - 1)
    key = (h, w, pad)
    if key not in _convs:
        _convs.clear()
        _convs[key] = Conv(h, w, pad)
    return _convs[key]

def box(x, r):
    """Mean over a (2r+1) square, edges replicated; x: H x W. A direct local mean: summed areas in float32 lose
    the local variance over a 1080 frame (it went negative, the guided filter divided by almost nothing and
    single pixels blew up into specks the encoder made into blocks)."""
    p = F.pad(x[None, None], (r, r, r, r), mode="replicate")
    return F.avg_pool2d(p, 2 * r + 1, 1)[0, 0]

def despeckle(depth, k=5):
    """A k x k median of the depth: the AI map tags single glints and pits as near or far (water glints and
    rock pits stayed clear inside haze as specks), and a median drops them while keeping edges."""
    h, w = depth.shape
    p = F.unfold(F.pad(depth[None, None], (k // 2,) * 4, mode="replicate"), k)
    return p.median(dim=1).values.view(h, w)

def islands_out(depth, r=3):
    """An opening then a closing (r px): islands of depth smaller than 2r+1 px go to their surroundings (water
    glints and rock pits kept their clear colour inside haze as specks after the median). For haze only: it would
    send a thin in-focus twig to the backdrop's depth in defocus."""
    mx = lambda x: F.max_pool2d(x[None, None], 2 * r + 1, 1, r)[0, 0]
    mn = lambda x: -F.max_pool2d(-x[None, None], 2 * r + 1, 1, r)[0, 0]
    return mn(mx(mx(mn(depth))))

def refine(depth, guide, r=4, eps=4e-4):
    """The depth's edges moved onto the picture's edges (a guided filter, He 2010): the AI map is softer than the
    picture, and a blur that changes where the picture does not leaves a halo."""
    g = guide
    mg, md = box(g, r), box(depth, r)
    cov = box(g * depth, r) - mg * md
    var = box(g * g, r) - mg * mg
    a = cov / (var.clamp(min=0) + eps)
    b = md - a * mg
    return (box(a, r) * g + box(b, r)).clamp(0, 1)

def grow_near(depth, r=2):
    """Near depth spread r px outward (a max filter): the refined map leaves a subject's edge pixels between its
    depth and the backdrop's, and a blur that half takes them reads as fur on an in-focus edge (the trunk)."""
    if r <= 0:
        return depth
    return F.max_pool2d(depth[None, None], 2 * r + 1, 1, r)[0, 0]

def focus_at(depth, x=0.5, y=0.5, size=0.04):
    """The depth at a point of the frame (x, y from 0 to 1): the median of a small window."""
    h, w = depth.shape
    r = max(2, int(size * h))
    cy, cx = int(y * (h - 1)), int(x * (w - 1))
    win = depth[max(0, cy - r):cy + r + 1, max(0, cx - r):cx + r + 1]
    return float(win.median())

def fill(img, m):
    """img where m is 1, spread into the rest by push-pull (a pyramid of masked means): each hole takes the colour
    of what surrounds it, nearest first."""
    if float(m.min()) >= 1:
        return img
    cs, ws = [img * m], [m[None]]
    while min(cs[-1].shape[-2:]) > 4:
        cs.append(F.avg_pool2d(cs[-1][None], 2, ceil_mode=True)[0])
        ws.append(F.avg_pool2d(ws[-1][None], 2, ceil_mode=True)[0])
    w = ws[-1].clamp(min=1e-6)
    col = torch.where(ws[-1] > 1e-6, cs[-1] / w, img.mean(dim=(1, 2), keepdim=True).expand_as(cs[-1]))
    for lv in range(len(cs) - 2, -1, -1):
        up = F.interpolate(col[None], size=cs[lv].shape[-2:], mode="bilinear", align_corners=False)[0]
        col = cs[lv] + up * (1 - ws[lv]).clamp(min=0)
    return col

def _planes(r):
    """Each pixel's share of each plane radius: a pixel between two radii is split between them."""
    radii = torch.tensor(RADII, device=DEV)
    rr = r.clamp(0, RADII[-1])
    i = torch.searchsorted(radii, rr.contiguous(), right=True).clamp(1, len(RADII) - 1) - 1
    lo, hi = radii[i], radii[i + 1]
    t = ((rr - lo) / (hi - lo)).clamp(0, 1)
    return i, t

def defocus(img, depth, focus=0.5, aperture_px=20.0, blades=0, rotation=0.0, roundness=0.4, rim=0.15,
            squeeze=1.0, boost=3.0, gauss=False, near_scale=1.0, far_smooth=12.0, amount=1.0):
    """img: linear CHW; depth: HxW (near 1). The blur radius at 1080 is aperture_px * |depth - focus|; planes in
    front of focus are spread by near_scale times as much. Returns linear CHW."""
    if amount <= 0 or aperture_px <= 0:
        return img
    _, h, w = img.shape
    if far_smooth > 0:
        soft = torch.minimum(depth, gblur(depth, far_smooth * h / 1080.0))
        depth = torch.where(depth < focus, torch.minimum(soft, torch.full_like(depth, focus)), depth)
    s = (depth - focus) * (aperture_px * amount * h / 1080.0)
    s = torch.where(s > 0, s * near_scale, s)
    r = s.abs()
    rmax = float(r.max())
    if rmax < 0.5:
        return img
    used = list(range(0, min(len(RADII), int(np.searchsorted(RADII, rmax)) + 1)))
    conv = conv_for(h, w, RADII[used[-1]], squeeze, gauss)
    src = lift(img, 0.0 if gauss else boost)
    i, t = _planes(r)
    far, near = (s <= 0).float(), (s > 0).float()
    shape = lambda k: (RADII[k], blades, rotation, roundness, rim, squeeze, gauss)

    def share(k, side):
        return side * (torch.where(i == k, 1 - t, 0.0) + torch.where(i == k - 1, t, 0.0))

    acc = fill(src, far)
    nearer = near.clone()
    masks = {k: share(k, far) for k in used}
    for k in used:
        nearer = nearer + masks[k]
    for k in reversed(used):
        m = masks[k]
        nearer = nearer - m
        if float(m.max()) <= 0:
            continue
        out = conv(torch.cat([src * m, m[None]], 0), shape(k))
        c, a = out[:3], out[3].clamp(min=0)
        col = torch.where(a > 1e-3, c / a.clamp(min=1e-3), acc)
        alpha = (a + nearer + m).clamp(0, 1)
        acc = col * alpha + acc * (1 - alpha)
    nc = torch.zeros_like(src)
    na = torch.zeros_like(depth)
    for k in used:
        m = share(k, near)
        if float(m.max()) <= 0:
            continue
        out = conv(torch.cat([src * m, m[None]], 0), shape(k))
        nc, na = nc + out[:3], na + out[3].clamp(min=0)
    res = nc / na.clamp(min=1.0) + acc * (1 - na.clamp(0, 1))
    return press(res, 0.0 if gauss else boost)

def _mirror(v, r, dim):
    """v padded by r on both sides of dim, edges mirrored (the reflect pad). torch's reflect pad must be under the
    size; past it the mirror carries on (the edge-mirrored signal repeats every 2 (n - 1) samples), so a glow wider than
    a quarter-size frame still runs (zglow size 2.6 grow 2 and haze glow_size 0.35 crashed on an 803-row
    picture). Under the size it is torch's own pad, bit for bit as before."""
    n = v.shape[dim]
    if r < n:
        pad = (r, r, 0, 0) if dim == 3 else (0, 0, r, r)
        return F.pad(v, pad, mode="reflect")
    i = torch.arange(-r, n + r, device=v.device)
    if n == 1:
        i = torch.zeros_like(i)
    else:
        p = 2 * (n - 1)
        i = torch.remainder(i, p)
        i = torch.where(i < n, i, p - i)
    return torch.index_select(v, dim, i)

def gblur(t, sigma):
    """A Gaussian blur of CHW (or HW) by two passes, edges mirrored."""
    if sigma < 0.3:
        return t
    r = int(math.ceil(sigma * 3))
    x = torch.arange(-r, r + 1, device=DEV, dtype=torch.float32)
    g = torch.exp(-x * x / (2 * sigma * sigma))
    g = g / g.sum()
    two = t.dim() == 2
    v = (t[None] if two else t)[:, None]
    v = F.conv2d(_mirror(v, r, 3), g.view(1, 1, 1, -1))
    v = F.conv2d(_mirror(v, r, 2), g.view(1, 1, -1, 1))
    v = v[:, 0]
    return v[0] if two else v

def down_blur(t, sigma):
    """A wide Gaussian blur done at a quarter size (glow and air need no fine detail)."""
    if sigma < 6:
        return gblur(t, sigma)
    f = 4
    two = t.dim() == 2
    v = (t[None] if two else t)[None]
    h, w = v.shape[-2:]
    s = F.avg_pool2d(v, f, ceil_mode=True)[0]
    s = gblur(s, sigma / f)
    s = F.interpolate(s[None], size=(h, w), mode="bilinear", align_corners=False)[0]
    return s[0] if two else s

def air_colour(img, depth, frac=0.08):
    """The colour of the air: the ambient light of the far scene. Of the farthest pixels, the mean of those between
    the 55th and 80th percentile of brightness, so a moon or a sun in the far set does not light the whole sky (
    the plain mean turned a night sky grey) while a pale horizon still makes pale air; a quarter of its saturation
    taken off."""
    d = depth.flatten()
    n = max(64, int(frac * d.numel()))
    idx = torch.topk(-d, n).indices
    px = img.reshape(3, -1)[:, idx]
    y = LUMA[0] * px[0] + LUMA[1] * px[1] + LUMA[2] * px[2]
    order = torch.argsort(y)
    band = order[int(0.55 * n):max(int(0.55 * n) + 1, int(0.80 * n))]
    c = px[:, band].mean(1)
    yc = LUMA[0] * c[0] + LUMA[1] * c[1] + LUMA[2] * c[2]
    return 0.75 * c + 0.25 * yc

def haze(img, depth, density=0.5, colour=None, blue=0.3, start=0.3, curve=1.5, glow=0.25, glow_size=0.12,
         brightness=1.0, linear=False, end=1.0, amount=1.0):
    """Air between the camera and each point. Distance runs from `start` (no air nearer) to the far plane, shaped by
    `curve`; transmission exp(-3 density distance) per channel, blue (`blue`) thinned faster. The air's colour is the
    scene's own far colour unless given (linear RGB), times `brightness`; the picture's lights glow through it
    (`glow`, spread `glow_size` of the height). linear: transmission falls in a straight line from start to end."""
    if amount <= 0 or density <= 0:
        return img
    _, h, w = img.shape
    z = ((1.0 - depth - start) / max(1e-4, 1.0 - start)).clamp(0, 1) ** curve
    if colour is None:
        colour = air_colour(img, depth)
    colour = torch.as_tensor(colour, device=DEV, dtype=torch.float32).view(3, 1, 1) * brightness
    beta = torch.tensor([1 - 0.15 * blue, 1 - 0.05 * blue, 1 + 0.15 * blue], device=DEV).view(3, 1, 1)
    if linear:
        zz = ((1.0 - depth - start) / max(1e-4, end - start)).clamp(0, 1)
        t = (1 - zz * min(1.0, density) * beta).clamp(0, 1)
    else:
        t = torch.exp(-3.0 * density * beta * z)
    t = 1 - amount * (1 - t)
    lights = img * smoothstep(0.45, 1.0, luma(img))
    airlight = colour + glow * down_blur(lights, glow_size * h)
    return img * t + airlight * (1 - t)

def depth_weight(depth, where="far", at=0.5, width=0.25):
    """Where in depth an effect lives: far (beyond `at`), near (nearer than `at`) or a band around `at`."""
    if where == "far":
        return smoothstep(at + width, at - width, depth)
    if where == "near":
        return smoothstep(at - width, at + width, depth)
    return torch.exp(-((depth - at) / max(1e-3, width)) ** 2)

def zglow(img, depth, amount=1.0, threshold=0.55, knee=0.3, size=1.0, where="far", at=0.4, width=0.25,
          tint=(1.0, 1.0, 1.0), grow=1.0):
    """The picture's own lights glowing where the depth says: a light is what passes a soft threshold; its glow
    falls off as a lens's does (four widths, the wide ones weak). grow: lights farther away glow wider (seen
    through more air), by up to this factor."""
    if amount <= 0:
        return img
    _, h, w = img.shape
    wgt = depth_weight(depth, where, at, width)
    src = img * smoothstep(threshold, threshold + knee, luma(img)) * wgt
    tint = torch.as_tensor(tint, device=DEV, dtype=torch.float32).view(3, 1, 1)
    g = torch.zeros_like(img)
    for frac, wt in ((0.004, 0.40), (0.012, 0.30), (0.035, 0.20), (0.08, 0.10)):
        near_g = down_blur(src, frac * h * size)
        if grow > 1.0:
            far_g = down_blur(src, frac * h * size * grow)
            mixw = (1 - depth).clamp(0, 1)
            near_g = near_g * (1 - mixw) + far_g * mixw / grow
        g = g + wt * near_g
    return img + amount * g * tint

def ease(p):
    p = min(1.0, max(0.0, p))
    return p * p * p * (p * (6 * p - 15) + 10)

def depth_wipe(a, b, depth_a, p, soft=0.12, far_first=False, blur=8.0, depth_b=None, rows=None):
    """a to b at progress p (0 to 1, eased): b shows first where a is nearest (far_first: farthest), the border
    sweeping through a's depth with a soft edge `soft` wide; a softens (blur px at 1080) just before it gives way,
    as a plane leaving focus. Exactly a at 0 and b at 1. rows (r0, r1): where a's picture is, when a carries bars;
    the blur reads only those rows (it drew the bars into the picture's edge rows)."""
    if p <= 0:
        return a
    if p >= 1:
        return b
    e = ease(p)
    d = depth_a if not far_first else 1 - depth_a
    if depth_b is not None:
        db = depth_b if not far_first else 1 - depth_b
        d = torch.maximum(d, db * e)
    thr = 1 + soft - e * (1 + 2 * soft)
    m = smoothstep(thr - soft, thr + soft, d)
    if blur > 0:
        _, h, w = a.shape
        edge = smoothstep(thr - 3 * soft, thr - soft, d) * (1 - m)
        if rows is None:
            ab = gblur(a, blur * h / 1080.0)
        else:
            r0, r1 = rows
            ab = a.clone()
            ab[:, r0:r1] = gblur(a[:, r0:r1], blur * h / 1080.0)
        a = a + (ab - a) * edge[None] * math.sin(math.pi * e)
    return a * (1 - m) + b * m
