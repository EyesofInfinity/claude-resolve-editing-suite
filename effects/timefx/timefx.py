"""Develop Time FX: effects made of time, rendered over a run of frames. A DCTL sees one frame, so these work on
the frame sequence itself, as the time glitches (effects/time/timeglitch.py) and the datamosh do.

Feedback (the picture fed back into itself, the way a camera pointed at its own monitor does):
  feedback(frames, env, zoom, turn, decay, hue, soft)
                         the output fed back each frame, zoomed and turned about a centre, and mixed by screen
  feedback_bubble(...)   the same loop seen through a glass sphere: the fed-back copy refracted by the ball
  feedback_distort(...)  the same loop pushed through a smooth noise field that drifts, so the echoes curl like heat
Time displacement:
  time_displace(frames, env, depth, matte)
                         each pixel taken from a frame offset in time by a matte: the picture's own luma, a ramp
                         (slit-scan) or a radial; fractional offsets interpolate between frames, so no bands step
Trails and the rest of time:
  trails(...)            echoes of the frames before, combined by lighten, screen or average, each echo darker
  trails_diffuse(...)    trails that drift and blur as they fade, like smoke rising off the bright parts
  time_average(...)      a window of frames averaged in linear light (a long exposure), or lightened (light painting)
  random_edits(...)      the clip cut into short pieces, some of them taken from elsewhere in the clip
  reverse_edits(...)     the clip cut into short pieces, some of them played backwards
  get_frame(...)         a frame from another moment mixed over the live picture (a held frame or a time offset)
  looper(...)            a section looped, its seam crossfaded so the loop runs on without a jump
  posterize_time(...)    the clip held to a lower frame rate; shutter blends each held frame from the ones it hides
  jitter_basic(...)      each frame swapped for one up to a few frames away
  jitter(...)            held, fractional time jitter, with a gate-weave shake of the frame if asked
Between two clips:
  morph(A, B, ...)       optical flow both ways (OpenCV DIS or Farneback), each clip warped toward the other and
                         crossfaded; the first frame is A's own and the last is B's own

frames: a list of HxWx3 uint8 Rec.709 gamma 2.4 arrays. Every function returns a new list of the same length (morph:
of len(A)). env and strength values may be one number or a list with one value per frame, so an effect can rise and
fall over a window. Light-like mixes happen in linear light (gamma 2.4). At env 0 the input frame comes back exactly.
MIT License.
"""
import math
import numpy as np
import cv2

_LUT = ((np.arange(256, dtype=np.float64) / 255.0) ** 2.4).astype(np.float32)
_LW = np.array([0.2126, 0.7152, 0.0722], np.float32)

def lin(f):
    """uint8 display picture to linear light, float32 0..1."""
    return _LUT[f]

def disp(x):
    """linear light back to a uint8 display picture."""
    return (np.power(np.clip(x, 0.0, 1.0), 1.0 / 2.4) * 255.0 + 0.5).astype(np.uint8)

def envelope(env, n):
    """One value per frame from a number or a sequence."""
    if np.isscalar(env):
        return np.full(n, float(env), np.float64)
    e = np.asarray(env, np.float64).ravel()
    if len(e) != n:
        raise ValueError(f"env has {len(e)} values for {n} frames")
    return e

def ramp_env(n, rise, fall, peak=1.0):
    """An envelope that rises over `rise` frames, holds, and falls over `fall` frames, eased (smoothstep)."""
    e = np.full(n, peak, np.float64)
    for i in range(n):
        if rise > 0 and i < rise:
            t = (i + 0.5) / rise
            e[i] = peak * t * t * (3 - 2 * t)
        if fall > 0 and i >= n - fall:
            t = (n - i - 0.5) / fall
            e[i] = min(e[i], peak * t * t * (3 - 2 * t))
    return e

def _smoothstep(a, b, x):
    t = np.clip((x - a) / max(b - a, 1e-6), 0.0, 1.0)
    return t * t * (3 - 2 * t)

def _luma_disp(f):
    return (f.astype(np.float32) @ _LW) / 255.0

def _hue_matrix(deg):
    """A turn of the hue about the grey axis (Rodrigues), in linear RGB."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    k = 1.0 / math.sqrt(3.0)
    K = np.array([[0, -k, k], [k, 0, -k], [-k, k, 0]], np.float64)
    M = np.eye(3) * c + s * K + (1 - c) * np.full((3, 3), 1.0 / 3.0)
    return M.astype(np.float32)

def _hue(x, deg):
    if abs(deg) < 1e-6:
        return x
    return np.maximum(x @ _hue_matrix(deg).T, 0.0)

def _screen(a, b):
    return 1.0 - (1.0 - a) * (1.0 - np.clip(b, 0.0, 1.0))

def _combine(cur, echo, blend):
    if blend == "screen":
        return _screen(cur, echo)
    if blend == "max":
        return np.maximum(cur, echo)
    if blend == "add":
        return np.minimum(cur + echo, 1.0)
    raise ValueError(f"blend {blend!r}: screen, max or add")

def _grid(H, W):
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
    return gx, gy

def _edge_window(H, W, px):
    """1 inside, falling smoothly to 0 over px at the frame's edge, so a fed-back copy never shows a hard border."""
    x = np.arange(W, dtype=np.float32)
    y = np.arange(H, dtype=np.float32)
    wx = _smoothstep(0.0, px, x) * _smoothstep(0.0, px, W - 1 - x)
    wy = _smoothstep(0.0, px, y) * _smoothstep(0.0, px, H - 1 - y)
    return (wy[:, None] * wx[None, :]).astype(np.float32)

def noise_field(H, W, t, scale=0.18, seed=0, comps=7):
    """A smooth two-component noise field (each a spread of 0.5 about 0, so mostly within -1..1), built from sine
    waves of random direction and frequency whose phases drift with t. scale: the largest feature as a share of the
    frame height. Exact at every pixel: each wave is split into products of a row and a column wave
    (sin(u + v) = sin u cos v + cos u sin v), so it costs a few outer products."""
    rng = np.random.default_rng(seed + 9001)
    x = np.arange(W, dtype=np.float64)
    y = np.arange(H, dtype=np.float64)
    out = []
    for _axis in range(2):
        acc = np.zeros((H, W), np.float32)
        norm = 0.0
        for k in range(comps):
            a = rng.uniform(0, 2 * math.pi)
            lam = scale * H / (1.6 ** (k * 0.5))
            f = 2 * math.pi / lam
            amp = 1.0 / (1.0 + 0.6 * k)
            ph = rng.uniform(0, 2 * math.pi)
            sp = rng.uniform(0.6, 1.4) * (1 if rng.random() < 0.5 else -1)
            u = f * math.cos(a) * x
            v = f * math.sin(a) * y + ph + sp * t
            cv, sv = (amp * np.cos(v)).astype(np.float32), (amp * np.sin(v)).astype(np.float32)
            su, cu = np.sin(u).astype(np.float32), np.cos(u).astype(np.float32)
            acc += cv[:, None] * su[None, :] + sv[:, None] * cu[None, :]
            norm += amp * amp
        out.append(acc / math.sqrt(2.0 * norm))
    return out[0], out[1]

class _Lin:
    """Linear copies of frames, made when asked and kept for a short window."""

    def __init__(self, frames, keep=48):
        self.f, self.keep, self.c = frames, keep, {}

    def __call__(self, i):
        i = min(max(int(i), 0), len(self.f) - 1)
        x = self.c.get(i)
        if x is None:
            if len(self.c) >= self.keep:
                self.c.pop(next(iter(self.c)))
            x = self.c[i] = lin(self.f[i])
        return x

def _at(frames, t, L=None):
    """The picture at a time t (frames, may be fractional): a copy of a frame, or two neighbours mixed in linear."""
    n = len(frames)
    t = min(max(float(t), 0.0), n - 1.0)
    a = int(math.floor(t))
    u = t - a
    if u < 1e-4 or a >= n - 1:
        return frames[a].copy()
    if u > 1 - 1e-4:
        return frames[a + 1].copy()
    L = L or _Lin(frames, 4)
    return disp(L(a) * (1 - u) + L(a + 1) * u)

def _shift_scale(img, dx, dy, s=1.0):
    H, W = img.shape[:2]
    c = ((W - 1) / 2.0, (H - 1) / 2.0)
    M = np.array([[s, 0, c[0] * (1 - s) + dx], [0, s, c[1] * (1 - s) + dy]], np.float32)
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)

def _affine_map(H, W, zoom, turn, centre):
    """Where each output pixel samples the fed-back picture: about the centre, 1/zoom and turned back by turn deg."""
    gx, gy = _grid(H, W)
    cx, cy = centre[0] * (W - 1), centre[1] * (H - 1)
    a = math.radians(turn)
    c, s = math.cos(a), math.sin(a)
    x, y = (gx - cx) / zoom, (gy - cy) / zoom
    return (cx + c * x + s * y).astype(np.float32), (cy - s * x + c * y).astype(np.float32)

def _bubble_map(H, W, centre, radius, refract):
    """The sample point seen through a glass ball: the picture magnified at the ball's middle and pressed toward its
    rim, continuous with the plain picture at the rim. Returns the map and the ball's soft-edged coverage."""
    gx, gy = _grid(H, W)
    cx, cy = centre[0] * (W - 1), centre[1] * (H - 1)
    R = radius * H
    px, py = gx - cx, gy - cy
    d = np.sqrt(px * px + py * py) / R
    e = 0.08
    z = (np.sqrt(np.clip(1.0 - d * d, 0.0, 1.0) + e) - math.sqrt(e)) / (math.sqrt(1.0 + e) - math.sqrt(e))
    k = 1.0 - refract * z
    mx, my = cx + px * k, cy + py * k
    cover = 1.0 - _smoothstep(0.9, 1.0, d)
    return mx.astype(np.float32), my.astype(np.float32), cover.astype(np.float32)

def _compose(mapx, mapy, ax, ay):
    """The affine sample map read at the points of another map (first through the ball, then the loop's zoom)."""
    return (cv2.remap(ax, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE),
            cv2.remap(ay, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE))

def _loop_pass(echo, contrast, chroma):
    """What one trip round a camera and monitor loop does to a picture: the system gamma above 1 sinks the dim parts
    faster than the bright (so old echoes fall to black, not to a grey veil), and the chroma gain pushes the colour
    further from grey each trip (so echoes of fire stay fire-coloured as they fade)."""
    if abs(contrast - 1.0) > 1e-6:
        echo = np.power(np.maximum(echo, 0.0), contrast)
    if abs(chroma - 1.0) > 1e-6:
        y = (echo @ _LW)[..., None]
        echo = np.maximum(y + chroma * (echo - y), 0.0)
    return echo

def _feedback_core(frames, env, maps, decay, hue, soft, blend, contrast, chroma, cover=None, shade=None, lens=None):
    """blend screen, max or add: the echo (darkened by decay) laid over the live picture; mix: the live picture
    replaced by decay of the echo (no light is added, so nothing lifts)."""
    n = len(frames)
    e = envelope(env, n)
    H, W = frames[0].shape[:2]
    sc = H / 1080.0
    win = _edge_window(H, W, 28 * sc)[..., None]
    out, fb = [], None
    for i, f in enumerate(frames):
        g = float(e[i])
        cur = lin(f)
        if fb is None or g <= 0:
            out.append(f.copy())
            fb = cur
            continue
        if lens is not None:
            lx, ly, lc = lens
            seen = cv2.remap(cur, lx, ly, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            cur = cur + (g * lc)[..., None] * (seen - cur)
        mx, my = maps(i)
        if blend == "mix":
            echo = cv2.remap(fb, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        else:
            echo = cv2.remap(fb * win, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        if soft > 0.05:
            echo = cv2.GaussianBlur(echo, (0, 0), soft * sc)
        echo = _loop_pass(_hue(echo, hue), contrast, chroma)
        a = np.float32(g * decay) if cover is None else (g * decay * cover)[..., None]
        if blend == "mix":
            o = cur + a * (echo - cur)
        else:
            o = _combine(cur, a * echo, blend)
        if shade is not None:
            o = o * (1.0 - g * shade)[..., None]
        fb = o
        out.append(disp(o))
    return out

def feedback(frames, env=1.0, zoom=1.025, turn=0.6, decay=0.62, hue=0.0, soft=0.8, centre=(0.5, 0.5),
             blend="screen", contrast=1.35, chroma=1.06):
    """The output fed back each frame: zoomed by zoom and turned by turn degrees about centre, each pass darker by
    decay, hue turned by hue degrees, softened by soft px, sunk by contrast and saturated by chroma (one trip round a
    camera pointed at its monitor), and laid over the live picture by screen in linear light (or max, add, mix).
    zoom above 1 sends the echoes outward (a tunnel toward the viewer), below 1 inward."""
    H, W = frames[0].shape[:2]
    m = _affine_map(H, W, zoom, turn, centre)
    return _feedback_core(frames, env, lambda i: m, decay, hue, soft, blend, contrast, chroma)

def feedback_bubble(frames, env=1.0, zoom=0.62, turn=0.0, decay=0.55, hue=0.0, soft=0.3, bubble=(0.5, 0.5),
                    radius=0.36, refract=0.32, blend="mix", inside=True, rim=0.25, contrast=1.0, chroma=1.03):
    """The loop seen through a glass ball centred at bubble (share of width, height) of radius (share of height).
    The live picture is seen through the ball (magnified at its middle, pressed toward its rim, the rim darkened by
    rim where light glances off), and the output is fed back through the ball and shrunk by zoom each pass, so the
    ball holds smaller and smaller balls receding into it. The default mix lays decay of the loop in place of the
    live picture (no light is added); turn spins each pass. inside keeps the echoes in the ball."""
    H, W = frames[0].shape[:2]
    bx, by, cover = _bubble_map(H, W, bubble, radius, refract)
    ax, ay = _affine_map(H, W, zoom, turn, bubble)
    mx, my = _compose(bx, by, ax, ay)
    gx, gy = _grid(H, W)
    d = np.sqrt((gx - bubble[0] * (W - 1)) ** 2 + (gy - bubble[1] * (H - 1)) ** 2) / (radius * H)
    shade = (rim * _smoothstep(0.62, 0.97, d) * cover).astype(np.float32) if rim > 0 else None
    return _feedback_core(frames, env, lambda i: (mx, my), decay, hue, soft, blend, contrast, chroma,
                          cover if inside else None, shade, (bx, by, cover))

def feedback_distort(frames, env=1.0, zoom=1.01, turn=0.0, decay=0.68, hue=0.0, soft=0.7, centre=(0.5, 0.5),
                     amount=6.0, scale=0.2, drift=0.08, seed=0, blend="screen", contrast=1.3, chroma=1.06):
    """The loop pushed through a smooth noise field each pass: amount px at 1080 of push, scale the size of its
    swirls (share of the height), drift how fast the field moves per frame. The pushes add up over the passes, so
    older echoes curl further, like a picture seen through rising heat."""
    H, W = frames[0].shape[:2]
    sc = H / 1080.0
    ax, ay = _affine_map(H, W, zoom, turn, centre)

    def maps(i):
        nx, ny = noise_field(H, W, i * drift, scale, seed)
        return ax + amount * sc * nx, ay + amount * sc * ny
    return _feedback_core(frames, env, maps, decay, hue, soft, blend, contrast, chroma)

def time_matte(kind, frame, angle=0.0, centre=(0.5, 0.5), soften=6.0):
    """A 0..1 matte: luma (the picture's own brightness, softened by soften px at 1080), ramp (across the frame at
    angle degrees: 0 runs left to right), radial (0 at centre, 1 at the farthest corner)."""
    H, W = frame.shape[:2]
    if kind == "luma":
        m = _luma_disp(frame)
        if soften > 0:
            m = cv2.GaussianBlur(m, (0, 0), soften * H / 1080.0)
        return np.clip(m, 0, 1)
    gx, gy = _grid(H, W)
    cx, cy = centre[0] * (W - 1), centre[1] * (H - 1)
    if kind == "ramp":
        a = math.radians(angle)
        p = (gx - cx) * math.cos(a) + (gy - cy) * math.sin(a)
        return ((p - p.min()) / max(float(p.max() - p.min()), 1e-6)).astype(np.float32)
    if kind == "radial":
        r = np.sqrt((gx - cx) ** 2 + (gy - cy) ** 2)
        return (r / max(float(r.max()), 1e-6)).astype(np.float32)
    raise ValueError(f"matte {kind!r}: luma, ramp, radial, an array or a function")

def time_displace(frames, env=1.0, depth=12.0, matte="luma", angle=0.0, centre=(0.5, 0.5), invert=False,
                  soften=6.0, ahead=False):
    """Each pixel taken from the frame depth x env x matte frames back (ahead: forward). matte: "luma", "ramp",
    "radial", an HxW array 0..1, or a function (i, frame) -> HxW array. Offsets between whole frames mix the two
    neighbours in linear light by the fraction, so a smooth matte gives a smooth picture with no steps. Times before
    the first frame (or after the last) hold the end frame."""
    n = len(frames)
    e = envelope(env, n)
    H, W = frames[0].shape[:2]
    L = _Lin(frames, int(abs(depth)) + 6)
    fixed = None
    if isinstance(matte, np.ndarray):
        fixed = matte.astype(np.float32)
    elif isinstance(matte, str) and matte != "luma":
        fixed = time_matte(matte, frames[0], angle, centre, soften)
    out = []
    for i, f in enumerate(frames):
        g = float(e[i])
        if g <= 0 or depth == 0:
            out.append(f.copy())
            continue
        if fixed is not None:
            m = fixed
        elif callable(matte):
            m = np.asarray(matte(i, f), np.float32)
        else:
            m = time_matte("luma", f, soften=soften)
        if invert:
            m = 1.0 - m
        o = (depth * g) * np.clip(m, 0, 1)
        k0, k1 = int(math.floor(float(o.min()))), int(math.ceil(float(o.max())))
        acc = np.zeros((H, W, 3), np.float32)
        for k in range(k0, k1 + 1):
            w = np.maximum(0.0, 1.0 - np.abs(o - k))
            if not w.any():
                continue
            acc += L(i + k if ahead else i - k) * w[..., None]
        out.append(disp(acc))
    return out

def light_mask(f, key=0.0, pop=0.0, thin=0.0, alone=0.0):
    """Which parts of a picture are lights, 0..1, eased: key keeps what is brighter than key (display luma); pop keeps
    small points brighter than the ring round them by pop (fireflies: 0.45), so a bright background never counts as a
    light. thin keeps points and thin streaks (under 7 px across at 1080) brighter than their wider surroundings by
    thin, so sparks count and the flame they fly from does not. alone keeps points brighter than the brightest pixel
    of that ring by alone (fireflies: 0.3): a glint where a dark trunk meets the sky has sky as bright as itself on
    one side and fails, though its ring's mean passes pop (fireflies clear the ring's brightest by 0.53 to 0.67,
    the trunk-edge glints by -0.03 to 0.04). Several given: all must hold."""
    L = _luma_disp(f)
    m = np.ones_like(L)
    if alone > 0:
        ring = (_ring(f.shape[0]) > 0).astype(np.uint8)
        d = L - cv2.dilate(L, ring, borderType=cv2.BORDER_REFLECT)
        m *= _smoothstep(alone - 0.05, alone + 0.05, d) * _smoothstep(0.3, 0.5, L)
    if key > 0:
        m *= _smoothstep(key - 0.08, key + 0.08, L)
    if pop > 0:
        d = L - cv2.filter2D(L, -1, _ring(f.shape[0]), borderType=cv2.BORDER_REFLECT)
        m *= _smoothstep(pop - 0.05, pop + 0.05, d) * _smoothstep(0.3, 0.5, L)
    if thin > 0:
        s = max(3, int(round(7 * f.shape[0] / 1080.0)) | 1)
        d = L - cv2.morphologyEx(L, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (s, s)))
        m *= _smoothstep(thin - 0.05, thin + 0.05, d) * _smoothstep(0.2, 0.4, L)
    return m

def _ring(H):
    """A ring 3 to 7 px out at 1080 (at least 2 to 4): its mean is a point's surroundings. A firefly is brighter than
    all of its ring; a gap of sky among twigs shares its ring with more sky, so it does not count (a plain blur
    let the sky gaps of the firefly forest through and the whole frame streaked)."""
    sc = H / 1080.0
    ri, ro = max(2.0, 3.0 * sc), max(4.0, 7.0 * sc)
    r = int(math.ceil(ro))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    d = np.sqrt(xx * xx + yy * yy)
    k = ((d >= ri) & (d <= ro)).astype(np.float32)
    return k / k.sum()

class _Lights:
    """The lights of each frame as sparse points (their linear colour by their mask) with the motion that carries
    each to the next frame, so a moving light can be swept along its path between frames instead of stamped once a
    frame (which leaves a row of beads).

    move 0: the motion is the optical flow at each point (OpenCV DIS at full size).
    move above 0 (px at 1080): each light is tracked as a blob. The camera's local motion (the median DIS flow in a
    window about 160 px wide, so near and far parts of a dolly each get their own) predicts where a part of the scene
    would be next frame; the nearest light blob there is the same light. A light kept by the scene (a twig highlight
    in a pan) lands where the camera says; a firefly drifts away from it. Lights whose drift from the camera over
    persist frames is above move (faded in over a band of 1.5 px) and which are found in each of those frames are
    kept, and each is swept along its own tracked motion. DIS alone cannot tell them apart: its flow at a 3 px firefly
    follows the scene around it (the residual of DIS flow at the fireflies was under 0.3 px for most of them)."""

    def __init__(self, frames, key, pop, thin=0.0, keep=6, move=None, persist=3, alone=0.0):
        self.f, self.key, self.pop, self.thin, self.keep, self.c = frames, key, pop, thin, keep, {}
        self.alone = alone
        self.move, self.persist, self.hold = move, int(persist), 3
        self.dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
        self.H, self.W = frames[0].shape[:2]
        self.sc = self.H / 1080.0
        self._m, self._F, self._b = {}, {}, {}

    def _cache(self, d, j, make):
        x = d.get(j)
        if x is None:
            if len(d) >= self.keep + self.persist + 2:
                d.pop(next(iter(d)))
            x = d[j] = make(j)
        return x

    def mask(self, j):
        return self._cache(self._m, j, lambda k: light_mask(self.f[k], self.key, self.pop, self.thin, self.alone))

    def flow(self, j):
        """DIS flow from frame j to j+1 (zero on the last frame)."""
        def make(k):
            if k + 1 >= len(self.f):
                return np.zeros((self.H, self.W, 2), np.float32)
            ga = cv2.cvtColor(self.f[k], cv2.COLOR_RGB2GRAY)
            gb = cv2.cvtColor(self.f[k + 1], cv2.COLOR_RGB2GRAY)
            return self.dis.calc(ga, gb, None)
        return self._cache(self._F, j, make)

    def blobs(self, j):
        """Frame j's light blobs: their centroids, the nearest-blob map, and the camera's local motion."""
        def make(k):
            b = (self.mask(k) > 0.3).astype(np.uint8)
            n, lab, _st, cent = cv2.connectedComponentsWithStats(b, connectivity=8)
            dist, dl = cv2.distanceTransformWithLabels(1 - b, cv2.DIST_L2, 3, labelType=cv2.DIST_LABEL_CCOMP)
            mp = np.zeros(int(dl.max()) + 1, np.int64)
            on = b > 0
            mp[dl[on]] = lab[on]
            F = self.flow(k)
            B = max(8, int(round(32 * self.sc)))
            bh, bw = max(1, self.H // B), max(1, self.W // B)
            blk = F[:bh * B, :bw * B].reshape(bh, B, bw, B, 2).transpose(0, 2, 1, 3, 4).reshape(bh, bw, B * B, 2)
            med = np.median(blk, axis=2).astype(np.float32)
            if bh >= 5 and bw >= 5:
                med = np.stack([cv2.medianBlur(np.ascontiguousarray(med[..., c]), 5) for c in range(2)], -1)
            cam = cv2.resize(med, (self.W, self.H), interpolation=cv2.INTER_LINEAR)
            return cent.astype(np.float32), dist, mp[dl], cam
        return self._cache(self._b, j, make)

    def _track(self, j):
        """Per blob of frame j: its weight (moves against the scene and persists) and its own motion to j+1."""
        cent, _d, _near, _cam = self.blobs(j)
        nb = len(cent)
        pos = cent.copy()
        res = np.zeros((nb, 2), np.float32)
        found = np.zeros(nb, np.float32)
        motion = np.zeros((nb, 2), np.float32)
        steps = 0
        R = 6.0 * self.sc + 1.0
        J = 2.0 * self.sc
        prev = None
        steady = np.ones(nb, bool)
        for t in range(self.persist):
            a = j + t
            if a + 1 >= len(self.f):
                break
            steps += 1
            _c, _dd, _nn, cam = self.blobs(a)
            ix = np.clip(np.rint(pos[:, 0]).astype(np.int64), 0, self.W - 1)
            iy = np.clip(np.rint(pos[:, 1]).astype(np.int64), 0, self.H - 1)
            pred = pos + cam[iy, ix]
            c1, d1, near1, _cam1 = self.blobs(a + 1)
            px = np.clip(np.rint(pred[:, 0]).astype(np.int64), 0, self.W - 1)
            py = np.clip(np.rint(pred[:, 1]).astype(np.int64), 0, self.H - 1)
            ok = d1[py, px] <= R
            hit = c1[near1[py, px]]
            r = np.where(ok[:, None], hit - pred, 0.0)
            if prev is not None:
                steady &= np.sqrt(((r - prev) ** 2).sum(1)) <= J
            prev = r
            res += r
            found += ok
            if t == 0:
                motion = np.where(ok[:, None], hit - pos, pred - pos)
                link = np.where(ok, near1[py, px], 0)
            pos = np.where(ok[:, None], hit, pred)
        if steps == 0:
            w = np.ones(nb, np.float32)
            w[0] = 0.0
            return w, motion, np.zeros(nb, np.int64)
        drift = np.sqrt((res ** 2).sum(1))
        m = self.move * self.sc
        w = (found >= steps) * steady * (_smoothstep(m - 0.75 * self.sc, m + 0.75 * self.sc, drift) if m > 0 else 1.0)
        w[0] = 0.0
        return w.astype(np.float32), motion, link

    def _held(self, j):
        """_track's weights with a hold: a light kept in one of the last `hold` frames stays kept while it is still
        tracked, so a firefly that blinks or is missed for a frame does not leave a gap in its line (without it
        the light painting read as dotted lines)."""
        if not hasattr(self, "_h"):
            self._h = {}
        start = j
        while start > 0 and (start - 1) not in self._h and j - start < self.hold:
            start -= 1
        for k in range(start, j + 1):
            if k in self._h:
                continue
            w, motion, link = self._track(k)
            age = np.where(w > 0.5, 0, 99)
            if k - 1 in self._h:
                wp, agep, linkp, _mp = self._h[k - 1]
                carry = (wp > 0.5) & (agep < self.hold) & (linkp > 0)
                tgt = linkp[carry]
                w = w.copy()
                np.maximum.at(w, tgt, wp[carry])
                np.minimum.at(age, tgt, agep[carry] + 1)
                w[0] = 0.0
            self._h[k] = (w, age, link, motion)
            if len(self._h) > self.keep + self.hold + 4:
                self._h.pop(min(self._h))
        w, _age, _link, motion = self._h[j]
        return w, motion

    def __call__(self, j):
        x = self.c.get(j)
        if x is not None:
            return x
        if len(self.c) >= self.keep:
            self.c.pop(next(iter(self.c)))
        f = self.f[j]
        m = self.mask(j)
        ys, xs = np.nonzero(m > 0.02)
        col = lin(f)[ys, xs] * m[ys, xs, None]
        if self.move is not None:
            w, motion = self._held(j)
            near = self.blobs(j)[2][ys, xs]
            wp = w[near]
            keep = wp > 0.01
            ys, xs, near = ys[keep], xs[keep], near[keep]
            col = col[keep] * wp[keep, None]
            fx, fy = motion[near, 0], motion[near, 1]
        elif j + 1 < len(self.f) and len(ys):
            F = self.flow(j)
            fx, fy = F[ys, xs, 0], F[ys, xs, 1]
        else:
            fx = fy = np.zeros(len(ys), np.float32)
        x = self.c[j] = (ys.astype(np.float32), xs.astype(np.float32), col.astype(np.float32),
                         np.asarray(fx, np.float32), np.asarray(fy, np.float32))
        return x

    def sweep(self, j, layer, weight, s0=0.0, s1=1.0):
        """Lay frame j's lights into layer (H*W x 3, by max) along their path from s0 to s1 of the way to frame j+1,
        in steps of at most half a pixel; weight(s) scales each step."""
        ys, xs, col, fx, fy = self(j)
        if not len(ys) or s1 <= s0:
            return
        steps = np.clip(np.ceil(np.sqrt(fx * fx + fy * fy) * (s1 - s0) / 0.5), 1, 64).astype(np.int64)
        idx = np.repeat(np.arange(len(ys)), steps)
        first = np.repeat(np.cumsum(steps) - steps, steps)
        u = (np.arange(len(idx)) - first) / steps[idx]
        s = (s0 + (s1 - s0) * u).astype(np.float32)
        px = np.rint(xs[idx] + s * fx[idx]).astype(np.int64)
        py = np.rint(ys[idx] + s * fy[idx]).astype(np.int64)
        ok = (px >= 0) & (px < self.W) & (py >= 0) & (py < self.H)
        w = np.asarray(weight(s[ok]), np.float32).reshape(-1, 1)
        flat = py[ok] * self.W + px[ok]
        vals = col[idx[ok]] * w
        lum = vals @ _LW
        order = np.lexsort((lum, flat))
        flat, vals, lum = flat[order], vals[order], lum[order]
        last = np.ones(len(flat), bool)
        last[:-1] = flat[1:] != flat[:-1]
        flat, vals, lum = flat[last], vals[last], lum[last]
        win = lum > layer[flat] @ _LW
        layer[flat[win]] = vals[win]

def trails(frames, env=1.0, length=8, decay=0.72, blend="max", key=0.0, pop=0.0, thin=0.0, sweep=False, move=None,
           persist=3, alone=0.0, offset=(0.0, 0.0),
           hue=0.0, soft=0.0):
    """Echoes of the frames before, combined with the live picture by max (lighten: bright moving things leave fading
    trails and dark stays dark), screen, or average (the echoes and the live picture mixed by their weights, a smear).
    Echo k is weighted decay**k and by env. key, pop, thin, alone (see light_mask) keep only the lights' echoes.
    sweep (lights only, max or screen): each light is drawn along its whole path between frames by optical flow, so
    the trail is one continuous streak as on a long exposure, and the trail decays by decay a frame with no length
    limit (decay 1 paints and never fades). Sweep suits point lights (fireflies, lamps); lights already streaked in
    the footage (sparks at an open shutter) sweep into ribbons and read better as plain echoes. move (px at 1080,
    with sweep): keep only lights that drift from the scene by more than move over persist frames, each swept
    along its own tracked path (fireflies in a pan, where twig highlights ride the camera; see _Lights). Without sweep: length echoes; offset moves echo k by k x offset px at
    1080; hue turns echo k by k x hue degrees; soft blurs echo k by k x soft px."""
    n = len(frames)
    e = envelope(env, n)
    H, W = frames[0].shape[:2]
    sc = H / 1080.0
    if sweep:
        lit = key > 0 or pop > 0 or thin > 0 or alone > 0
        return _trails_swept(frames, e, decay, blend, key, pop if lit else 0.45, thin, hue, move, persist, alone)
    L = _Lin(frames, int(length) + 4)
    out = []
    for i, f in enumerate(frames):
        g = float(e[i])
        if g <= 0 or i == 0:
            out.append(f.copy())
            continue
        o = L(i).copy()
        acc, wsum = np.zeros_like(o), 0.0
        for k in range(1, int(length) + 1):
            if i - k < 0:
                break
            w = g * decay ** k
            x = L(i - k)
            if key > 0 or pop > 0 or thin > 0 or alone > 0:
                x = x * light_mask(frames[i - k], key, pop, thin, alone)[..., None]
            if offset[0] or offset[1]:
                x = _shift_scale(x, k * offset[0] * sc, k * offset[1] * sc)
            if soft > 0:
                x = cv2.GaussianBlur(x, (0, 0), k * soft * sc)
            x = _hue(x, k * hue)
            if blend == "average":
                acc += w * x
                wsum += w
            else:
                o = _combine(o, w * x, blend)
        if blend == "average":
            o = (o + acc) / (1.0 + wsum)
        out.append(disp(o))
    return out

def _trails_swept(frames, e, decay, blend, key, pop, thin, hue, move=None, persist=3, alone=0.0):
    n = len(frames)
    H, W = frames[0].shape[:2]
    sc = H / 1080.0
    lights = _Lights(frames, key, pop, thin, move=move, persist=persist, alone=alone)
    T = np.zeros((H * W, 3), np.float32)
    live = False
    out = []
    for i, f in enumerate(frames):
        g = float(e[i])
        if live:
            T *= np.float32(decay)
            if hue:
                T = _hue(T, hue)
        if i > 0 and g > 0:
            lights.sweep(i - 1, T, lambda s: g * decay ** (1.0 - s))
            live = True
        if not live or float(T.max()) < 1e-6:
            out.append(f.copy())
            continue
        t = cv2.GaussianBlur(T.reshape(H, W, 3), (0, 0), 0.6 * sc)
        out.append(disp(_combine(lin(f), t, "screen" if blend == "screen" else "max")))
    return out

def trails_diffuse(frames, env=1.0, decay=0.9, rise=(0.0, -5.0), spread=2.6, swirl=6.0, key=0.55, pop=0.0,
                   thin=0.0, gain=0.5, fade=0.0, contrast=1.08, scale=0.12, drift=0.05, sweep=False,
                   move=None, persist=3, alone=0.0, blend="screen", seed=0):
    """Trails that drift and blur as they fade, like smoke: the lights of the live picture (key, pop, thin: see
    light_mask) are laid into a trail each frame at gain x env; the trail moves by rise px per frame at 1080 plus
    swirl px of a smooth drifting noise field, blurs by spread px, keeps decay of its light, sinks its thin parts by
    contrast and loses fade of its colour each frame, and is screened (or maxed, or added) over the live picture. The
    blur adds up frame on frame, so the oldest trail is the widest and faintest. When env falls the trail already laid
    drifts on and fades. The defaults suit a fire's glow. For small moving lights (fireflies) set sweep, so each
    light lays its whole path between frames (one ribbon, not a row of beads), with a faster drift (0.2) so the push
    wanders like a random walk and the smoke spreads instead of stretching into marbled threads; move and persist
    as in trails."""
    n = len(frames)
    e = envelope(env, n)
    H, W = frames[0].shape[:2]
    sc = H / 1080.0
    gx, gy = _grid(H, W)
    win = _edge_window(H, W, 20 * sc)[..., None]
    lights = _Lights(frames, key, pop, thin, move=move, persist=persist, alone=alone) if sweep else None
    out, buf = [], None
    for i, f in enumerate(frames):
        g = float(e[i])
        cur = lin(f)
        trail = None
        if buf is not None:
            nx, ny = noise_field(H, W, i * drift, scale, seed)
            mx = gx - rise[0] * sc - swirl * sc * nx
            my = gy - rise[1] * sc - swirl * sc * ny
            trail = cv2.remap(buf * win, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            if spread > 0:
                trail = cv2.GaussianBlur(trail, (0, 0), spread * sc)
            if fade > 0:
                trail = trail * (1 - fade) + fade * (trail @ _LW)[..., None]
            trail = _loop_pass(trail, contrast, 1.0) * decay
            if float(trail.max()) < 1e-6:
                trail = None
        if trail is None:
            out.append(f.copy())
        else:
            out.append(disp(_combine(cur, trail, blend)))
        if g > 0 and lights is not None:
            if i == 0:
                continue
            layer = np.zeros((H * W, 3), np.float32)
            lights.sweep(i - 1, layer, lambda s: g * gain)
            feed = layer.reshape(H, W, 3)
            buf = feed if trail is None else _screen(trail, feed)
        elif g > 0:
            feed = cur * (g * gain * light_mask(f, key, pop, thin, alone))[..., None]
            buf = feed if trail is None else _screen(trail, feed)
        else:
            buf = trail
    return out

def time_average(frames, env=1.0, radius=4.0, blend="mean", past=False, key=0.0, pop=0.0, thin=0.0, sweep=True,
                 move=None, persist=3, alone=0.0):
    """A window 2 x radius x env frames wide around each frame (past: the frames before it), mixed in linear light:
    mean (a long exposure: water turns to silk) or max (every bright thing that passed stays lit). With key, pop or thin
    (see light_mask) and max, only the lights are kept and the rest of the picture stays live; with sweep each light
    is drawn along its path between frames by optical flow, so a point light paints one continuous line (light
    painting). Sweep suits points (fireflies, lamps); lights that are already streaks in the footage (sparks shot at
    an open shutter) read better with sweep off, their own streaks joined end to end. The window's end frames count
    by the fraction of the radius, so it grows without a step. move and persist (with sweep) as in trails."""
    n = len(frames)
    e = envelope(env, n)
    H, W = frames[0].shape[:2]
    sc = H / 1080.0
    L = _Lin(frames, int(2 * radius) + 6)
    lit = blend == "max" and (key > 0 or pop > 0 or thin > 0 or alone > 0)
    lights = (_Lights(frames, key, pop, thin, keep=int(2 * radius) + 6, move=move, persist=persist, alone=alone)
              if lit and sweep else None)
    out = []
    for i, f in enumerate(frames):
        R = radius * float(e[i])
        if R <= 1e-4:
            out.append(f.copy())
            continue
        lo, hi = (i - 2 * R, i) if past else (i - R, i + R)
        if lights is not None:
            T = np.zeros((H * W, 3), np.float32)
            for j in range(max(0, int(math.floor(lo))), min(n - 1, int(math.ceil(hi)))):
                s0, s1 = max(0.0, lo - j), min(1.0, hi - j)
                lights.sweep(j, T, lambda s: 1.0, s0, s1)
            t = cv2.GaussianBlur(T.reshape(H, W, 3), (0, 0), 0.6 * sc)
            out.append(disp(np.maximum(lin(f), t)))
            continue
        span = int(math.ceil(R + 0.5))
        acc, wsum = None, 0.0
        for j in range(-span if not past else -2 * span, (span if not past else 0) + 1):
            if past:
                w = min(1.0, max(0.0, 2 * R + 0.5 - abs(j)))
            else:
                w = min(1.0, max(0.0, R + 0.5 - abs(j)))
            if w <= 0 or not (0 <= i + j < n):
                continue
            x = L(i + j)
            if lit and j != 0:
                x = x * light_mask(frames[i + j], key, pop, thin, alone)[..., None]
            if blend == "max":
                acc = w * x if acc is None else np.maximum(acc, w * x)
            else:
                acc = w * x if acc is None else acc + w * x
                wsum += w
        out.append(disp(acc if blend == "max" else acc / wsum))
    return out

def _segments(n, seg, rng):
    s, segs = 0, []
    while s < n:
        ln = int(rng.integers(seg[0], seg[1] + 1))
        segs.append((s, min(n, s + ln)))
        s += ln
    return segs

def _pick(frames, src):
    return [frames[int(min(max(k, 0), len(frames) - 1))].copy() for k in src]

def random_edits(frames, env=1.0, seg=(6, 18), reach=None, seed=0):
    """The clip cut into pieces seg[0] to seg[1] frames long; each piece, with the chance env at its first frame, is
    replaced by a piece of the same length from elsewhere in the clip (within reach frames when given). Each piece
    plays forward. Returns the frames and leaves a source index list in random_edits.last."""
    n = len(frames)
    e = envelope(env, n)
    rng = np.random.default_rng(seed)
    src = list(range(n))
    for a, b in _segments(n, seg, rng):
        r, ln = rng.random(), b - a
        lo, hi = (0, n - ln) if reach is None else (max(0, a - reach), min(n - ln, a + reach))
        start = int(rng.integers(lo, hi + 1)) if hi >= lo else a
        if r < e[a]:
            src[a:b] = range(start, start + ln)
    random_edits.last = src
    return _pick(frames, src)

def reverse_edits(frames, env=1.0, seg=(6, 14), seed=0):
    """The clip cut into pieces seg[0] to seg[1] frames long; each piece, with the chance env at its middle, plays
    backwards in its own place. Leaves the source index list in reverse_edits.last."""
    n = len(frames)
    e = envelope(env, n)
    rng = np.random.default_rng(seed)
    src = list(range(n))
    for a, b in _segments(n, seg, rng):
        if rng.random() < e[(a + b - 1) // 2]:
            src[a:b] = range(b - 1, a - 1, -1)
    reverse_edits.last = src
    return _pick(frames, src)

def get_frame(frames, env=1.0, at=0.0, offset=None):
    """The picture from another moment mixed over the live one by env in linear light: frame at (a fixed frame, a
    freeze), or, with offset, the frame offset frames away from each one (may be fractional, interpolated)."""
    n = len(frames)
    e = envelope(env, n)
    L = _Lin(frames, 8)
    held = None if offset is not None else _at(frames, at, L)
    out = []
    for i, f in enumerate(frames):
        g = float(e[i])
        if g <= 0:
            out.append(f.copy())
            continue
        src = held if held is not None else _at(frames, i + offset, L)
        if g >= 1:
            out.append(src.copy())
        else:
            out.append(disp(lin(f) * (1 - g) + lin(src) * g))
    return out

def looper(frames, start=0, length=24, xfade=6, bounce=False):
    """The frames start .. start+length-1 looped for the clip's length. The loop's last xfade frames crossfade (in
    linear light) toward the frames just before start, so the jump back to start continues the motion. bounce plays
    the section forward then back instead (no crossfade needed)."""
    n = len(frames)
    length = int(min(length, n - start))
    xfade = int(min(xfade, start, length - 1))
    L = _Lin(frames, 2 * xfade + 4)
    out = []
    for i in range(n):
        if bounce:
            p = i % max(1, 2 * length - 2)
            k = p if p < length else 2 * length - 2 - p
            out.append(frames[start + k].copy())
            continue
        k = i % length
        if xfade > 0 and k >= length - xfade:
            w = (k - (length - xfade) + 1) / (xfade + 1.0)
            out.append(disp(L(start + k) * (1 - w) + L(start + k - length) * w))
        else:
            out.append(frames[start + k].copy())
    return out

def posterize_time(frames, env=1.0, step=3.0, shutter=0.0):
    """The clip held to one new frame in every step x env frames (fractional steps average out over time, a step of
    1 is the clip). shutter 0..1: each held frame becomes the linear mean of that share of the frames it stands for,
    as film at a low rate with an open shutter, which reads as motion blur where the plain hold reads as a stutter."""
    n = len(frames)
    e = envelope(env, n)
    holds, ph = [], 1.0
    for i in range(n):
        s = 1.0 + (step - 1.0) * max(0.0, float(e[i]))
        if ph >= 1.0 - 1e-9:
            holds.append([i, 1])
            ph -= 1.0
        else:
            holds[-1][1] += 1
        ph += 1.0 / s
    L = _Lin(frames, int(step) + 4)
    out = []
    for h, run in holds:
        m = max(1, int(round(run * shutter)))
        pic = frames[h].copy() if m == 1 else disp(sum(L(h + j) for j in range(m)) / m)
        out.extend(pic.copy() for _ in range(run))
    return out

def jitter_basic(frames, env=1.0, amount=3, seed=0):
    """Each frame swapped for one up to amount x env frames before or after it, picked at random each frame."""
    n = len(frames)
    e = envelope(env, n)
    rng = np.random.default_rng(seed)
    d = rng.integers(-int(amount), int(amount) + 1, n)
    src = [i + int(round(d[i] * e[i])) for i in range(n)]
    jitter_basic.last = src
    return _pick(frames, src)

def jitter(frames, env=1.0, amount=3.0, hold=2, shake=0.0, seed=0):
    """Time jitter held for hold frames at a time: each hold shows the clip from up to amount x env frames away
    (fractional, interpolated in linear light), and with shake (px at 1080) the frame itself jumps by up to that much,
    scaled just enough to keep the edges covered, like a gate that does not hold the film still."""
    n = len(frames)
    e = envelope(env, n)
    H, W = frames[0].shape[:2]
    sc = H / 1080.0
    rng = np.random.default_rng(seed)
    L = _Lin(frames, int(amount) * 2 + 6)
    out, src = [], []
    for i in range(n):
        if i % max(1, hold) == 0:
            d = rng.uniform(-amount, amount)
            sx, sy = rng.uniform(-1, 1, 2)
        g = float(e[i])
        if g <= 0:
            out.append(frames[i].copy())
            src.append(i)
            continue
        t = i + d * g
        src.append(t)
        pic = _at(frames, t, L)
        if shake > 0:
            dx, dy = sx * shake * sc * g, sy * shake * sc * g
            s = 1.0 + 2.0 * max(abs(dx) / W, abs(dy) / H) + 1e-4
            pic = _shift_scale(pic, dx, dy, s)
        out.append(pic)
    jitter.last = src
    return out

def _flow(a, b, method, smooth, limit=0.0):
    """Flow from picture a to b (a(x) ~ b(x + F(x))), measured at half size above 1000 px wide, held to limit x the
    height and smoothed."""
    H, W = a.shape[:2]
    k = 2 if W > 1000 else 1
    ga = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    gb = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    if k > 1:
        ga = cv2.resize(ga, (W // k, H // k), interpolation=cv2.INTER_AREA)
        gb = cv2.resize(gb, (W // k, H // k), interpolation=cv2.INTER_AREA)
    if method == "farneback":
        F = cv2.calcOpticalFlowFarneback(ga, gb, None, 0.5, 5, 31, 10, 7, 1.5, 0)
    else:
        dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
        F = dis.calc(ga, gb, None)
    if limit > 0:
        mag = np.sqrt((F ** 2).sum(2, keepdims=True)) * k
        F = F * np.minimum(1.0, limit * H / np.maximum(mag, 1e-6))
    if smooth > 0:
        F = cv2.GaussianBlur(F, (0, 0), smooth / k * H / 1080.0)
    if k > 1:
        F = cv2.resize(F, (W, H), interpolation=cv2.INTER_LINEAR) * k
    return F

def morph(A, B, progress=None, method="dis", smooth=28.0, limit=0.12, ease=True):
    """A morph between two runs of frames of the same length (A's tail, B's head, both moving). Each frame the flow
    is measured both ways between A's and B's frames; A is pushed the share t of the way toward B and B the rest of the
    way back toward A, and the two are crossfaded by t in linear light. progress: t per frame (default 0 to 1 across
    the run, eased by smoothstep when ease). smooth: px at 1080 the flow is blurred by, so unrelated pictures melt
    into each other rather than tear; limit: the longest push, as a share of the height. The first frame is A's own
    and the last is B's own."""
    n = len(A)
    if len(B) != n:
        raise ValueError("morph wants A and B of the same length")
    if progress is None:
        t = np.linspace(0.0, 1.0, n)
        if ease:
            t = t * t * (3 - 2 * t)
    else:
        t = envelope(progress, n)
    H, W = A[0].shape[:2]
    gx, gy = _grid(H, W)
    out = []
    for i in range(n):
        u = float(t[i])
        if u <= 0:
            out.append(A[i].copy())
            continue
        if u >= 1:
            out.append(B[i].copy())
            continue
        Fab = _flow(A[i], B[i], method, smooth, limit)
        Fba = _flow(B[i], A[i], method, smooth, limit)
        a = cv2.remap(lin(A[i]), gx - u * Fab[..., 0], gy - u * Fab[..., 1], cv2.INTER_LINEAR,
                      borderMode=cv2.BORDER_REFLECT)
        b = cv2.remap(lin(B[i]), gx - (1 - u) * Fba[..., 0], gy - (1 - u) * Fba[..., 1], cv2.INTER_LINEAR,
                      borderMode=cv2.BORDER_REFLECT)
        out.append(disp(a * (1 - u) + b * u))
    return out

FX = {
    "feedback": feedback, "feedback_bubble": feedback_bubble, "feedback_distort": feedback_distort,
    "time_displace": time_displace, "trails": trails, "trails_diffuse": trails_diffuse,
    "time_average": time_average, "random_edits": random_edits, "reverse_edits": reverse_edits,
    "get_frame": get_frame, "looper": looper, "posterize_time": posterize_time, "jitter_basic": jitter_basic,
    "jitter": jitter, "morph": morph,
}
