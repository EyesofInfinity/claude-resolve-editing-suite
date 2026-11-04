"""Grain Match: read a reference clip and a clip, print the Develop Grain Match slider values, write them. MIT License.

usage: python -I grainmatch.py <reference> <clip> [options]
  --frames N        frames read from each clip (default 30: three stretches of 10 spread over the clip)
  --stretches K     how many stretches (default 3); a --ref-start or --clip-start reads one stretch there
  --height H        the timeline height the clips play at (default 1080); both are read at it
  --ref-start S     seconds into the reference to start reading (default: its middle)
  --clip-start S    the same for the clip
  --hold            also match the reference's still share (Hold); off by default, since a still share in stock
                    footage is mostly picture texture or grain the codec froze, and still grain on a moving shot
                    reads as a dirty lens
  --json PATH       write both analyses and the slider values
  --drx PATH        write a grade: one ResolveFX DCTL plugin node carrying the values (apply it to the clip's node
                    graph in Resolve with Apply Grade from a still, or import it in the Gallery)
  --lut-path REL    the DCTL's path inside Resolve's LUT folder (default Develop\\Grainmatch\\Develop Grain Match.dctl,
                    where effects/build.py --install puts it)
  --sliders PATH    write the slider values alone as JSON (name: value)

Exit status 2 when either clip has no measurable grain area (the reasons are printed).
"""
import json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import grainlib as gl

DCTL_SRC = os.path.join(HERE, "Develop Grain Match.src.dctl")
DEFAULT_LUT = "Develop\\Grainmatch\\Develop Grain Match.dctl"

def slider_order():
    pat = re.compile(r"DEFINE_UI_PARAMS\(\s*(\w+)\s*,\s*([^,]+?)\s*,\s*DCTLUI_SLIDER_FLOAT\s*,\s*([-0-9.]+)\s*,\s*([-0-9.]+)\s*,\s*([-0-9.]+)")
    return [(m.group(1), m.group(2), float(m.group(3)), float(m.group(4)), float(m.group(5)))
            for m in pat.finditer(open(DCTL_SRC, encoding="utf-8").read())]

def figures(a):
    """The slider figures of one analysis: luma and colour per band, colour balance, sizes, links, hold."""
    b = [a["bands"][n]["sd"] for n in gl.BAND_NAMES]
    corr = a.get("corr") or {}
    return {"Y": [s["Y"] for s in b], "B": [s["Cb"] for s in b], "R": [s["Cr"] for s in b],
            "size": a.get("gauss_size_y") or 0.0, "csize": a.get("gauss_size_c") or 0.0,
            "YB": 100 * corr.get("Y_Cb", 0.0), "YR": 100 * corr.get("Y_Cr", 0.0), "BR": 100 * corr.get("Cb_Cr", 0.0),
            "hold": a.get("hold")}

def sliders(ref, clip, hold=False):
    r, c = figures(ref), figures(clip)
    v = {"gmRefYS": r["Y"][0], "gmRefYM": r["Y"][1], "gmRefYH": r["Y"][2],
         "gmRefBS": r["B"][0], "gmRefBM": r["B"][1], "gmRefBH": r["B"][2],
         "gmRefRS": r["R"][0], "gmRefRM": r["R"][1], "gmRefRH": r["R"][2],
         "gmRefSz": r["size"], "gmRefCSz": r["csize"], "gmRefYB": r["YB"], "gmRefYR": r["YR"], "gmRefBR": r["BR"],
         "gmHold": 100 * max(0.0, min(1.0, r["hold"] or 0.0)) if hold else 0.0,
         "gmClYS": c["Y"][0], "gmClYM": c["Y"][1], "gmClYH": c["Y"][2],
         "gmClBS": c["B"][0], "gmClBM": c["B"][1], "gmClBH": c["B"][2],
         "gmClRS": c["R"][0], "gmClRM": c["R"][1], "gmClRH": c["R"][2],
         "gmClSz": c["size"], "gmClCSz": c["csize"], "gmAmount": 100.0, "gmSeed": 0.0, "gmView": 0.0}
    rng = {n: (lo, hi) for n, _, _, lo, hi in slider_order()}
    return {k: round(min(max(val, rng[k][0]), rng[k][1]), 2) for k, val in v.items()}

def write_drx(values, path, lut):
    sys.path.insert(0, os.path.join(REPO, "tools"))
    from template import Grade
    g = Grade(os.path.join(REPO, "tools", "base.drx"))
    order = slider_order()
    params = [("DCTLs", "str", lut)] + [(f"sliderFloatParam{i}", "f64", float(values[n])) for i, (n, *_) in enumerate(order)]
    node = g.dctl_plugin(1, 190, 180, params)
    g.feed(node)
    g.out(node)
    return g.write(path)

def report(name, a):
    lines = [f"{name}: {a.get('path', '')}",
             f"  read {a['frames']} frames at {a['analysis_height']} lines from {a.get('start')} s ({a.get('codec')}, {a.get('native_h')} lines native)"]
    for n in gl.BAND_NAMES:
        b = a["bands"][n]
        s = b["sd"]
        lines.append(f"  {n:10s} luma {s['Y']:5.2f}  Cb {s['Cb']:5.2f}  Cr {s['Cr']:5.2f}   R {s['R']:5.2f} G {s['G']:5.2f} B {s['B']:5.2f}"
                     f"   ({b['grain_patches']} grain patches of {b['patches']}{'' if b['measured'] else ', NOT MEASURED'})")
    acf = a.get("acf") or {}
    lines.append(f"  size {a.get('gauss_size_y')} px luma, {a.get('gauss_size_c')} px colour (lag-1 correlation {acf.get('y1')}, {acf.get('cb1')}, {acf.get('cr1')})")
    if a.get("corr"):
        k = a["corr"]
        lines.append(f"  links Y-Cb {k['Y_Cb']}, Y-Cr {k['Y_Cr']}, Cb-Cr {k['Cb_Cr']} (R-G {k['R_G']}, R-B {k['R_B']}, G-B {k['G_B']})")
    lines.append(f"  hold {a.get('hold')} (still share in the flattest areas), codec copied {a.get('copied')}, moving picture {a.get('moving_picture')}, "
                 f"grain area {a.get('grain_fraction')}, blocking {a.get('blocking')}")
    for nt in a.get("notes", []):
        lines.append("  NOTE " + nt)
    return "\n".join(lines)

def usable(a):
    return a.get("bands") and any(a["bands"][n]["measured"] for n in gl.BAND_NAMES)

def main():
    args = sys.argv[1:]
    if len(args) < 2 or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(1)

    def opt(name, default=None, conv=str):
        return conv(args[args.index(name) + 1]) if name in args else default
    ref_path, clip_path = args[0], args[1]
    n, height, k = opt("--frames", 30, int), opt("--height", 1080, int), opt("--stretches", 3, int)
    t0 = time.time()
    ref = gl.analyze_file(ref_path, opt("--ref-start", None, float), n, height, k)
    t1 = time.time()
    clip = gl.analyze_file(clip_path, opt("--clip-start", None, float), n, height, k)
    t2 = time.time()
    print(report("Reference", ref) if ref.get("bands") else f"Reference: {ref['notes']}")
    print(report("Clip", clip) if clip.get("bands") else f"Clip: {clip['notes']}")
    print(f"analysis: reference {t1 - t0:.1f} s, clip {t2 - t1:.1f} s")
    if not usable(ref) or not usable(clip):
        print("No slider values: a clip has no measurable grain area. Try another stretch (--ref-start, --clip-start).")
        sys.exit(2)
    v = sliders(ref, clip, "--hold" in args)
    print("\nDevelop Grain Match sliders:")
    for name, label, *_ in slider_order():
        print(f"  {label:24s} {v[name]:8.2f}")
    if opt("--json"):
        json.dump({"reference": ref, "clip": clip, "sliders": v}, open(opt("--json"), "w", encoding="utf-8"), indent=1)
        print("wrote", opt("--json"))
    if opt("--sliders"):
        json.dump(v, open(opt("--sliders"), "w", encoding="utf-8"), indent=1)
        print("wrote", opt("--sliders"))
    if opt("--drx"):
        print("wrote", write_drx(v, opt("--drx"), opt("--lut-path", DEFAULT_LUT)))

if __name__ == "__main__":
    main()
