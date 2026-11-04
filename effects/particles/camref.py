"""Develop Particles camera match: reads a baked DCTL's camera path back and holds it against what camera.py wrote
. check.mjs runs it; it also runs on its own:

    python -I effects/particles/camref.py <baked.dctl> <name.camera.json> [<out.json>]
    python -I effects/particles/camref.py --synth <out folder>     (two made-up paths baked, see synth)
    python -I effects/particles/camref.py --rebake <baked.dctl> ... (onto the current build, see rebake)

It checks, and prints one line each:
  1. the baked DCTL is the current build with only the data block and the Frame Rate default changed;
  2. PC_META in the DCTL is the json's meta (to the 7 digits the DCTL carries);
  3. PC_CAM in the DCTL is the path the json's per-frame moves integrate to (camera.py integrate and pack), within
     what the json's rounding of the moves (5 decimals) allows, and its last sample is the json's path_end;
  4. no NaN or infinity in either table.
With <out.json> it writes camera.py's own decoding of the DCTL's tables (cam_at, fwd, inv) at a grid of shot times
and depths, for check.mjs to hold the DCTL's decoder (camAt, camFwd, camInv in particles.h) against.
Exit 1 when a check fails. MIT License.
"""
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import camera as cm

def floats(text, name):
    m = re.search(r"__CONSTANT__ float " + name + r"\[(\d+)\] = \{([^}]*)\};", text)
    vals = [float(v.strip().rstrip("f")) for v in m.group(2).split(",") if v.strip()]
    if len(vals) != int(m.group(1)):
        raise SystemExit(f"{name}: {len(vals)} values for [{m.group(1)}]")
    return np.array(vals)

def strip(text):
    a, b = text.index("// PC_DATA_BEGIN"), text.index("// PC_DATA_END") + len("// PC_DATA_END")
    t = text[:a] + text[b:]
    return re.sub(r"(DEFINE_UI_PARAMS\(\s*ptFps\s*,[^,]+,\s*DCTLUI_SLIDER_FLOAT\s*,\s*)([-0-9.]+)", r"\g<1>X", t)

def synth(out):
    """Two made-up camera paths baked through camera.py's own pack and bake, for check.mjs: synth_pan, a pan of 40 px
    right and 20 px up a frame (at 1080 rows) at every depth; synth_par, a truck of 10 q px right a frame, so a layer
    at disparity q slides 10 q px a frame (near layers more). 97 frames at 24 fps, no zoom, no roll."""
    os.makedirs(out, exist_ok=True)
    nf = 97
    k = np.arange(nf, dtype=np.float64)
    for name, mv in (("synth_pan", lambda q: (40.0, -20.0)), ("synth_par", lambda q: (10.0 * q, 0.0))):
        p3 = np.zeros((nf, 3, 3))
        for j, q in enumerate(cm.QS):
            ax, ay = mv(q)
            p3[:, j, 0] = ax * k
            p3[:, j, 1] = ay * k
        meta, tab, _ = cm.pack(p3, np.zeros(nf), 24.0)
        for f in cm.bake(meta, tab, out, name, 24.0, name):
            print(f)

def rebake(paths):
    """A baked DCTL moved onto the current build: its camera data block and Frame Rate default carried over as they
    are (no new analysis), the rest the build's. For after particles.h changes."""
    for p in paths:
        t = open(p, encoding="utf-8").read()
        a, b = t.index("// PC_DATA_BEGIN"), t.index("// PC_DATA_END") + len("// PC_DATA_END")
        fps = re.search(r"DEFINE_UI_PARAMS\(\s*ptFps\s*,[^,]+,\s*DCTLUI_SLIDER_FLOAT\s*,\s*([-0-9.]+)", t).group(1)
        fam = "Develop Particles Depth" if "Particles Depth - " in os.path.basename(p) else "Develop Particles"
        build = open(os.path.join(HERE, "build", f"{fam}.dctl"), encoding="utf-8").read()
        nt = cm.set_default(cm.put_data(build, t[a:b]), "ptFps", float(fps))
        open(p, "w", encoding="utf-8", newline="\n").write(nt)
        print(f"rebaked {p}")

def main():
    a = sys.argv[1:]
    if a and a[0] == "--synth":
        synth(a[1])
        return
    if a and a[0] == "--rebake":
        rebake(a[1:])
        return
    dctl, jp = a[0], a[1]
    out = a[2] if len(a) > 2 else None
    text = open(dctl, encoding="utf-8").read()
    J = json.load(open(jp, encoding="utf-8"))
    fails = 0

    def ok(name, cond, info):
        nonlocal fails
        print(f"{'pass' if cond else 'FAIL'} {name} {info}")
        if not cond:
            fails += 1

    fam = "Develop Particles Depth" if "Particles Depth - " in os.path.basename(dctl) else "Develop Particles"
    build = open(os.path.join(HERE, "build", f"{fam}.dctl"), encoding="utf-8").read()
    ok(f"{os.path.basename(dctl)}: the current build with only the camera data and Frame Rate changed",
       strip(text) == strip(build), "")
    meta, tab = floats(text, "PC_META"), floats(text, "PC_CAM")
    ok("tables finite", bool(np.isfinite(meta).all() and np.isfinite(tab).all()), f"meta {len(meta)}, path {len(tab)}")
    jm = np.array(J["meta"], dtype=np.float64)
    em = float(np.max(np.abs(meta - jm) / np.maximum(np.abs(jm), 1e-3)))
    ok("PC_META is the json's meta", em < 2e-6, f"worst relative {em:.2e}")
    moves = np.array(J["moves"], dtype=np.float64)
    p3, roll = cm.integrate(moves)
    m2, t2, _ = cm.pack(p3, roll, J["fps"], np.array(jm[16:27]), float(jm[14]))
    t2 = np.array(t2)
    same = len(t2) == len(tab)
    d = np.abs(t2 - tab).reshape(-1, cm.PER) if same else None
    if same:
        exy, els, erl = float(d[:, [0, 1, 3, 4, 6, 7]].max()), float(d[:, [2, 5, 8]].max()), float(d[:, 9].max())
        ok("PC_CAM is the path the json's moves integrate to", exy < 0.1 and els * 1101.0 < 0.25 and erl * 1101.0 < 0.25,
           f"{len(tab) // cm.PER} samples; worst x/y {exy:.4f} px, at the corner by scale {els * 1101.0:.3f} px, "
           f"by roll {erl * 1101.0:.3f} px")
    else:
        ok("PC_CAM is the path the json's moves integrate to", False, f"{len(t2)} floats against {len(tab)}")
    n = int(meta[0])
    last = tab[(n - 1) * cm.PER:(n - 1) * cm.PER + cm.PER]
    pe = J["path_end"]
    want = np.array(pe["q0"] + pe["q0.8"] + pe["q1.6"], dtype=np.float64)
    ok("the last sample is the json's path_end", float(np.max(np.abs(last[:9] - want))) <= 0.0051
       and abs(np.degrees(last[9]) - pe["roll_deg"]) <= 0.00051 and int(meta[12]) == 1,
       f"worst {float(np.max(np.abs(last[:9] - want))):.4f}")
    if out:
        fps = float(meta[2])
        dur = (float(meta[13]) - 1) / fps
        ts = [-0.5, 0.0, 0.37 / fps, 0.25 * dur, 0.5 * dur + 0.5 / fps, dur, dur + 1.0]
        qs = [-0.2, 0.0, 0.05, 0.33, 0.8, 1.0, 1.3, 1.6, 2.0]
        pts = [(100.0, 80.0), (960.0, 540.0), (1700.0, 1000.0)]
        rows = []
        for t in ts:
            for q in qs:
                c = cm.cam_at(meta, tab, t, q, 0.7)
                c1 = cm.cam_at(meta, tab, t, q)
                rows.append({"ts": t, "q": q, "g": cm.cam_g(meta, q), "cam07": c.tolist(), "cam": c1.tolist(),
                             "fwd": [list(cm.fwd(c1, x, y)) for x, y in pts], "inv": [list(cm.inv(c1, x, y)) for x, y in pts]})
        json.dump({"pts": pts, "rows": rows, "meta": meta.tolist(), "frames": int(meta[13]), "fps": fps,
                   "start_s": J["start_s"]}, open(out, "w", encoding="utf-8"))
    print(f"{fails} failed" if fails else "camref ok")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
