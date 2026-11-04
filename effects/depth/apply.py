"""Develop Depth on a clip: the picture and its depth pass in, one effect, a 1080p H.264 file out.

usage: python -I apply.py <clip or catalog idx> <out.mp4> --fx <name> [--start s] [--dur s] [--depth pass.mov]
           [--in s] [--out s] [--strength 1] [--refine 4] [--<argument> value ...]
       python -I apply.py --list

--depth is the pass depth_pass.py rendered for exactly this start and length; without it the pass is made now (Resolve
must be running with the test project open) and kept in tests/out/depth/pass. Arguments of the effect are given by
name (--aperture_px 30 --blades 6). --focus is a depth (0.4), a point of the frame (0.5,0.6: the depth there,
followed through the clip), or omitted for the frame's middle. rack pulls focus from --focus to --focus_to over
--rack_dur s from --rack_at s. depth_wipe takes --b <clip or idx> --bstart s, with --pre and --post seconds of clean
picture around it, and --wipe_dur s; it works inside the pictures (bars stay out of it), takes --norm and --refine
(default 0 for the wipe, as it was judged) and refuses --strength, --in and --out (a transition has no amount).
"""
import inspect
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import depthfx as dx
import develop_paths

def _timefx_apply():
    """Time FX's reader and writer (the same fit, tags and rate), loaded under its own name: both files are apply.py."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("timefx_apply", os.path.join(REPO, "effects", "timefx", "apply.py"))
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.join(REPO, "effects", "timefx"))
    spec.loader.exec_module(m)
    sys.path.pop(0)
    return m

ta = _timefx_apply()

PASS_DIR = os.path.join(REPO, "tests", "out", "depth", "pass")
FX = {"defocus": dx.defocus, "zblur": dx.defocus, "rack": dx.defocus, "haze": dx.haze, "zglow": dx.zglow,
      "depth_wipe": dx.depth_wipe}
WHAT = {"defocus": "a lens's depth of field, with aperture shapes",
        "zblur": "blur that grows with distance from a plane",
        "rack": "focus pulled from one plane to another",
        "haze": "air between the camera and the far scene",
        "zglow": "the scene's lights glowing at a chosen depth",
        "depth_wipe": "a transition that peels the shot away from the camera outward"}
OWN = {"--fx", "--start", "--dur", "--depth", "--in", "--out", "--strength", "--refine", "--focus", "--focus_to",
       "--rack_at", "--rack_dur", "--focus_smooth", "--link", "--drive", "--drive_focus", "--b", "--bstart", "--bdepth", "--pre", "--post", "--wipe_dur", "--crf", "--norm"}

def ta_catalog():
    """The footage index (tools/develop_paths.py), or None."""
    return develop_paths.broll_catalog()

def clip_path(s):
    return develop_paths.clip_from_index(s) if s.isdigit() else os.path.abspath(s)

def depth_frames(src, start, n, given):
    """The depth pass for n frames from start, made by Resolve when not given; returns n x H x W float (near 1)."""
    if not given:
        stem = os.path.splitext(os.path.basename(src))[0][:40]
        given = os.path.join(PASS_DIR, f"{stem}_{start:.2f}_{n}.mov")
        if not os.path.exists(given):
            fps = ta.probe_fps(src)
            subprocess.run([sys.executable, "-I", os.path.join(HERE, "depth_pass.py"), src, given, "--start",
                            f"{start}", "--dur", f"{n / fps:.6f}"], check=True)
    p = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", given, "-frames:v", str(n), "-pix_fmt", "rgb48le",
                        "-f", "rawvideo", "-"], capture_output=True, check=True)
    d = np.frombuffer(p.stdout, np.uint16).reshape(-1, ta.H, ta.W, 3)[..., 0]
    if d.shape[0] < n:
        sys.exit(f"the depth pass {given} holds {d.shape[0]} frames, {n} wanted")
    return d.astype(np.float32) / 65535.0

def content_box(frames):
    """The rows the picture fills (Resolve and ffmpeg letterbox a wide clip the same way): the bars are black in
    every frame."""
    m = np.max(np.stack([f.max(axis=(1, 2)) for f in frames[::max(1, len(frames) // 8)]]), axis=0)
    rows = np.nonzero(m > 3)[0]
    return (int(rows[0]), int(rows[-1]) + 1) if len(rows) else (0, ta.H)

def normalise(d, box):
    """One scale for the whole clip: the nearest 0.5% to 1, the farthest 0.5% to 0 (the AI map's range moves from
    clip to clip; within a clip it holds)."""
    y0, y1 = box
    v = d[:, y0:y1:4, ::4].ravel()
    lo, hi = np.percentile(v, 0.5), np.percentile(v, 99.5)
    return np.clip((d - lo) / max(1e-4, hi - lo), 0, 1)

def env(n, fps, ein, eout, strength):
    e = np.full(n, strength, dtype=np.float64)
    if ein > 0:
        e *= np.clip(np.arange(n) / (ein * fps), 0, 1)
    if eout > 0:
        e *= np.clip((n - 1 - np.arange(n)) / (eout * fps), 0, 1)
    return e

def cast(text, default):
    t = text.strip()
    if isinstance(default, bool):
        return t.lower() in ("1", "true", "yes", "on")
    if isinstance(default, (tuple, list)) or (default is None and "," in t):
        return tuple(float(x) for x in t.split(","))
    try:
        return int(t) if isinstance(default, int) and "." not in t else float(t)
    except ValueError:
        return t

def fx_args(fn, a):
    sig = inspect.signature(fn)
    out = {}
    for i in range(0, len(a) - 1):
        if a[i].startswith("--") and a[i] not in OWN and a[i][2:] in sig.parameters:
            out[a[i][2:]] = cast(a[i + 1], sig.parameters[a[i][2:]].default)
    unknown = [x for x in a if x.startswith("--") and x not in OWN and x[2:] not in sig.parameters]
    if unknown:
        sys.exit(f"not arguments of {fn.__name__}: {unknown}")
    return out

def arg(a, name, default):
    return a[a.index(name) + 1] if name in a else default

def focus_track(d, spec, box, k=0.15):
    """Focus for every frame: a fixed depth, or the depth at a point followed through the clip (smoothed by k a
    frame, so focus glides as a puller's does rather than twitching with the AI map; a jumping subject wants a
    smaller k)."""
    if spec and "," not in spec:
        return np.full(len(d), float(spec))
    x, y = (float(v) for v in spec.split(",")) if spec else (0.5, 0.5)
    y0, y1 = box
    raw = np.array([dx.focus_at(dx.dep(f[y0:y1]), x, y) for f in d])
    out = raw.copy()
    for i in range(1, len(raw)):
        out[i] = out[i - 1] + k * (raw[i] - out[i - 1])
    return out

def run(a):
    name = arg(a, "--fx", None)
    if name not in FX:
        sys.exit(f"--fx one of {sorted(FX)}")
    src, out = clip_path(a[0]), os.path.abspath(a[1])
    start, dur = float(arg(a, "--start", 0)), float(arg(a, "--dur", 3))
    fps = ta.probe_fps(src)
    crf = int(arg(a, "--crf", 18))
    fn = FX[name]
    kw = fx_args(fn, a)
    if name == "zblur":
        kw["gauss"] = True
    t0 = time.time()
    if name == "depth_wipe":
        return run_wipe(a, src, out, start, fps, crf, kw, t0)
    frames = ta.read(src, start, dur, "fit")
    n = len(frames)
    box = content_box(frames)
    y0, y1 = box
    d = depth_frames(src, start, n, arg(a, "--depth", None))
    if arg(a, "--norm", "1") == "1":
        d = normalise(d, box)
    e = env(n, fps, float(arg(a, "--in", 0)), float(arg(a, "--out", 0)), float(arg(a, "--strength", 1)))
    if arg(a, "--link", None):
        sys.path.insert(0, os.path.join(REPO, "effects", "audio", "link"))
        import analyse as al
        drv = al.drive(arg(a, "--link", None), arg(a, "--drive", "rms"), n)
        if name == "rack" and arg(a, "--drive_focus", "0") == "1":
            pass
        else:
            e = e * drv
    rf = int(arg(a, "--refine", 4))
    foc = None
    if name in ("defocus", "zblur", "rack"):
        foc = focus_track(d, arg(a, "--focus", None), box, float(arg(a, "--focus_smooth", 0.15)))
        if name == "rack":
            to = focus_track(d, arg(a, "--focus_to", "0.1"), box)
            at, rd = float(arg(a, "--rack_at", dur * 0.3)), float(arg(a, "--rack_dur", 1.0))
            u = np.array([dx.ease((k / fps - at) / max(1e-3, rd)) for k in range(n)])
            if arg(a, "--link", None) and arg(a, "--drive_focus", "0") == "1":
                u = drv
            foc = foc + (to - foc) * u
    res = []
    for k in range(n):
        f = frames[k]
        if e[k] <= 0:
            res.append(f)
            continue
        img = dx.lin(f[y0:y1])
        dd = dx.despeckle(dx.dep(d[k, y0:y1]))
        if name == "haze":
            dd = dx.islands_out(dd, 3)
        if rf > 0:
            dd = dx.refine(dd, dx.luma(img) ** (1 / 2.4), rf)
        if foc is not None:
            dd = dx.grow_near(dd, 2)
        rest = {x: v for x, v in kw.items() if x not in ("focus", "amount")}
        amt = float(e[k]) * float(kw.get("amount", inspect.signature(fn).parameters["amount"].default))
        if foc is not None:
            o = fn(img, dd, focus=float(foc[k]), amount=amt, **rest)
        else:
            o = fn(img, dd, amount=amt, **rest)
        g = f.copy()
        g[y0:y1] = dx.disp(o)
        res.append(g)
    ta.write(res, out, fps, crf)
    print(f"{name}: {n} frames in {time.time() - t0:.1f} s ({(time.time() - t0) / n:.2f} s a frame) -> {out}")

def wipe_frame(fa, fb, da, db, p, box_a, box_b, refine=0, **kw):
    """One frame of depth_wipe inside the pictures, as the other modes work inside theirs: fa, fb the frames (uint8
    HxWx3, bars and all), da, db their normalised depth (HxW), p the progress, box_a, box_b their picture rows. It
    runs on the rows either picture fills; each depth is despeckled (and refined, refine > 0) inside its own picture;
    a's blur reads only a's picture; where a has bars they give way first and where b has bars they pull nothing
    forward. Rows outside both pictures are bars in both and stay as they are. (the whole frame went in,
    and the blur drew the bars into the picture's edge rows.)"""
    if p <= 0:
        return fa
    if p >= 1:
        return fb
    import torch
    (a0, a1), (b0, b1) = box_a, box_b
    y0, y1 = min(a0, b0), max(a1, b1)
    far = bool(kw.get("far_first", False))

    def prep(f, d, r0, r1, bar):
        img = dx.lin(f[y0:y1])
        dd = torch.full(img.shape[1:], bar, device=dx.DEV)
        sub = dx.despeckle(dx.dep(d[r0:r1]))
        if refine > 0:
            sub = dx.refine(sub, dx.luma(img[:, r0 - y0:r1 - y0]) ** (1 / 2.4), refine)
        dd[r0 - y0:r1 - y0] = sub
        return img, dd

    A, dA = prep(fa, da, a0, a1, 0.0 if far else 1.0)
    B, dB = prep(fb, db, b0, b1, 1.0 if far else 0.0)
    o = dx.depth_wipe(A, B, dA, p, depth_b=dB, rows=(a0 - y0, a1 - y0), **kw)
    g = fa.copy()
    g[y0:y1] = dx.disp(o)
    return g

def run_wipe(a, src, out, start, fps, crf, kw, t0):
    given = [x for x in ("--strength", "--in", "--out") if x in a]
    if given:
        sys.exit(f"depth_wipe is a transition and has no amount: {', '.join(given)} do not apply (its timing is --pre, "
                 f"--wipe_dur, --post)")
    bsrc = clip_path(arg(a, "--b", None) or sys.exit("--b <clip> for depth_wipe"))
    bstart = float(arg(a, "--bstart", 0))
    pre, post, wd = float(arg(a, "--pre", 0.75)), float(arg(a, "--post", 0.75)), float(arg(a, "--wipe_dur", 1.25))
    n = int(round((pre + wd + post) * fps))
    fa = ta.read(src, start, 0, "fit", count=n)
    fb = ta.read(bsrc, bstart, 0, "fit", count=n)
    n = min(len(fa), len(fb))
    box_a, box_b = content_box(fa), content_box(fb)
    da = depth_frames(src, start, n, arg(a, "--depth", None))
    db = depth_frames(bsrc, bstart, n, arg(a, "--bdepth", None))
    if arg(a, "--norm", "1") == "1":
        da, db = normalise(da, box_a), normalise(db, box_b)
    rf = int(arg(a, "--refine", 0))
    k0, k1 = int(round(pre * fps)), int(round((pre + wd) * fps))
    res = []
    for k in range(n):
        p = (k - k0) / max(1, k1 - k0)
        res.append(wipe_frame(fa[k], fb[k], da[k], db[k], p, box_a, box_b, rf, **kw))
    ta.write(res, out, fps, crf)
    print(f"depth_wipe: {n} frames in {time.time() - t0:.1f} s -> {out}")

def main():
    a = sys.argv[1:]
    if not a or a[0] == "--list":
        for k, fn in FX.items():
            ps = [p for p in inspect.signature(fn).parameters if p not in ("img", "depth", "a", "b", "depth_a", "p")]
            print(f"{k:11s} {WHAT[k]}\n            {', '.join(ps)}")
        return
    run(a)

if __name__ == "__main__":
    main()
