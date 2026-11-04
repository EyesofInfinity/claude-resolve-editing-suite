"""Develop Light Comp on a clip: a generated light composited into the plate by its depth, a 1080p H.264 out.

usage: python -I apply.py <clip or catalog idx> <out.mp4> --light <name> [--start s] [--frames n | --dur s]
           [--depth pass.mov] [--at depth | x,y] [--set slider=value ...] [--progress a,b] [--frame0 k]
           [--in s] [--out s] [--strength 1] [--before before.mp4] [--sticker sticker.mp4] [--<comp argument> value]
       python -I apply.py --list

--light is one of layers.LIGHTS (the DCTL, its sliders, black or diff, scene or lens). --set changes the DCTL's own
sliders (--set lzHue=200 --set lzX0=10). --progress runs a Transition DCTL's progress from a to b over the shot (Glow
Dissolve's flare crossing). --at is the light's depth (0 far, 1 near) or a point of the frame whose depth it takes,
followed through the clip. The comp's own arguments (lightcomp.comp) by name: --spill 1 --rim 1 --reach 1 --occlude 0.03
--ramp 0 --defocus_px -1 --cast 0.35 --grain_amt 1 --air -1 --ambient 0 --gain 1 --knee 0.7 --kind scene|lens.
--depth defaults to the pass for this clip and start in tests/out/depth/pass (the main checkout's, then this one's).
--before writes the DCTL itself laid on the plate; --sticker the same light added over the plate and nothing else.
"""
import glob
import importlib.util
import inspect
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EFF = os.path.dirname(HERE)
REPO = os.path.dirname(EFF)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(EFF, "depth"))
import depthfx as dx
import layers as lay
import lightcomp as lc

def _depth_apply():
    spec = importlib.util.spec_from_file_location("depth_apply", os.path.join(EFF, "depth", "apply.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

da = _depth_apply()
ta = da.ta
sys.path.insert(0, os.path.join(REPO, "tools"))
import develop_paths
PASS_DIRS = [d for d in (develop_paths.setting("depth_pass_dir", "DEVELOP_DEPTH_PASS_DIR"),
                         os.path.join(REPO, "tests", "out", "depth", "pass")) if d]
OWN = {"--light", "--start", "--frames", "--dur", "--depth", "--at", "--set", "--progress", "--frame0", "--in", "--out",
       "--strength", "--before", "--sticker", "--crf", "--refine", "--seed"}

def find_pass(src, start, n):
    """The depth pass made for this clip from this start holding at least n frames (the shortest such)."""
    stem = os.path.splitext(os.path.basename(src))[0][:40]
    best = None
    for d in PASS_DIRS:
        for p in glob.glob(os.path.join(d, f"{glob.escape(stem)}_{start:.2f}_*.mov")):
            try:
                k = int(os.path.splitext(p)[0].rsplit("_", 1)[1])
            except ValueError:
                continue
            if k >= n and (best is None or k < best[0]):
                best = (k, p)
    if best is None:
        sys.exit(f"no depth pass for {stem} from {start:.2f} s with {n} frames in {PASS_DIRS}")
    return best[1]

def comp_args(a):
    sig = inspect.signature(lc.comp).parameters
    out = {}
    for i in range(len(a) - 1):
        if a[i].startswith("--") and a[i] not in OWN:
            k = a[i][2:]
            if k not in sig or k in ("plate_u8", "D", "E", "pl", "at", "frame", "parts", "amount"):
                sys.exit(f"not an argument of the comp: {a[i]}")
            v = a[i + 1]
            out[k] = v if k == "kind" else float(v)
    return out

def at_track(d, spec, box):
    """The light's depth for every frame: a fixed depth, or the depth at a point followed (smoothed) through the clip,
    with a shift after it (x,y,shift: -0.05 puts the light just behind what stands there)."""
    if "," not in spec:
        return np.full(len(d), float(spec))
    v = spec.split(",")
    shift = float(v[2]) if len(v) > 2 else 0.0
    return np.clip(da.focus_track(d, ",".join(v[:2]), box, 0.15) + shift, 0, 1)

def render(src, start, n, light, at="0.5", sets=None, progress=None, frame0=236, depth=None, kw=None, env=None,
           want_before=False, want_sticker=False, refine=4, seed=0, log=None, frames=None):
    """The comp over n frames of a clip (or over the given frames, read from the clip at start as Resolve fits it);
    returns (after, before or None, sticker or None, info)."""
    kw = dict(kw or {})
    if frames is None:
        frames = ta.read(src, start, 0, "fit", count=n)
    n = len(frames)
    box = da.content_box(frames)
    y0, y1 = box
    dpath = depth or find_pass(src, start, n)
    d = da.normalise(da.depth_frames(src, start, n, dpath), box)
    name = light
    kind = kw.pop("kind", lay.LIGHTS[name][3])
    pick = np.linspace(0, n - 1, min(5, n)).astype(int)
    dd_cache = {}

    def depth_of(k):
        if k not in dd_cache:
            img = dx.lin(frames[k][y0:y1])
            dd = dx.despeckle(dx.dep(d[k, y0:y1]))
            if refine > 0:
                dd = dx.refine(dd, dx.luma(img) ** (1 / 2.4), refine)
            dd_cache.clear()
            dd_cache[k] = dd
        return dd_cache[k]

    pl = lc.Plate([frames[k][y0:y1] for k in pick], [depth_of(k).cpu().numpy() for k in pick])
    ats = at_track(d, at, box)
    env = np.ones(n) if env is None else env
    after, bef, stk = [], [], []
    for k in range(n):
        f = frames[k]
        pr = None
        if progress is not None:
            p0, p1 = progress
            pr = p0 + (p1 - p0) * (k / max(1, n - 1))
        E = lay.layer(name, frame0 + k, f, sets, pr)[:, y0:y1]
        D = depth_of(k)
        o = lc.comp(f[y0:y1], D, E, pl, at=float(ats[k]), kind=kind, amount=float(env[k]), frame=frame0 + k,
                    seed=seed, **kw)
        g = f.copy()
        g[y0:y1] = o
        after.append(g)
        if want_before:
            bef.append(lay.before(name, frame0 + k, f, sets, pr))
        if want_sticker:
            s = f.copy()
            s[y0:y1] = lc.over(f[y0:y1], E, float(env[k]))
            stk.append(s)
        if log:
            log(k)
    info = {"plate": pl.summary(), "box": box, "depth": dpath, "at": [round(float(x), 3) for x in ats[::max(1, n // 6)]],
            "kind": kind}
    return after, (bef or None), (stk or None), info

def main():
    a = sys.argv[1:]
    if not a or a[0] == "--list":
        for k, v in lay.LIGHTS.items():
            print(f"{k:9s} {v[2]:5s} {v[3]:5s} {v[4]}  sliders {v[1]}")
        return
    src, out = da.clip_path(a[0]), os.path.abspath(a[1])
    arg = lambda k, dflt: a[a.index(k) + 1] if k in a else dflt
    light = arg("--light", None)
    if light not in lay.LIGHTS:
        sys.exit(f"--light one of {sorted(lay.LIGHTS)}")
    start = float(arg("--start", 0))
    fps = ta.probe_fps(src)
    n = int(arg("--frames", 0)) or int(round(float(arg("--dur", 2)) * fps))
    sets = {}
    for i in range(len(a) - 1):
        if a[i] == "--set":
            k, v = a[i + 1].split("=")
            sets[k] = float(v)
    progress = tuple(float(x) for x in arg("--progress", "").split(",")) if "--progress" in a else None
    e = da.env(n, fps, float(arg("--in", 0)), float(arg("--out", 0)), float(arg("--strength", 1)))
    t0 = time.time()
    after, bef, stk, info = render(src, start, n, light, arg("--at", "0.5"), sets, progress, int(arg("--frame0", 236)),
                                   arg("--depth", None), comp_args(a), e, "--before" in a, "--sticker" in a,
                                   int(arg("--refine", 4)), int(arg("--seed", 0)))
    crf = int(arg("--crf", 16))
    ta.write(after, out, fps, crf)
    if bef:
        ta.write(bef, os.path.abspath(arg("--before", "")), fps, crf)
    if stk:
        ta.write(stk, os.path.abspath(arg("--sticker", "")), fps, crf)
    info.update({"out": out, "light": light, "frames": len(after), "seconds": round(time.time() - t0, 1)})
    print(json.dumps(info))

if __name__ == "__main__":
    main()
