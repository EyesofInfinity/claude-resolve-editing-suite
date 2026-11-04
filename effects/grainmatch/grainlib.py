"""Grain analysis for Develop Grain Match. MIT License.

Measures a clip's grain as Resolve's DCTL sees it: Rec.709 display values (gamma 2.4), R'G'B' 0 to 1, at the analysis
height (the timeline's height, 1080 by default). Grain is measured in Y'CbCr (BT.709 weights) built from those R'G'B'
values, so luma grain and colour grain are read apart, and R, G, B figures come from the same covariance.

The grain is the part of the picture that changes from one frame to the next where the picture itself does not.
The frame is cut into square patches (48 px at 1080). Each patch has its shading (a quadratic surface per component)
taken out. For two consecutive frames, half the variance of the difference of a patch's residuals is its moving grain:
  - where the scene is static, texture and edges cancel in the difference, so a textured patch reads grain alone;
  - where the camera moves, a flat patch (sky, wall, fog, defocus) carries no picture to move, so it reads grain alone;
  - a textured patch that moves reads high and falls out, because each band's grain is a low quantile (the 25th) of
    its patches, corrected for the spread pure grain of the measured coarseness shows (computed by simulation).
Patches the codec copied from the frame before (a difference of exactly zero) are counted and left out. Patches near
clipping are left out. The patches within 1.6 times the band level are the grain patches; colour, coarseness,
correlation and blocking are read over them.

What is reported (codes are 8-bit code units, display value x 255):
  bands      per brightness band (tents centred at display luma 0.15, 0.45, 0.80: shadows, mids, highlights; between
             centres the tents mix the band variances, the rule the DCTL uses): the moving grain's standard deviation
             in Y', Cb, Cr and R, G, B, and its correlations. A band with fewer than MIN_PATCHES grain patches is not
             measured and takes its nearest measured neighbour's figures (said in notes).
  acf        the grain's lag-1 and lag-2 correlation (x and y averaged) for Y', Cb and Cr: how coarse it is.
  corr       the correlation between the Y', Cb and Cr grain (and R, G, B) over all bands.
  hold       the same-place correlation of the residual between consecutive frames in the grain patches: 0 is grain
             new every frame; near 1 is a still structure (picture micro-texture, or grain the codec froze).
  static_sd_y  the residual's whole standard deviation in the grain patches (moving plus still), for reference.
  copied     the share of usable patch pairs the codec copied unchanged.
  blocking   compression block edges' energy over the blocks' insides, on the native 8 px grid (1 is none).
"""
import json, math, subprocess
import numpy as np

BANDS = (0.15, 0.45, 0.80)
BAND_NAMES = ("shadows", "mids", "highlights")
KR, KB = 0.2126, 0.0722
KG = 1.0 - KR - KB
PATCH_1080 = 48
MIN_PATCHES = 40
QUANT = 0.25
Z_QUANT = -0.6745
GRAIN_BAND = 1.6
MOVE_KEEP = 0.6

def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,pix_fmt,r_frame_rate,codec_name:format=duration",
                        "-of", "json", path], capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    s = j["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    fps = float(num) / float(den) if float(den) else 25.0
    dur = float(j.get("format", {}).get("duration", 0) or 0)
    return {"w": int(s["width"]), "h": int(s["height"]), "pix": s.get("pix_fmt", ""), "fps": fps, "dur": dur,
            "codec": s.get("codec_name", "")}

def decode(path, start=None, n=24, height=1080, info=None):
    """n frames from start seconds (None: centred in the clip) as float32 (H, W, 3) display values."""
    info = info or probe(path)
    if start is None:
        start = max(0.0, info["dur"] / 2 - n / info["fps"] / 2) if info["dur"] else 0.0
    rgb_src = info["pix"].startswith(("gbr", "rgb", "bgr", "argb", "rgba", "bgra", "abgr"))
    W, H = info["w"], info["h"]
    vf = []
    if height and H != height:
        W = int(round(W * height / H / 2)) * 2
        H = height
        vf.append(f"scale={W}:{H}:flags=bicubic")
    if not rgb_src:
        vf.append("scale=in_color_matrix=bt709:in_range=tv:flags=bicubic+accurate_rnd+full_chroma_int")
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-i", path, "-frames:v", str(n)]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-pix_fmt", "rgb48le", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint16)
    k = fr.size // (W * H * 3)
    if k == 0:
        raise RuntimeError(f"no frames decoded from {path}")
    fr = fr[:k * W * H * 3].reshape(k, H, W, 3).astype(np.float32) / 65535.0
    return [f for f in fr], {"start": round(start, 3), "frames": k, "w": W, "h": H, "native_h": info["h"],
                            "pix": info["pix"], "codec": info["codec"], "fps": round(info["fps"], 3)}

def to_ycc(img):
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    y = KR * r + KG * g + KB * b
    return np.stack([y, (b - y) / (2 * (1 - KB)), (r - y) / (2 * (1 - KR))], -1)

def ycc_to_rgb_matrix():
    """M such that rgb = M @ ycc (BT.709)."""
    return np.array([[1, 0, 2 * (1 - KR)],
                     [1, -2 * (1 - KB) * KB / KG, -2 * (1 - KR) * KR / KG],
                     [1, 2 * (1 - KB), 0]], np.float64)

def tents(y):
    """Weights of the three band tents at display luma y (constant beyond the end centres); sums to 1."""
    y = np.asarray(y, np.float64)
    c0, c1, c2 = BANDS
    w0 = np.clip((c1 - y) / (c1 - c0), 0, 1)
    w2 = np.clip((y - c1) / (c2 - c1), 0, 1)
    w1 = 1 - w0 - w2
    return np.stack([w0, w1, w2], -1)

def _basis(P):
    u = (np.arange(P) - (P - 1) / 2) / P
    X, Y = np.meshgrid(u, u)
    B = np.stack([np.ones_like(X), X, Y, X * X, X * Y, Y * Y], -1).reshape(-1, 6)
    Q, _ = np.linalg.qr(B)
    return Q

def patches(img, P):
    """(N, P*P, C) patches on a grid of non-overlapping squares, the grid centred in the frame, and their origins."""
    H, W, C = img.shape
    ny, nx = H // P, W // P
    oy, ox = (H - ny * P) // 2, (W - nx * P) // 2
    a = img[oy:oy + ny * P, ox:ox + nx * P].reshape(ny, P, nx, P, C).transpose(0, 2, 1, 3, 4).reshape(ny * nx, P * P, C)
    ys, xs = np.meshgrid(oy + np.arange(ny) * P, ox + np.arange(nx) * P, indexing="ij")
    return a, np.stack([ys.ravel(), xs.ravel()], -1)

def detrend(a, Q):
    """a (N, P*P, C): residual after the quadratic surface per patch and component."""
    coef = np.matmul(Q.T, a)
    return a - np.matmul(Q, coef)

def patch_acf(r, P):
    """Lag-1 and lag-2 correlation (x and y averaged) of detrended residuals r (N, P*P)."""
    r = r.reshape(-1, P, P)
    m = lambda x: np.mean(x, dtype=np.float64)
    v0 = m(r * r)
    if v0 <= 0:
        return float("nan"), float("nan")
    a1 = 0.5 * (m(r[:, :, 1:] * r[:, :, :-1]) + m(r[:, 1:] * r[:, :-1])) / v0
    a2 = 0.5 * (m(r[:, :, 2:] * r[:, :, :-2]) + m(r[:, 2:] * r[:, :-2])) / v0
    return float(a1), float(a2)

def gaussian_field(shape, s, rng):
    """Unit-variance white noise blurred by a Gaussian of sigma s px (s <= 0.05: white)."""
    z = rng.standard_normal(shape)
    if s <= 0.05:
        return z
    from scipy.ndimage import gaussian_filter
    f = gaussian_filter(z, s, mode="wrap")
    return f / f.std()

_GT = {}

def _gauss_acf_table(P):
    if P not in _GT:
        rng = np.random.default_rng(3)
        Q = _basis(P)
        rows = []
        for s in [0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.7, 2.0, 2.5, 3.0, 4.0, 5.0]:
            f = gaussian_field((P * 12, P * 12), s, rng)
            a, _ = patches(f[..., None], P)
            rows.append((s, patch_acf(detrend(a, Q)[..., 0], P)[0]))
        _GT[P] = np.array(rows)
    return _GT[P]

def sigma_for_acf1(acf1, P):
    """The Gaussian blur sigma whose filtered white noise shows this lag-1 correlation after the quadratic detrend
    in a P x P patch (a table by simulation)."""
    table = _gauss_acf_table(P)
    acf1 = float(np.clip(acf1, table[0, 1], table[-1, 1]))
    return float(np.interp(acf1, table[:, 1], table[:, 0]))

_SPREAD_CACHE = {}

def pure_spread(P, acf1, n=600):
    """For pure grain whose detrended lag-1 correlation in a P x P patch is acf1: the relative spread (sd of patch
    variance / mean) and the mean factor (detrended variance / true variance). By simulation, cached."""
    acf1 = 0.3 if not acf1 == acf1 else acf1
    key = (P, round(float(acf1), 2))
    if key in _SPREAD_CACHE:
        return _SPREAD_CACHE[key]
    s = sigma_for_acf1(acf1, P)
    rng = np.random.default_rng(7)
    Q = _basis(P)
    side = int(math.ceil(math.sqrt(n))) * P
    f = gaussian_field((side, side), s, rng).astype(np.float64)
    a, _ = patches(f[..., None], P)
    r = detrend(a, Q)[..., 0]
    v = r.var(1) * (P * P) / (P * P - 6)
    out = (float(v.std() / v.mean()), float(v.mean()))
    _SPREAD_CACHE[key] = out
    return out

def _motion_keep(y0, y1, P, dis):
    """Per patch: the variance of (frame 1 warped onto frame 0 by DIS optical flow) - frame 0, over the variance of
    the plain difference, on the luma planes y0, y1 (float32)."""
    import cv2
    g0 = np.clip(y0 * 255 + 0.5, 0, 255).astype(np.uint8)
    g1 = np.clip(y1 * 255 + 0.5, 0, 255).astype(np.uint8)
    fl = dis.calc(g0, g1, None)
    H, W = y0.shape
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    w1 = cv2.remap(y1, gx + fl[..., 0], gy + fl[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    a, _ = patches(np.stack([y1 - y0, w1 - y0], -1), P)
    a = a - a.mean(1, keepdims=True)
    v = (a * a).sum(1, dtype=np.float64)
    return v[:, 1] / (v[:, 0] + 1e-30)

def analyze(frames, meta=None, patch=None, breaks=()):
    """frames: float (H, W, 3) display values in time order. breaks: indices t where frame t + 1 does not follow
    frame t (the start of a new stretch), so that pair is skipped."""
    meta = dict(meta or {})
    breaks = set(breaks)
    H, W, _ = frames[0].shape
    scale = H / 1080.0
    P = patch or max(16, int(round(PATCH_1080 * scale / 4)) * 4)
    Q = _basis(P).astype(np.float32)
    nfr = len(frames)
    if nfr < 2:
        raise ValueError("grain is read from frame differences: give at least 2 frames")
    dof = P * P - 6
    res, ym, ok, pos, ys = [], [], [], None, []
    for f in frames:
        f = np.asarray(f, np.float32)
        c = to_ycc(f)
        ys.append(np.ascontiguousarray(c[..., 0]))
        a, pos = patches(np.concatenate([c, f], -1), P)
        res.append(detrend(a, Q))
        ym.append(a[:, :, 0].mean(1))
        lo = (a[:, :, 3:] <= 0.003).mean((1, 2))
        hi = (a[:, :, 3:] >= 0.997).mean((1, 2))
        ok.append((ym[-1] > 0.035) & (ym[-1] < 0.965) & (lo < 0.002) & (hi < 0.002))
    npp = len(ym[0])

    D, S, XY, YM, PAIR, IDX, MOV = [], [], [], [], [], [], []
    import cv2
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    for t in range(nfr - 1):
        v = ok[t] & ok[t + 1]
        if t in breaks or not v.any():
            continue
        a, b = res[t][v], res[t + 1][v]
        d = b - a
        MOV.append(_motion_keep(ys[t], ys[t + 1], P, dis)[v])
        f8 = np.float64
        D.append((d * d).sum(1, dtype=f8) / dof / 2)
        S.append(0.5 * ((a * a).sum(1, dtype=f8) + (b * b).sum(1, dtype=f8)) / dof)
        XY.append((a[:, :, 0] * b[:, :, 0]).sum(1, dtype=f8) / dof)
        YM.append(0.5 * (ym[t][v] + ym[t + 1][v]))
        PAIR.append(np.full(v.sum(), t)); IDX.append(np.where(v)[0])
    if not D:
        return _empty(meta, P, nfr, "no usable patches (the frames are clipped or empty)")
    D, S, XY, YM = np.concatenate(D), np.concatenate(S), np.concatenate(XY), np.concatenate(YM)
    PAIR, IDX, MOV = np.concatenate(PAIR), np.concatenate(IDX), np.concatenate(MOV)
    copied = D[:, 0] < (0.02 / 255) ** 2
    moving = (MOV < MOVE_KEEP) & ~copied
    live = ~copied & ~moving
    band_of = np.argmax(tents(YM), -1)

    def diff_of(sel):
        """the frame differences (M, P*P, 6) of the selected pairs"""
        out = []
        for t in np.unique(PAIR[sel]):
            ii = IDX[sel & (PAIR == t)]
            out.append(res[t + 1][ii] - res[t][ii])
        return np.concatenate(out) if out else np.zeros((0, P * P, 6))

    seed = np.zeros(len(D), bool)
    for b in range(3):
        idx = np.where(live & (band_of == b))[0]
        if idx.size >= 4:
            seed[idx[D[idx, 0] <= np.quantile(D[idx, 0], QUANT)]] = True
    acf1 = patch_acf(diff_of(seed)[:, :, 0], P)[0] if seed.sum() >= 3 else 0.3
    grain = np.zeros(len(D), bool)
    level = [float("nan")] * 3
    for it in range(2):
        spread, mfac = pure_spread(P, acf1)
        grain[:] = False
        for b in range(3):
            idx = np.where(live & (band_of == b))[0]
            if idx.size < MIN_PATCHES:
                continue
            q = np.quantile(D[idx, 0], QUANT) / max(0.2, 1 + Z_QUANT * spread)
            level[b] = q / mfac
            grain[idx[D[idx, 0] <= GRAIN_BAND * q]] = True
        if grain.sum() >= 3:
            acf1 = patch_acf(diff_of(grain)[:, :, 0], P)[0]
    count = np.array([int((grain & (band_of == b)).sum()) for b in range(3)])
    measured = [bool(count[b] >= MIN_PATCHES) for b in range(3)]

    comps = ["Y", "Cb", "Cr", "R", "G", "B"]
    band_cov = np.full((3, 6, 6), np.nan)
    acf = {}
    spec = None
    if grain.sum() >= 3:
        dg = diff_of(grain)
        order = np.concatenate([np.where(grain & (PAIR == t))[0] for t in np.unique(PAIR[grain])])
        Wt = tents(YM[order])
        cov_p = np.matmul(dg.transpose(0, 2, 1).astype(np.float64), dg.astype(np.float64)) / dof / 2
        A = Wt.T @ Wt + 1e-12 * np.eye(3)
        band_cov = np.linalg.solve(A, np.einsum("nb,ncd->bcd", Wt, cov_p).reshape(3, -1)).reshape(3, 6, 6) / mfac
        for k, nm in ((0, "y"), (1, "cb"), (2, "cr")):
            a1, a2 = patch_acf(dg[:, :, k], P)
            acf[nm + "1"], acf[nm + "2"] = round(a1, 3), round(a2, 3)
        T = np.vstack([np.eye(3), ycc_to_rgb_matrix()])
        edges = np.linspace(0.035, 0.965, 17)
        lev = np.full((3, 3), np.nan)
        for k, nm in ((0, "y"), (1, "cb"), (2, "cr")):
            sp_k, mf_k = pure_spread(P, acf[nm + "1"])
            ys_, qs_, ws_ = [], [], []
            for i in range(16):
                idx = np.where(live & (YM >= edges[i]) & (YM < edges[i + 1]))[0]
                if idx.size < max(8, MIN_PATCHES // 4):
                    continue
                ys_.append(YM[idx].mean())
                qs_.append(np.quantile(D[idx, k], QUANT) / max(0.2, 1 + Z_QUANT * sp_k) / mf_k)
                ws_.append(idx.size)
            if len(ys_) >= 1:
                Wb = tents(np.array(ys_)) * np.sqrt(np.array(ws_, np.float64))[:, None]
                rhs = np.array(qs_) * np.sqrt(np.array(ws_, np.float64))
                lev[:, k] = np.linalg.solve(Wb.T @ Wb + 1e-9 * np.eye(3) * (Wb.T @ Wb).trace(), Wb.T @ rhs)
        for b in range(3):
            if not np.isfinite(lev[b]).all():
                continue
            C3 = band_cov[b][:3, :3]
            d3 = np.sqrt(np.clip(np.diag(C3), 1e-30, None))
            R3 = C3 / np.outer(d3, d3)
            sd3 = np.sqrt(np.clip(lev[b], 0, None))
            band_cov[b] = T @ (R3 * np.outer(sd3, sd3)) @ T.T
        r = dg[:, :, 0].reshape(-1, P, P)
        win = np.outer(np.hanning(P), np.hanning(P))
        Fm = (np.abs(np.fft.fft2(r * win)) ** 2).mean(0)
        fr = np.hypot(np.fft.fftfreq(P)[None, :], np.fft.fftfreq(P)[:, None])
        edges = np.linspace(0, 0.5, 9)
        spec = [float(Fm[(fr >= edges[i]) & (fr < edges[i + 1])].mean()) for i in range(8)]
        spec = [round(s / sum(spec), 4) for s in spec]
    for b in range(3):
        if not measured[b]:
            near = [j for j in sorted(range(3), key=lambda j: abs(j - b)) if measured[j]]
            band_cov[b] = band_cov[near[0]] if near else np.nan

    def corrs(C):
        dg_ = np.clip(np.diag(C), 0, None)
        c = C / np.sqrt(np.outer(dg_, dg_) + 1e-30)
        return {"Y_Cb": round(float(c[0, 1]), 3), "Y_Cr": round(float(c[0, 2]), 3), "Cb_Cr": round(float(c[1, 2]), 3),
                "R_G": round(float(c[3, 4]), 3), "R_B": round(float(c[3, 5]), 3), "G_B": round(float(c[4, 5]), 3)}

    per = {}
    for b in range(3):
        sd = np.sqrt(np.clip(np.diag(band_cov[b]), 0, None)) * 255
        per[BAND_NAMES[b]] = {"centre": BANDS[b], "measured": measured[b], "grain_patches": int(count[b]),
                              "patches": int((live & (band_of == b)).sum()),
                              "level_y": round(math.sqrt(level[b]) * 255, 3) if level[b] == level[b] else None,
                              "sd": {c: round(float(sd[i]), 3) for i, c in enumerate(comps)},
                              "corr": corrs(band_cov[b])}
    wsum = count.astype(np.float64)
    if wsum.sum() > 0 and np.isfinite(band_cov).all():
        Cw = np.einsum("b,bcd->cd", wsum, band_cov) / wsum.sum()
        corr_all = corrs(Cw)
    else:
        corr_all = None

    flat = np.zeros(len(D), bool)
    for b in range(3):
        idx = np.where(grain & (band_of == b))[0]
        if idx.size >= 4:
            flat[idx[S[idx, 0] <= GRAIN_BAND * np.quantile(S[idx, 0], QUANT)]] = True
    hold = float(XY[flat].sum() / S[flat, 0].sum()) if flat.sum() >= 3 and S[flat, 0].sum() > 0 else float("nan")
    static_sd = math.sqrt(S[flat, 0].mean()) * 255 if flat.sum() >= 3 else float("nan")

    block = float("nan")
    if grain.sum() >= 3 and meta.get("native_h", H) == H:
        num = den = 0.0
        nb = ni = 0
        sel = np.where(grain)[0][:4000]
        cache = {}
        for j in sel:
            t, i = PAIR[j], IDX[j]
            if t not in cache:
                y = ys[t].astype(np.float64)
                cache = {t: (np.diff(y, axis=1) ** 2, np.diff(y, axis=0) ** 2)}
            dx, dy = cache[t]
            py, px = pos[i]
            sx = dx[py:py + P, px:px + P - 1]
            sy = dy[py:py + P - 1, px:px + P]
            colx = (px + np.arange(P - 1)) % 8 == 7
            rowy = (py + np.arange(P - 1)) % 8 == 7
            num += sx[:, colx].sum() + sy[rowy, :].sum()
            nb += sx[:, colx].size + sy[rowy, :].size
            den += sx[:, ~colx].sum() + sy[~rowy, :].sum()
            ni += sx[:, ~colx].size + sy[~rowy, :].size
        if den > 0:
            block = float((num / nb) / (den / ni))

    usable = int(len(D))
    grain_frac = float(grain.sum() / max(1, live.sum()))
    notes = []
    for b in range(3):
        if not measured[b]:
            notes.append(f"{BAND_NAMES[b]}: too few grain patches ({int(count[b])} of {P} px over {nfr - 1} frame "
                         f"pairs, {MIN_PATCHES} needed): filled from the nearest measured band")
    if not any(measured):
        notes.append("no band could be measured: the clip has too little flat or still area to tell grain from picture")
    if grain_frac < 0.15 and any(measured):
        notes.append(f"only {grain_frac:.0%} of the usable patches read as grain (flat or still): the figures are "
                     f"an upper bound")
    if copied.mean() > 0.3:
        notes.append(f"the codec copied {copied.mean():.0%} of patch pairs unchanged: grain there is frozen and "
                     f"was not counted")
    if block == block and block > 1.25:
        notes.append(f"compression blocking: block edges carry {block:.2f}x the energy of the block insides")
    if hold == hold and hold > 0.6:
        notes.append(f"hold {hold:.2f}: most of the fine structure in the flat areas stays still from frame to frame "
                     f"(picture texture or grain the codec froze); only the moving part is matched")
    out = {"analysis_height": H, "frames": nfr, "patch": P, "bands": per, "corr": corr_all,
           "acf": acf, "spectrum_y": spec,
           "gauss_size_y": round(sigma_for_acf1(acf["y1"], P) / scale, 3) if acf else None,
           "gauss_size_c": round(sigma_for_acf1(0.5 * (acf["cb1"] + acf["cr1"]), P) / scale, 3) if acf else None,
           "hold": round(hold, 3) if hold == hold else None,
           "static_sd_y": round(static_sd, 3) if static_sd == static_sd else None,
           "copied": round(float(copied.mean()), 3), "moving_picture": round(float(moving.mean()), 3),
           "grain_fraction": round(grain_frac, 3),
           "grain_patches": int(grain.sum()), "usable_patch_pairs": usable,
           "blocking": round(block, 3) if block == block else None, "notes": notes}
    out.update({k: v for k, v in meta.items() if k not in out})
    return out

def _empty(meta, P, nfr, why):
    out = {"analysis_height": None, "frames": nfr, "patch": P, "bands": None, "notes": [why]}
    out.update(meta)
    return out

def analyze_file(path, start=None, n=24, height=1080, stretches=1):
    """Read n frames: from start (seconds) as one stretch, or, with start None and stretches k > 1, as k stretches
    of n // k frames spread evenly over the clip (one stretch: the clip's middle)."""
    if start is not None or stretches <= 1:
        frames, meta = decode(path, start, n, height)
        meta["path"] = path
        return analyze(frames, meta)
    info = probe(path)
    m = max(2, n // stretches)
    span = max(0.0, info["dur"] - m / info["fps"] - 0.2)
    frames, breaks, starts, meta = [], [], [], None
    for i in range(stretches):
        s = 0.1 + span * (i + 0.5) / stretches
        f, meta = decode(path, s, m, height, info)
        if frames:
            breaks.append(len(frames) - 1)
        frames += f
        starts.append(round(s, 2))
    meta.update({"path": path, "start": starts, "frames": len(frames)})
    return analyze(frames, meta, breaks=breaks)
