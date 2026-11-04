"""Develop Particles camera match: one command, a shot in and a baked DCTL out, so the particles move
with the scene when the camera moves.

    python -I effects/particles/camera.py <shot or b-roll catalog idx> <out folder> [--start s] [--dur s]
        [--name text] [--no-depth] [--json-only]

It writes, for the shot:
  Develop Particles - <name>.dctl        the plain DCTL with the shot's camera path baked in
  Develop Particles Depth - <name>.dctl  the same for the depth version
  <name>.camera.json                     the analysis: the path, the fit's quality, its cost, the drift numbers

How it measures the camera. Each pair of frames gets dense optical flow (OpenCV DIS, as Develop Time FX's morph
uses), checked forward against backward, kept only where the picture has texture. Each frame gets a depth map from
Depth Anything V2 Small (Apache-2.0, on the GPU, near white, put on Develop Depth's scale: the nearest 0.5% of the
picture 1, the farthest 0.5% 0). The flow is then fitted, robustly (a Tukey fit throws out fire, water and people),
by a camera that turns and moves:

    flow = t_R + q t_T + (z_R + q z_T) (x - c) + roll J (x - c)

where q is the depth (disparity) at the point. t_R, z_R and roll are what a pan, a tilt, a zoom and a roll do: the
same at every depth. t_T and z_T are what a truck, a crane or a dolly does: more the nearer the thing is. So a
particle at disparity q moves exactly as the scene's own points at that disparity do: near layers shift more than
far ones. With a flat or featureless scene the depth part falls to nothing and every layer moves with the plate.

The per-frame moves are chained into a path from the shot's first frame, for three disparities (0, 0.8 and 1.6);
the DCTL interpolates in q between them (quadratic) and in time between samples. Values are at 1080 rows (the DCTL
scales them), times in seconds, so one bake plays on any timeline rate. The table stays under 14000 floats (56 KB,
the 64 KB of constant memory a CUDA kernel has, as effects/beat/bake.py found): a long shot is sampled every second
or third frame.

In Resolve: put the baked DCTL on the shot (Edit page OpenFX > ResolveFX Color > DCTL, or a DCTL plugin node), set
Shot Start s to where the shot's analysed first frame sits on the timeline (seconds from the timeline's first frame)
and Frame Rate to the timeline's rate. Source X and Y (sparks, embers) are read on the shot's first frame.

MIT License. Copyright (c) 2026 the Claude Resolve Editing Suite authors.
"""
import json
import os
import re
import subprocess
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render as rd

AW, AH = 960, 540
UNIT = 1080.0 / AH
QS = (0.0, 0.8, 1.6)
PER = 10
BUDGET = 14000
META_N = 32
DA_MODEL = "depth-anything/Depth-Anything-V2-Small-hf"

def arg(a, name, default):
    return a[a.index(name) + 1] if name in a else default

def stream(path, start, n, W=AW, H=AH):
    """Frames from start, fitted into W x H as Resolve fits a clip (letterboxed), as rgb24, one at a time."""
    vf = (f"scale={W}:{H}:in_color_matrix=bt709:in_range=tv:force_original_aspect_ratio=decrease,"
          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2")
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{start:.4f}", "-i", path]
    if n:
        cmd += ["-frames:v", str(n)]
    cmd += ["-vf", vf, "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = W * H * 3
    while True:
        b = p.stdout.read(size)
        if len(b) < size:
            break
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
    p.stdout.close()
    p.wait()

class Depther:
    """Depth Anything V2 Small on the GPU: relative disparity, near high, put on Develop Depth's scale per frame."""

    def __init__(self):
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        import torch
        from transformers import AutoModelForDepthEstimation
        self.torch = torch
        self.dev = "cuda" if torch.cuda.is_available() else "cpu"
        self.dt = torch.float16 if self.dev == "cuda" else torch.float32
        try:
            self.model = AutoModelForDepthEstimation.from_pretrained(DA_MODEL, local_files_only=True).to(self.dev, self.dt).eval()
        except OSError:
            sys.exit(f"the depth model is not downloaded (about 99 MB). Run: hf download {DA_MODEL}. Or pass --no-depth.")
        self.mean = torch.tensor([0.485, 0.456, 0.406], device=self.dev).view(1, 3, 1, 1)
        self.std = torch.tensor([0.229, 0.224, 0.225], device=self.dev).view(1, 3, 1, 1)

    def __call__(self, rgb, box):
        torch = self.torch
        F = torch.nn.functional
        H, W = rgb.shape[:2]
        h = 518
        w = int(round(W * h / H / 14.0)) * 14
        with torch.no_grad():
            x = torch.from_numpy(np.ascontiguousarray(rgb)).to(self.dev).permute(2, 0, 1)[None].float() / 255.0
            x = F.interpolate(x, size=(h, w), mode="bicubic", align_corners=False).clamp(0, 1)
            x = ((x - self.mean) / self.std).to(self.dt)
            d = self.model(pixel_values=x).predicted_depth
            d = F.interpolate(d[:, None].float(), size=(H, W), mode="bilinear", align_corners=False)[0, 0]
        d = d.cpu().numpy()
        v = d[box[0]:box[1]:4, ::4].ravel()
        lo, hi = np.percentile(v, 0.5), np.percentile(v, 99.5)
        return np.clip((d - lo) / max(1e-6, hi - lo), 0.0, 1.0).astype(np.float32)

def content_rows(rgb):
    m = rgb.max(axis=(1, 2))
    rows = np.nonzero(m > 6)[0]
    return (int(rows[0]), int(rows[-1]) + 1) if len(rows) else (0, rgb.shape[0])

def samples(ga, gb, dis, box, stride=6):
    """Flow from ga to gb at a grid, kept where forward and backward agree and the picture has texture.
    Returns points (analysis px), flows (analysis px) and the texture weight."""
    H, W = ga.shape
    ff = dis.calc(ga, gb, None)
    fb = dis.calc(gb, ga, None)
    m = 10
    ys, xs = np.mgrid[max(box[0], 0) + m:min(box[1], H) - m:stride, m:W - m:stride]
    xs, ys = xs.ravel().astype(np.float32), ys.ravel().astype(np.float32)
    f = ff[ys.astype(int), xs.astype(int)]
    xb, yb = xs + f[:, 0], ys + f[:, 1]
    inside = (xb >= 0) & (xb < W - 1) & (yb >= box[0]) & (yb < box[1] - 1)
    bx = cv2.remap(fb[..., 0], xb.reshape(1, -1), yb.reshape(1, -1), cv2.INTER_LINEAR).ravel()
    by = cv2.remap(fb[..., 1], xb.reshape(1, -1), yb.reshape(1, -1), cv2.INTER_LINEAR).ravel()
    err = np.hypot(f[:, 0] + bx, f[:, 1] + by)
    eig = cv2.cornerMinEigenVal(ga, 7)[ys.astype(int), xs.astype(int)]
    ok = inside & (err < 0.5)
    if ok.sum() > 50:
        thr = np.percentile(eig[ok], 35)
        ok &= eig >= thr
    return np.stack([xs[ok], ys[ok]], 1), f[ok], np.sqrt(eig[ok] + 1e-9)

LK = dict(winSize=(21, 21), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))

def samples_lk(ga, gb, box, n=1500):
    """Corners (Shi-Tomasi) tracked from ga to gb (pyramidal Lucas-Kanade), kept where the track back lands home."""
    H, W = ga.shape
    mask = np.zeros((H, W), np.uint8)
    mask[box[0] + 10:box[1] - 10, 10:W - 10] = 1
    p0 = cv2.goodFeaturesToTrack(ga, n, 0.005, 8, mask=mask, blockSize=7)
    if p0 is None:
        return np.zeros((0, 2), np.float32), np.zeros((0, 2), np.float32), np.zeros(0)
    p1, st, _ = cv2.calcOpticalFlowPyrLK(ga, gb, p0, None, **LK)
    pb, st2, _ = cv2.calcOpticalFlowPyrLK(gb, ga, p1, None, **LK)
    p0, p1, pb = p0.reshape(-1, 2), p1.reshape(-1, 2), pb.reshape(-1, 2)
    ok = (st.ravel() == 1) & (st2.ravel() == 1) & (np.hypot(*(pb - p0).T) < 0.25)
    ok &= (p1[:, 0] > 2) & (p1[:, 0] < W - 2) & (p1[:, 1] > box[0] + 2) & (p1[:, 1] < box[1] - 2)
    return p0[ok], (p1 - p0)[ok], np.ones(int(ok.sum()))

def fit(pts, flow, q, w0, depth=True):
    """The camera move between two frames from the flow at points with disparity q, at 1080 rows:
    (tRx, tRy, zR, roll, tTx, tTy, zT). Robust: Huber, then Tukey. Returns the move, the inlier share, the
    residual's spread (px)."""
    cx, cy = AW / 2.0, AH / 2.0
    dx, dy = (pts[:, 0] - cx) * UNIT, (pts[:, 1] - cy) * UNIT
    fx, fy = flow[:, 0] * UNIT, flow[:, 1] * UNIT
    n = len(dx)
    one, zero = np.ones(n), np.zeros(n)
    qm = float(np.average(q, weights=w0))
    qc = q - qm
    Ax = np.stack([one, zero, dx, -dy, qc, zero, qc * dx], 1)
    Ay = np.stack([zero, one, dy, dx, zero, qc, qc * dy], 1)
    A = np.concatenate([Ax, Ay])
    y = np.concatenate([fx, fy])
    wt = np.concatenate([w0, w0])
    wt = wt / wt.mean()
    k = 7 if depth else 4
    A = A[:, :k]
    lam = np.zeros(k)
    if depth:
        lam[4:] = 2 * n * 0.0004 * np.array([1.0, 1.0, 500.0 ** 2])
    w = wt.copy()
    p = np.zeros(k)
    sig = 1.0
    for it in range(8):
        Aw = A * w[:, None]
        p = np.linalg.solve(A.T @ Aw + np.diag(lam) + 1e-9 * np.eye(k), Aw.T @ y)
        r = y - A @ p
        rr = np.hypot(r[:n], r[n:])
        sig = max(1.4826 * np.median(rr), 0.05)
        rr2 = np.concatenate([rr, rr])
        if it < 3:
            c = 1.5 * sig
            w = wt * np.where(rr2 <= c, 1.0, c / np.maximum(rr2, 1e-9))
        else:
            c = 4.685 * sig
            w = wt * np.where(rr2 < c, (1 - (rr2 / c) ** 2) ** 2, 0.0)
    inl = float(np.mean(rr < 4.685 * sig))
    out = np.zeros(7)
    out[:k] = p
    out[0] -= qm * out[4]
    out[1] -= qm * out[5]
    out[2] -= qm * out[6]
    return out, inl, float(sig)

GK = np.linspace(0.0, 1.0, 11)

def gmap(q, gk, slope):
    """The depth curve: the map's disparity q to how much the scene at q moves (0 at the farthest, 1 at the nearest),
    straight on past the nearest thing."""
    q = np.asarray(q, dtype=np.float64)
    return np.where(q <= 1.0, np.interp(q, GK, gk), gk[-1] + slope * (q - 1.0))

def depth_curve(S, moves, log=print):
    """A depth map from a network is not straight in disparity: its far end is squeezed or stretched. How much the
    scene moves at each depth, across the frames where the camera's move shows depth, gives the curve back. Each
    point's own disparity is read off its flow along the depth part of the move; a curve through the knots is fitted
    to it (robust, smooth, never falling), then set so 0 stays 0 and 1 stays 1. A shot that shows no depth keeps the
    straight line."""
    qs, es, ws = [], [], []
    for (d, f, q, w0), m in zip(S, moves):
        if d is None:
            continue
        tx = m[4] + m[6] * d[:, 0]
        ty = m[5] + m[6] * d[:, 1]
        t2 = tx * tx + ty * ty
        if np.median(t2) < 0.3 ** 2:
            continue
        rx = m[0] + m[2] * d[:, 0] - m[3] * d[:, 1]
        ry = m[1] + m[2] * d[:, 1] + m[3] * d[:, 0]
        e = ((f[:, 0] - rx) * tx + (f[:, 1] - ry) * ty) / np.maximum(t2, 1e-6)
        qs.append(q)
        es.append(e)
        ws.append(w0 * t2)
    if not qs:
        log("  depth curve: the camera shows no depth; straight")
        return GK.copy(), 1.0, 0.0
    q, e, w = np.concatenate(qs), np.concatenate(es), np.concatenate(ws)
    ok = np.isfinite(e) & (np.abs(e) < 4.0)
    q, e, w = q[ok], e[ok], w[ok]
    B = np.maximum(0.0, 1.0 - np.abs(q[:, None] - GK[None, :]) / 0.1)
    D2 = np.diff(np.eye(len(GK)), 2, axis=0)
    wr = w.copy()
    sw = w.sum()
    for _ in range(6):
        Bw = B * wr[:, None]
        g = np.linalg.solve(B.T @ Bw + 0.02 * sw * D2.T @ D2 + 1e-9 * sw * np.eye(len(GK)), Bw.T @ e)
        r = e - B @ g
        s = max(1.4826 * np.median(np.abs(r)), 0.02)
        wr = w * np.minimum(1.0, 1.5 * s / np.maximum(np.abs(r), 1e-9))
    g = np.maximum.accumulate(g)
    if g[-1] - g[0] < 0.2:
        log("  depth curve: too flat to trust; straight")
        return GK.copy(), 1.0, float(sw)
    g = (g - g[0]) / (g[-1] - g[0])
    slope = float(np.clip((g[-1] - g[-4]) / 0.3, 0.3, 3.0))
    log("  depth curve: " + " ".join(f"{v:.2f}" for v in g) + f", past 1 at slope {slope:.2f}")
    return g, slope, float(sw)

def analyse(path, start, dur, use_depth=True, log=print):
    fps = rd.fps_of(path)
    n = int(round(dur * fps)) if dur else 0
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    dep = Depther() if use_depth else None
    t0 = time.time()
    t_depth = t_flow = t_fit = 0.0
    grays, depths, S = [], [], []
    box = None
    prev = None
    for i, rgb in enumerate(stream(path, start, n)):
        if box is None:
            box = content_rows(rgb)
        g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        ta = time.time()
        if dep is not None:
            d = dep(rgb, box)
        else:
            d = np.full((AH, AW), 0.5, np.float32)
        t_depth += time.time() - ta
        grays.append(g)
        depths.append(cv2.resize(d, (AW // 4, AH // 4), interpolation=cv2.INTER_AREA).astype(np.float16))
        if prev is not None:
            ta = time.time()
            if "lk" in os.environ.get("CAM_EXP", ""):
                pts, fl, wv = samples_lk(prev[0], g, box)
            else:
                pts, fl, wv = samples(prev[0], g, dis, box)
            t_flow += time.time() - ta
            if len(pts) >= 120:
                q = prev[1][pts[:, 1].astype(int), pts[:, 0].astype(int)].astype(np.float64)
                dd = np.stack([(pts[:, 0] - AW / 2.0) * UNIT, (pts[:, 1] - AH / 2.0) * UNIT], 1)
                S.append((dd, fl * UNIT, q, wv))
            else:
                S.append((None, None, None, None))
        prev = (g, d)
    nf = len(grays)
    if nf < 2:
        sys.exit(f"{path}: {nf} frames read")

    def fit_all(gk, slope):
        mv, inl, sg, qsp, cnt = [], [], [], [], []
        for d, f, q, w0 in S:
            if d is None:
                mv.append(mv[-1].copy() if mv else np.zeros(7))
                inl.append(0.0); sg.append(0.0); qsp.append(0.0); cnt.append(0)
                continue
            gq = gmap(q, gk, slope)
            m, a, s = fit(d / UNIT + [AW / 2.0, AH / 2.0], f / UNIT, gq, w0, dep is not None)
            mv.append(m); inl.append(a); sg.append(s); cnt.append(len(q))
            qsp.append(float(np.percentile(q, 90) - np.percentile(q, 10)))
        return np.array(mv), inl, sg, qsp, cnt

    ta = time.time()
    moves, inliers, sigmas, qspread, counts = fit_all(GK, 1.0)
    gk, slope, gw = GK.copy(), 1.0, 0.0
    if dep is not None and "straight" not in os.environ.get("CAM_EXP", ""):
        gk, slope, gw = depth_curve(S, moves, log)
        moves, inliers, sigmas, qspread, counts = fit_all(gk, slope)
    t_fit += time.time() - ta
    if use_depth and len(moves) > 5 and "nosmooth" not in os.environ.get("CAM_EXP", ""):
        k = cv2.getGaussianKernel(7, 1.5).ravel()
        sm = moves.copy()
        for j in (4, 5, 6):
            sm[:, j] = np.convolve(np.pad(moves[:, j], 3, mode="edge"), k, mode="valid")
        qm = 0.5
        sm[:, 0] += (moves[:, 4] - sm[:, 4]) * qm
        sm[:, 1] += (moves[:, 5] - sm[:, 5]) * qm
        sm[:, 2] += (moves[:, 6] - sm[:, 6]) * qm
        moves = sm
    total = time.time() - t0
    log(f"analysed {nf} frames in {total:.1f} s (depth {t_depth:.1f} s, flow {t_flow:.1f} s, fit {t_fit:.1f} s)")
    return {"fps": fps, "frames": nf, "box": box, "moves": moves, "inliers": np.array(inliers),
            "sigma": np.array(sigmas), "qspread": np.array(qspread), "count": np.array(counts),
            "grays": grays, "depths": depths, "depth": bool(use_depth), "gk": gk, "slope": slope,
            "cost": {"total_s": total, "depth_s": t_depth, "flow_s": t_flow, "fit_s": t_fit}}

def integrate(moves, qs=QS):
    """The path from the first frame for each disparity in qs: (frames, len(qs), 3) of tx, ty (1080 px) and log
    scale, and the roll (frames,). A point at disparity q at screen x on the first frame is at
    c + exp(ls) R(roll) (x - c) + (tx, ty) on frame k."""
    nf = len(moves) + 1
    out = np.zeros((nf, len(qs), 3))
    roll = np.zeros(nf)
    for j, q in enumerate(qs):
        s, T, ph = 1.0, np.zeros(2), 0.0
        for k, m in enumerate(moves):
            a = 1.0 + m[2] + q * m[6]
            th = m[3]
            c, sn = np.cos(th), np.sin(th)
            T = a * np.array([c * T[0] - sn * T[1], sn * T[0] + c * T[1]]) + np.array([m[0] + q * m[4], m[1] + q * m[5]])
            s *= a
            ph += th
            out[k + 1, j] = (T[0], T[1], np.log(s))
            roll[k + 1] = ph
    return out, roll

def pack(path3, roll, fps, gk=GK, slope=1.0, budget=BUDGET):
    nf = len(roll)
    step = 1
    while (nf + step - 1) // step * PER + META_N > budget:
        step += 1
    idx = list(range(0, nf, step))
    tab = []
    for i in idx:
        for j in range(3):
            tab += [float(path3[i, j, 0]), float(path3[i, j, 1]), float(path3[i, j, 2])]
        tab.append(float(roll[i]))
    rate = fps / step
    corner = np.hypot(960.0, 540.0)
    vmax, smin = [], []
    for j in range(3):
        v = np.hypot(np.diff(path3[:, j, 0]), np.diff(path3[:, j, 1])) + corner * (
            np.abs(np.diff(path3[:, j, 2])) + np.abs(np.diff(roll)))
        vmax.append(float(np.max(v) * fps) if len(v) else 0.0)
        smin.append(float(np.exp(np.min(path3[:, j, 2]))))
    meta = [len(idx), rate, fps, QS[0], QS[1], QS[2], vmax[0], vmax[1], vmax[2], smin[0], smin[1], smin[2],
            float(step), float(nf), float(slope), 0.0] + [float(v) for v in gk] + [0.0] * (META_N - 16 - len(gk))
    return meta, tab, idx

def cam_g(meta, q):
    """What the DCTL decodes (particles.h camG): the depth curve at the map's disparity q."""
    if q <= 1.0:
        x = max(q, 0.0) * 10.0
        i = min(int(np.floor(x)), 9)
        return meta[16 + i] + (meta[17 + i] - meta[16 + i]) * (x - i)
    return meta[26] + meta[14] * (q - 1.0)

def cam_at(meta, tab, ts, q, amt=1.0):
    """What the DCTL decodes (particles.h camAt): (tx, ty, log scale, roll) at shot time ts for the map's disparity
    q (the depth curve first, then the path's three samples)."""
    n = int(meta[0])
    if n < 2:
        return np.zeros(4)
    x = min(max(ts * meta[1], 0.0), n - 1.0)
    i = min(int(np.floor(x)), n - 2)
    f = x - i
    q0, q1, q2 = meta[3], meta[4], meta[5]
    qq = min(max(cam_g(meta, q), q0), q2)
    w0 = (qq - q1) * (qq - q2) / ((q0 - q1) * (q0 - q2))
    w1 = (qq - q0) * (qq - q2) / ((q1 - q0) * (q1 - q2))
    w2 = (qq - q0) * (qq - q1) / ((q2 - q0) * (q2 - q1))
    out = np.zeros(4)
    for k in range(3):
        a = tab[i * PER + k] * w0 + tab[i * PER + 3 + k] * w1 + tab[i * PER + 6 + k] * w2
        b = tab[(i + 1) * PER + k] * w0 + tab[(i + 1) * PER + 3 + k] * w1 + tab[(i + 1) * PER + 6 + k] * w2
        out[k] = a + (b - a) * f
    out[3] = tab[i * PER + 9] + (tab[(i + 1) * PER + 9] - tab[i * PER + 9]) * f
    return out * amt

def fwd(cm, x, y, cx=960.0, cy=540.0):
    s, c, sn = np.exp(cm[2]), np.cos(cm[3]), np.sin(cm[3])
    ux, uy = x - cx, y - cy
    return cx + s * (c * ux - sn * uy) + cm[0], cy + s * (sn * ux + c * uy) + cm[1]

def inv(cm, x, y, cx=960.0, cy=540.0):
    s, c, sn = np.exp(cm[2]), np.cos(cm[3]), np.sin(cm[3])
    ux, uy = x - cx - cm[0], y - cy - cm[1]
    return cx + (c * ux + sn * uy) / s, cy + (-sn * ux + c * uy) / s

def drift(A, meta, tab, spans_s=(0.5, 1.0, 2.0, 4.0), every_s=0.5, log=print):
    """Long feature tracks (Shi-Tomasi corners and pyramidal Lucas-Kanade, each step checked back, independent of
    the dense flow the path was fitted on) against the path: for each track from frame a to frame b, where the
    path puts the point (at its own depth) and where the picture puts it, in px at 1080. Also the same for a
    particle locked to the screen and for one moving with the plate's mean motion but no depth."""
    G, D, fps = A["grays"], A["depths"], A["fps"]
    box = A["box"]
    nf = len(G)
    lk = dict(winSize=(21, 21), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    mask = np.zeros((AH, AW), np.uint8)
    mask[box[0] + 12:box[1] - 12, 12:AW - 12] = 1
    errs = {s: {"match": [], "locked": [], "flat": []} for s in spans_s}
    maxspan = int(round(max(spans_s) * fps))
    for a in range(0, nf - 1, max(1, int(round(every_s * fps)))):
        p0 = cv2.goodFeaturesToTrack(G[a], 500, 0.01, 12, mask=mask)
        if p0 is None:
            continue
        p0 = p0.reshape(-1, 2)
        q = D[a].astype(np.float32)[np.clip((p0[:, 1] / 4).astype(int), 0, AH // 4 - 1),
                                    np.clip((p0[:, 0] / 4).astype(int), 0, AW // 4 - 1)]
        cur, alive = p0.copy(), np.ones(len(p0), bool)
        want = {int(round(s * fps)): s for s in spans_s}
        for b in range(a + 1, min(nf, a + maxspan + 1)):
            nx, st, _ = cv2.calcOpticalFlowPyrLK(G[b - 1], G[b], cur.reshape(-1, 1, 2), None, **lk)
            bk, st2, _ = cv2.calcOpticalFlowPyrLK(G[b], G[b - 1], nx, None, **lk)
            nx, bk = nx.reshape(-1, 2), bk.reshape(-1, 2)
            alive &= (st.ravel() == 1) & (st2.ravel() == 1) & (np.hypot(*(bk - cur).T) < 0.3)
            alive &= (nx[:, 0] > 4) & (nx[:, 0] < AW - 4) & (nx[:, 1] > box[0] + 4) & (nx[:, 1] < box[1] - 4)
            cur = nx
            if b - a in want and alive.sum() >= 10:
                s = want[b - a]
                ta, tb = a / fps, b / fps
                for k in np.nonzero(alive)[0]:
                    x0, y0 = p0[k] * UNIT
                    x1, y1 = cur[k] * UNIT
                    wx, wy = inv(cam_at(meta, tab, ta, float(q[k])), x0, y0)
                    px, py = fwd(cam_at(meta, tab, tb, float(q[k])), wx, wy)
                    wx, wy = inv(cam_at(meta, tab, ta, 0.5), x0, y0)
                    fx, fy = fwd(cam_at(meta, tab, tb, 0.5), wx, wy)
                    errs[s]["match"].append((float(q[k]), px - x1, py - y1))
                    errs[s]["locked"].append((float(q[k]), x0 - x1, y0 - y1))
                    errs[s]["flat"].append((float(q[k]), fx - x1, fy - y1))
            if not alive.any():
                break

    def layer(e, bands=None):
        e = np.array(e)
        tot, wsum = 0.0, 0
        for lo in np.arange(0.0, 1.0, 0.2):
            m = (e[:, 0] >= lo) & (e[:, 0] < lo + 0.2 + (1e-6 if lo >= 0.8 else 0.0))
            if m.sum() >= 5:
                v = np.hypot(np.median(e[m, 1]), np.median(e[m, 2]))
                tot += m.sum() * v
                wsum += m.sum()
                if bands is not None:
                    bands.append([round(float(lo), 1), int(m.sum()), round(float(np.median(e[m, 1])), 2),
                                  round(float(np.median(e[m, 2])), 2)])
        return round(float(tot / max(wsum, 1)), 2)

    out = {}
    for s, e in errs.items():
        if not e["match"]:
            continue
        m = np.hypot(*np.array(e["match"])[:, 1:].T)
        lo = np.hypot(*np.array(e["locked"])[:, 1:].T)
        fl = np.hypot(*np.array(e["flat"])[:, 1:].T)
        bands = []
        r = {"tracks": int(len(m)),
             "layer_match_px": layer(e["match"], bands), "layer_locked_px": layer(e["locked"]),
             "bands_q_n_dx_dy": bands,
             "layer_one_depth_px": layer(e["flat"]),
             "point_match_median_px": round(float(np.median(m)), 2),
             "point_match_p90_px": round(float(np.percentile(m, 90)), 2),
             "point_locked_median_px": round(float(np.median(lo)), 2),
             "point_one_depth_median_px": round(float(np.median(fl)), 2)}
        out[f"{s:g}s"] = r
        log(f"  over {s:g} s ({len(m)} tracks): a depth layer slides {r['layer_match_px']} px against the plate with "
            f"the match ({r['layer_one_depth_px']} px at one depth, {r['layer_locked_px']} px locked to the screen); "
            f"single points {r['point_match_median_px']} px median")
    return out

def fnum(v):
    s = f"{float(v):.7g}"
    if "e" in s or "E" in s:
        s = f"{float(v):.9f}".rstrip("0")
    if "." not in s:
        s += ".0"
    return s + "f"

def data_block(meta, tab, shot=""):
    lines, cur = [], []
    for v in tab:
        cur.append(fnum(v))
        if len(cur) == 10:
            lines.append(", ".join(cur))
            cur = []
    if cur:
        lines.append(", ".join(cur))
    return "\n".join([
        "// PC_DATA_BEGIN",
        f"// Develop Particles' camera path, baked by effects/particles/camera.py from {shot or 'a shot'}: {int(meta[13])} "
        f"frames at {meta[2]:.3f} fps, {int(meta[0])} samples. MIT License.",
        "// meta: samples, samples a second, shot fps, the three depths baked, the most px a second at each, the least",
        "// scale at each, frames per sample, frames, the depth curve's slope past 1, a spare, the depth curve at the",
        "// map's disparity 0, 0.1 to 1, five spare",
        f"__CONSTANT__ float PC_META[{META_N}] = {{ " + ", ".join(fnum(v) for v in meta) + " };",
        f"__CONSTANT__ float PC_CAM[{len(tab)}] = {{\n    " + ",\n    ".join(lines) + " };",
        "// PC_DATA_END"])

def put_data(text, block):
    a, b = text.index("// PC_DATA_BEGIN"), text.index("// PC_DATA_END") + len("// PC_DATA_END")
    return text[:a] + block + text[b:]

def set_default(text, name, val):
    pat = re.compile(r"(DEFINE_UI_PARAMS\(\s*" + re.escape(name) + r"\s*,[^,]+,\s*DCTLUI_SLIDER_FLOAT\s*,\s*)([-0-9.]+)")
    if not pat.search(text):
        raise SystemExit(f"no slider {name}")
    v = f"{float(val):g}"
    return pat.sub(lambda m: m.group(1) + v + ("" if "." in v else ".0"), text, count=1)

def shot_name(path):
    base = os.path.splitext(os.path.basename(path))[0]
    return re.sub(r"[^A-Za-z0-9 _-]+", "", base).strip()[:40] or "shot"

def bake(meta, tab, out, name, fps, shot=""):
    made = []
    for fam in ("Develop Particles", "Develop Particles Depth"):
        src = os.path.join(HERE, "build", f"{fam}.dctl")
        t = open(src, encoding="utf-8").read()
        t = put_data(t, data_block(meta, tab, shot))
        t = set_default(t, "ptFps", round(fps, 3))
        dst = os.path.join(out, f"{fam} - {name}.dctl")
        open(dst, "w", encoding="utf-8", newline="\n").write(t)
        made.append(dst)
    return made

def main():
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    src, out = rd.clip(a[0]), os.path.abspath(a[1])
    start, dur = float(arg(a, "--start", "0")), float(arg(a, "--dur", "0"))
    name = arg(a, "--name", None) or shot_name(src)
    os.makedirs(out, exist_ok=True)
    A = analyse(src, start, dur, "--no-depth" not in a)
    path3, roll = integrate(A["moves"])
    meta, tab, idx = pack(path3, roll, A["fps"], A["gk"], A["slope"])
    t0 = time.time()
    dr = drift(A, meta, tab)
    t_drift = time.time() - t0
    made = [] if "--json-only" in a else bake(meta, tab, out, name, A["fps"], os.path.basename(src))
    m = A["moves"]
    rep = {"shot": src, "start_s": start, "frames": A["frames"], "fps": A["fps"], "depth": A["depth"],
           "samples": int(meta[0]), "frames_per_sample": int(meta[12]), "table_floats": len(tab) + META_N,
           "cost_s": {k: round(v, 2) for k, v in A["cost"].items()}, "drift_check_s": round(t_drift, 2),
           "fit": {"inlier_share_median": round(float(np.median(A["inliers"])), 3),
                   "residual_px_median": round(float(np.median(A["sigma"])) * 1.0, 3),
                   "points_median": int(np.median(A["count"])),
                   "depth_spread_median": round(float(np.median(A["qspread"])), 3)},
           "path_end": {"q0": [round(v, 2) for v in path3[-1, 0]], "q0.8": [round(v, 2) for v in path3[-1, 1]],
                        "q1.6": [round(v, 2) for v in path3[-1, 2]], "roll_deg": round(float(np.degrees(roll[-1])), 3)},
           "speed_px_s": [round(v, 1) for v in meta[6:9]],
           "parallax_share": round(float(np.median(np.hypot(m[:, 4], m[:, 5]) / (np.hypot(m[:, 0], m[:, 1]) + np.hypot(m[:, 4], m[:, 5]) + 1e-6))), 3),
           "drift": dr, "dctl": made}
    jp = os.path.join(out, f"{name}.camera.json")
    json.dump({**rep, "meta": meta, "moves": A["moves"].round(5).tolist()}, open(jp, "w", encoding="utf-8"), indent=1)
    print(json.dumps(rep, indent=1))

if __name__ == "__main__":
    main()
