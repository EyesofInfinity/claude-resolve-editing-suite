"""Checks for the beat family. Run from anywhere: python -I check_beat.py [--quick]

  analysis   on synth.py tracks with a known grid (a drifting 4/4, a swung 92, a slowing 140 with a long pad intro,
             a 3/4 waltz): beat F-measure (70 ms), mean timing error, downbeat F-measure, low hits found
  tiers      every tier keeps its gap, the lists nest, tier 2 never passes 3 events in any second
  packing    pack then decode: times within 5 ms, payloads exact; a 20-minute song fits the 14000-float budget
  engine     shape.py: a Hit peaks on the event's own frame; the bright reactions never pass 3 peaks in a second
             even with Max Hits a Second at 8; Pump ducks on the hit and breathes back
  the DCTL   (node check.mjs) the baked DCTL's envelope equals shape.py's frame for frame, identity at Amount 0 and
             between hits, repeat, range; the generic build (no song, the BPM grid) the same
  drive      drive.py on a built Develop effect: it passes the transpiler's gates and gives the picture back exactly
             between hits
  visualizer every style renders finite, its alpha in range, silence draws a still frame
MIT License.
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "audio", "link"))
import bake
import music
import score
import shape as shp
import synth

FAILS = []
COUNT = [0]

def ok(name, cond, info=""):
    COUNT[0] += 1
    print(("pass " if cond else "FAIL ") + name + (f"  {info}" if info else ""))
    if not cond:
        FAILS.append(name)

def synth_track(**kw):
    import librosa
    x, truth = synth.make(**kw)
    return librosa.resample(x, orig_sr=synth.SR, target_sr=music.SR), truth

def check_analysis():
    cases = [("drift 118 to 126", dict()), ("swing 92", dict(bpm=92, to=92, swing=1.0, seed=2)),
             ("140 to 128, 4-bar pad intro", dict(bpm=140, to=128, seed=3, intro=4)),
             ("waltz 100 to 104", dict(bpm=100, to=104, meter=3, seed=4))]
    keep = None
    for name, kw in cases:
        y, truth = synth_track(**kw)
        m = music.analyse(y, meter=truth["meter"])
        drums = [t for t in truth["beats"] if t >= truth["drums_from"] - 0.01]
        f = score.fmeasure([t for t in m["beats"] if t >= truth["drums_from"] - 0.1], drums)
        d = score.downbeats(m["beats"], m["bar"], [t for t in truth["beats"]], truth["bar"])
        low = [t for t, b in zip(truth["beats"], truth["bar"]) if t >= truth["drums_from"] - 0.01
               and (b in (0, 2) if truth["meter"] == 4 else b == 0)]
        k = score.fmeasure(m["kicks"], low)
        ok(f"analysis {name}: beats", f["F"] >= 0.97 and f["mean_abs_err_ms"] <= 10,
           f"F {f['F']}, mean error {f['mean_err_ms']} ms, mean abs {f['mean_abs_err_ms']} ms (with drums)")
        ok(f"analysis {name}: downbeats", d["F"] >= 0.85, f"F {d['F']} (whole track, pad intro included)")
        ok(f"analysis {name}: kicks found", k["recall"] >= 0.95, f"recall {k['recall']}, {k['n_det']} low hits "
           f"(bass notes count as low hits)")
        if keep is None:
            keep = (m, truth)
    return keep

def check_tiers(m):
    for lst in ("beat", "hit", "kick"):
        times = np.array(m["beats" if lst == "beat" else lst + "s"])
        tiers = np.array(m[lst + "_tier"])
        good = True
        for g, gap in enumerate(music.GAPS):
            t = np.sort(times[tiers >= g])
            if len(t) > 1 and np.diff(t).min() < gap - 1e-6:
                good = False
        t2 = np.sort(times[tiers >= 2])
        most = max((np.sum((t2 >= a) & (t2 <= a + 1.0)) for a in t2), default=0)
        ok(f"tiers {lst}: gaps kept, at most 3 a second at tier 2", good and most <= 3, f"busiest second {most}")

def check_packing(m):
    p = bake.pack(m)
    dec = bake.unpack(p, 100.0)
    t_beats = dec["beat"][0] / 100.0
    kept = [t for t, tier in zip(m["beats"], m["beat_tier"]) if tier >= 0]
    err = np.abs(t_beats - np.array(kept)).max() if kept else 0
    pay = dec["hit"][1]
    tiers_back = pay - 4 * np.floor(pay / 4)
    want = [t for t in m["hit_tier"] if t >= p["dropped"]["hit_min_tier"]]
    ok("packing: times and tiers back", err <= 0.0051 and np.array_equal(tiers_back, np.array(want, float)),
       f"worst time error {err * 1000:.1f} ms over {len(kept)} beats")
    big = dict(m)
    dur = m["duration"]
    reps = int(np.ceil(1200 / dur))
    for k in ("beats", "hits", "kicks"):
        big[k] = [t + r * dur for r in range(reps) for t in m[k]]
    for k in ("bar", "beat_tier", "beat_strength", "hit_tier", "hit_strength", "hit_down", "kick_tier",
              "kick_strength", "kick_down"):
        big[k] = list(m[k]) * reps
    big["curves"] = {b: list(v) * reps for b, v in m["curves"].items()}
    big["duration"] = dur * reps
    pb = bake.pack(big)
    ok("packing: a 20-minute song fits", sum(pb["meta"][:4]) <= bake.BUDGET,
       f"{sum(pb['meta'][:4])} floats, {pb['dropped']}, {big['duration'] / 60:.1f} min")
    return p

def peaks_of(env):
    return [i for i in range(1, len(env) - 1) if env[i] > 0.05 and env[i] >= env[i - 1] and env[i] > env[i + 1]
            or (env[i] > 0.05 and env[i - 1] == 0 and env[i] >= env[i + 1] and env[i] > 0)]

def check_engine(p):
    eng = shp.Engine(p)
    fps = 24.0
    frames = np.arange(0, int(p["meta"][7] * fps))
    env = shp.from_sliders(eng, {"btMode": 1, "btSource": 0, "btRelease": 200, "btRate": 8, "btAccent": 0}, frames)
    fe, pay = bake.unpack(p, fps)["beat"]
    on = set(int(f) for f in fe)
    pk = [i for i in range(1, len(env)) if env[i] > env[i - 1] + 0.2]
    miss = [i for i in pk if i not in on]
    ok("engine: every Hit lands on its beat's frame", len(pk) > 20 and not miss, f"{len(pk)} rises, {len(miss)} off")
    worst = 0
    for src in (0, 2, 3):
        e = shp.from_sliders(eng, {"btMode": 3, "btSource": src, "btRelease": 120, "btRate": 8}, frames)
        rises = [i for i in range(1, len(e)) if e[i] > e[i - 1] + 0.05 and e[i] > 0.15]
        r = np.array(rises) / fps
        most = max((np.sum((r >= a) & (r < a + 1.0)) for a in r), default=0)
        worst = max(worst, most)
    ok("engine: Flash never passes 3 hits in any second (Max Hits 8 asked)", worst <= 3, f"busiest second {worst}")
    e = shp.from_sliders(eng, {"btMode": 5, "btSource": 3, "btShape": 1, "btRelease": 300}, frames)
    kf, kp = bake.unpack(p, fps)["kick"]
    fk = sorted(set(int(f) for f, q in zip(kf, kp) if q - 4 * np.floor(q / 4) >= 2))
    mid = [f for f in fk if 50 < f < len(e) - 50][:20]
    dips = [e[f] < e[f - 1] - 0.1 for f in mid if f - 1 >= 0]
    ok("engine: Pump ducks on the low hits", len(dips) > 5 and np.mean(dips) > 0.8, f"{np.mean(dips):.2f} of {len(dips)}")
    return eng

def expect_cases(eng, p, fps=24.0):
    n = int(p["meta"][7] * fps) + 24
    frames = list(range(-30, n, 1))
    sets = [("beats hit", {"btSource": 0}), ("downbeats hit attack", {"btSource": 1, "btAttack": 120}),
            ("hits rate 8 motion", {"btMode": 1, "btSource": 2, "btRate": 8, "btRelease": 90}),
            ("low hits pump", {"btSource": 3, "btShape": 1, "btRelease": 400}),
            ("hits swell bright", {"btMode": 3, "btSource": 2, "btShape": 2, "btRelease": 300, "btRate": 8}),
            ("bass follow", {"btSource": 4, "btFloor": 20}), ("mids pump", {"btSource": 5, "btShape": 1}),
            ("highs swell", {"btSource": 6, "btShape": 2}),
            ("start 1.5 s nudge -1 at 30 fps", {"btStart": 1.5, "btNudge": -1, "btFps": 30}),
            ("23.976 fps accent 100", {"btFps": 23.976, "btAccent": 100}),
            ("BPM 128 grid", {"btBpm": 128, "btSource": 0}), ("BPM 200 grid downbeats", {"btBpm": 200, "btSource": 1}),
            ("BPM 190 bright tier", {"btBpm": 190, "btMode": 0, "btRate": 8})]
    defaults = {"btMode": 0, "btAmount": 50, "btSource": 0, "btShape": 0, "btAttack": 0, "btRelease": 250,
                "btAccent": 40, "btRate": 4, "btFloor": 25, "btNudge": 0, "btStart": 0, "btFps": 24, "btBpm": 0}
    cases = []
    for name, s in sets:
        full = dict(defaults)
        full.update(s)
        fr = frames if full["btFps"] == 24 else list(range(-30, int(p["meta"][7] * full["btFps"]) + 24))
        cases.append({"name": name, "sliders": s, "frames": fr, "env": [float(v) for v in shp.from_sliders(eng, full, fr)]})
    return cases

def check_dctl(p, eng, m):
    build = os.path.join(HERE, "build", "Develop Beat.dctl")
    subprocess.run([sys.executable, "-I", os.path.join(HERE, "..", "build.py"), HERE], check=True, capture_output=True)
    tmp = tempfile.mkdtemp(prefix="beatchk_")
    baked = os.path.join(tmp, "Develop Beat - synth.dctl")
    open(baked, "w", encoding="utf-8", newline="\n").write(
        bake.put_data(open(build, encoding="utf-8").read(), bake.data_block(p, "synth")))
    fr, pay = bake.unpack(p, 24.0)["beat"]
    db = [int(f) for f, q in zip(fr, pay) if (int(q) // 4) % 8 == 0]
    loud = db[3]
    quiet = (db[3] + db[4]) // 2
    exp = {"cases": expect_cases(eng, p), "loud": loud, "quiet": quiet}
    json.dump(exp, open(os.path.join(tmp, "expect.json"), "w"))
    for f, label in ((baked, "baked"), (build, "generic")):
        if label == "generic":
            g = shp.Engine({"meta": [0, 0, 0, 0, 8, 0, 4, 0], "beat": [], "hit": [], "kick": [], "curve": []})
            e2 = {"cases": [c for c in expect_cases(g, {"meta": [0, 0, 0, 0, 8, 0, 4, 40.0]})],
                  "loud": 48, "quiet": 24 + 12}
            json.dump(e2, open(os.path.join(tmp, "expect_generic.json"), "w"))
            ep = os.path.join(tmp, "expect_generic.json")
        else:
            ep = os.path.join(tmp, "expect.json")
        r = subprocess.run(["node", os.path.join(HERE, "check.mjs"), f, ep], capture_output=True, text=True, cwd=HERE)
        lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("pass", "FAIL"))]
        for ln in lines:
            ok(f"DCTL {label}: {ln[5:]}", ln.startswith("pass"))
        if r.returncode != 0 and not any(ln.startswith("FAIL") for ln in lines):
            ok(f"DCTL {label} ran", False, r.stderr[-400:])
        g = subprocess.run(["node", os.path.join(REPO, "tests", "cpu", "order_gate.mjs"), f], capture_output=True, text=True)
        ok(f"DCTL {label}: order gate", g.returncode == 0, g.stdout.strip()[-120:])
    return tmp

def check_drive(p, tmp):
    import drive as drv
    eff = os.path.join(REPO, "effects", "fx", "build", "Develop Glint.dctl")
    out = os.path.join(tmp, "Develop Glint Beat.dctl")
    text = drv.drive(open(eff, encoding="utf-8").read(), ["gnAmount"], p, "synth",
                     {"btSource": 1, "btRelease": 100})
    open(out, "w", encoding="utf-8", newline="\n").write(text)
    g = subprocess.run(["node", os.path.join(REPO, "tests", "cpu", "order_gate.mjs"), out], capture_output=True, text=True)
    ok("drive: Develop Glint driven passes the gates", g.returncode == 0, g.stdout.strip()[-160:])
    js = os.path.join(tmp, "drive_check.mjs")
    fe, pay = bake.unpack(p, 24.0)["beat"]
    bar = np.floor(pay / 4) - 8 * np.floor(pay / 32)
    downs = [int(f) for f, b in zip(fe, bar) if b == 0]
    loud, quiet = downs[3], (downs[3] + downs[4]) // 2
    open(js, "w", encoding="utf-8").write(f"""
import {{ compile }} from "file:///{os.path.join(REPO, 'tests', 'cpu', 'dctl.mjs').replace(os.sep, '/')}";
const W = 96, H = 54, n = W * H, A = {{ r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) }};
for (let i = 0; i < n; i++) {{ const v = (i % 7 === 0) ? 1 : 0.2 + 0.3 * ((i * 37) % 11) / 11; A.r[i] = v; A.g[i] = v; A.b[i] = v; }}
function run(frame, P) {{
  const T = compile("{out.replace(os.sep, '/')}", P, {{ frame }}).transform; let d = 0;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {{ const c = T(W, H, x, y, {{d: A.r, w: W}}, {{d: A.g, w: W}}, {{d: A.b, w: W}}), i = y * W + x;
    if (c.x !== A.r[i] || c.y !== A.g[i] || c.z !== A.b[i]) d++; }}
  return d;
}}
console.log(JSON.stringify({{ quiet: run({quiet}, {{}}), loud: run({loud}, {{}}), depth0_quiet: run({quiet}, {{ btDepth: 0 }}) }}));
""")
    r = subprocess.run(["node", js], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        d = {"error": r.stderr[-300:]}
    ok("drive: Glint exact between hits, glinting on the downbeat, steady at depth 0",
       d.get("quiet") == 0 and d.get("loud", 0) > 0 and d.get("depth0_quiet", 0) > 0, json.dumps(d))

def check_review(p, tmp):
    """cases: a baked song with no beats keeps to its own hits; a driven slider whose range leaves out 0."""
    hits = [int(round(t * 100)) * 128 + 3 + 8 * 15 for t in (1.3, 4.1, 8.7)]
    e = shp.Engine({"meta": [0, 3, 0, 0, 8, 0, 4, 10.0], "beat": [], "hit": hits, "kick": [], "curve": []})
    beats = max(e.env(f, src=0, rel=6.0) for f in range(0, 240))
    on = [round(e.env(f, src=2, rel=6.0), 3) for f in (31, 98, 209)]
    grid = [e.env(f, src=2, rel=6.0) for f in (48, 144, 192)]
    ok("no beats in the song: Source Beats stays still, Source Hits lands on the three hits, no 120 BPM grid",
       beats == 0.0 and min(on) > 0.5 and max(grid) == 0.0, f"beats {beats} hits {on} grid {grid}")
    eff = os.path.join(REPO, "effects", "fx", "build", "Develop Rays.dctl")
    import drive as drv
    text = drv.drive(open(eff, encoding="utf-8").read(), ["ryPeriod"], p, "synth")
    out = os.path.join(tmp, "Develop Rays Beat.dctl")
    open(out, "w", encoding="utf-8", newline="\n").write(text)
    js = os.path.join(tmp, "drive_rays.mjs")
    open(js, "w", encoding="utf-8").write(f"""
import {{ compile }} from "file:///{os.path.join(REPO, 'tests', 'cpu', 'dctl.mjs').replace(os.sep, '/')}";
const W = 64, H = 36, n = W * H, A = {{ r: new Float32Array(n).fill(0.9), g: new Float32Array(n).fill(0.8), b: new Float32Array(n).fill(0.5) }};
const T = compile("{out.replace(os.sep, '/')}", {{ ryMode: 2 }}, {{ frame: 20000 }}).transform; let bad = 0;
for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {{ const c = T(W, H, x, y, {{d: A.r, w: W}}, {{d: A.g, w: W}}, {{d: A.b, w: W}});
  if (!Number.isFinite(c.x) || !Number.isFinite(c.y) || !Number.isFinite(c.z)) bad++; }}
console.log(JSON.stringify({{ bad }}));
""")
    r = subprocess.run(["node", js], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        d = {"error": r.stderr[-300:]}
    ok("drive: Sweep Period (minimum 0.5) falls to 0.5 between hits, every pixel finite",
       "0.5f + (ryPeriod - 0.5f) * btK" in text and d.get("bad") == 0, json.dumps(d))
    big = "".join(f"DEFINE_UI_PARAMS(s{i}, S{i}, DCTLUI_SLIDER_FLOAT, 0.0, 0.0, 1.0, 1.0)\n" for i in range(60))
    fake = big + "__DEVICE__ float3 transform(int p_Width, int p_Height, int p_X, int p_Y, __TEXTURE__ p_TexR, " \
                 "__TEXTURE__ p_TexG, __TEXTURE__ p_TexB)\n{\n    return make_float3(s0, s1, s2);\n}\n"
    try:
        drv.drive(fake, ["s0"], p, "synth")
        refused = False
    except SystemExit:
        refused = True
    ok("drive: refuses an effect that would pass 64 sliders", refused)
    try:
        bake.pack({"duration": 10.0, "meter": 9})
        meter = False
    except SystemExit:
        meter = True
    except Exception:
        meter = False
    ok("bake: refuses a meter above 8", meter)

def check_visualizer(tmp):
    import soundfile as sf
    import visualizer as vz
    y, _ = synth.make(bars=4, intro=0)
    wav = os.path.join(tmp, "v.wav")
    sf.write(wav, np.concatenate([np.zeros(synth.SR, np.float32), y]), synth.SR)
    for style in ("line", "ring", "wave"):
        spec = vz.Spectrum(wav, 24.0)
        pt = vz.Painter(spec, style, 320, 180)
        fr = [pt.display(pt.frame(k)) for k in range(0, 40)]
        finite = all(np.isfinite(f).all() and f.min() >= 0 and f.max() <= 1 for f in fr)
        still = np.abs(fr[12] - fr[13]).max() < 1e-3
        moving = np.abs(fr[30] - fr[33]).max() > 0.05
        lit = max(f.mean() for f in fr[24:])
        ok(f"visualizer {style}: finite, still in silence, moves with the music, light not a wash",
           finite and still and moving and lit < 0.2, f"mean light {lit:.3f}")
    out = os.path.join(tmp, "v.mov")
    vz.render(wav, out, "line", 320, 180, 24.0, alpha=True)
    pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=pix_fmt,codec_name",
                         "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip()
    ok("visualizer: ProRes 4444 with alpha", "prores" in pr and "yuva444" in pr, pr)

def main():
    m, truth = check_analysis()
    check_tiers(m)
    p = check_packing(m)
    eng = check_engine(p)
    tmp = check_dctl(p, eng, m)
    check_drive(p, tmp)
    check_review(p, tmp)
    check_visualizer(tmp)
    print(f"{COUNT[0] - len(FAILS)} of {COUNT[0]} pass" + (f"; FAILED: {FAILS}" if FAILS else ""))
    sys.exit(1 if FAILS else 0)

if __name__ == "__main__":
    main()
