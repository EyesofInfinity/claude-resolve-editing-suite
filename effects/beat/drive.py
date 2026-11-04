"""Put any Develop effect's slider on the beat: beat.h's engine and a song's tables written into a built
transform DCTL, the slider read through the envelope, and the driver's own sliders added (all labelled "Beat ...").
The slider's value becomes the peak on the hit; Beat Depth sets how far it falls between hits (100: to 0, so an
Amount slider gives the picture back exactly between hits).

usage: python -I drive.py <built effect.dctl> <slider[,slider]> <music.json or packed.json> <out.dctl>
       [--source beats] [--shape hit] [--release 250] [--attack 0] [--accent 40] [--rate 4] [--depth 100]
       [--fps 24] [--music-start 0] [--motion]
--source beats, downbeats, hits, low, bass, mids, highs; --shape hit, pump, swell. Without --motion the driver keeps
to the photosensitive limit (at most 3 hits a second), the safe choice for any slider that changes the frame's light.
beat.py runs this for you with --drive. MIT License.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bake
import shape as shp

DRIVER = [
    ("btSource", "Beat Source", 0.0, 0.0, 6.0, 1.0),
    ("btShape", "Beat Shape", 0.0, 0.0, 2.0, 1.0),
    ("btDepth", "Beat Depth", 100.0, 0.0, 100.0, 1.0),
    ("btAttack", "Beat Attack ms", 0.0, 0.0, 500.0, 1.0),
    ("btRelease", "Beat Release ms", 250.0, 20.0, 2000.0, 1.0),
    ("btAccent", "Beat Downbeat Accent", 40.0, 0.0, 100.0, 1.0),
    ("btRate", "Beat Max Hits a Second", 3.0, 1.0, 8.0, 1.0),
    ("btFloor", "Beat Band Floor", 25.0, 0.0, 90.0, 1.0),
    ("btNudge", "Beat Nudge Frames", 0.0, -6.0, 6.0, 1.0),
    ("btStart", "Beat Music Start s", 0.0, 0.0, 3600.0, 0.01),
    ("btFps", "Beat Timeline FPS", 24.0, 12.0, 120.0, 0.001),
    ("btBpm", "Beat BPM", 0.0, 0.0, 300.0, 0.1),
]
LIMIT = 64

def engine_source(block):
    t = open(os.path.join(HERE, "beat.h"), encoding="utf-8").read()
    return t.replace('#include "btdata.h"\n', block + "\n")

def drive(text, sliders, packed, song="", defaults=None, motion=False):
    if re.search(r"__DEVICE__\s+\w+\s+transition\s*\(", text):
        raise SystemExit("a Transition DCTL: drive a transform DCTL")
    m = re.search(r"__DEVICE__\s+float3\s+transform\s*\([^)]*\)\s*\{", text)
    if not m:
        raise SystemExit("no transform function found")
    if re.search(r"\bbt[A-Z]\w*", text):
        raise SystemExit("the effect already uses names starting with bt (driven already?)")
    rest = {}
    for s in sliders:
        d = re.search(r"DEFINE_UI_PARAMS\(\s*" + re.escape(s) + r"\s*,[^,]+,\s*DCTLUI_SLIDER_FLOAT\s*,"
                      r"\s*([-0-9.eE+]+)\s*,\s*([-0-9.eE+]+)\s*,\s*([-0-9.eE+]+)", text)
        if not d:
            raise SystemExit(f"no float slider named {s}")
        lo, hi = float(d.group(2)), float(d.group(3))
        rest[s] = 0.0 if lo <= 0.0 <= hi else (lo if lo > 0.0 else hi)
    labels = set(x.strip() for x in re.findall(r"DEFINE_UI_PARAMS\(\s*\w+\s*,([^,]+),", text))
    for _, lab, *_r in DRIVER:
        if lab in labels:
            raise SystemExit(f"the effect already has a slider labelled {lab}")
    i0 = m.end()
    depth, i = 1, i0
    while depth and i < len(text):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    body = text[i0:i - 1]
    for s in sliders:
        body = re.sub(r"\b" + re.escape(s) + r"\b", s + "_bt", body)
    head = ("\n    // the beat (effects/beat/drive.py): the driven sliders peak on the hit and fall by Beat Depth between\n"
            "    float btE = btEnv(TIMELINE_FRAME_INDEX, btStart, btNudge, btFps, (int)(btSource + 0.5f), (int)(btShape + 0.5f), "
            "btAttack * btFps / 1000.0f, btRelease * btFps / 1000.0f, btAccent / 100.0f, "
            f"btTier(btRate, {0 if motion else 1}), btBpm, btFloor / 100.0f);\n"
            "    float btK = 1.0f - btDepth / 100.0f * (1.0f - btE);\n")
    for s in sliders:
        r = rest[s]
        head += (f"    float {s}_bt = {s} * btK;\n" if r == 0.0 else
                 f"    float {s}_bt = {r!r}f + ({s} - {r!r}f) * btK;\n")
    text = text[:i0] + head + body + text[i - 1:]
    last = list(re.finditer(r"DEFINE_UI_PARAMS\([^\n]*\n", text))[-1]
    rows = "".join(f"DEFINE_UI_PARAMS({n}, {lab}, DCTLUI_SLIDER_FLOAT, {d}, {lo}, {hi}, {st})\n"
                   for n, lab, d, lo, hi, st in DRIVER)
    rows += ('DEFINE_UI_TOOLTIP(Beat Source, "0 Beats, 1 Downbeats, 2 Hits, 3 Low Hits, 4 Bass, 5 Mids, 6 Highs")\n'
             'DEFINE_UI_TOOLTIP(Beat Shape, "0 Hit, 1 Pump (ducks on the beat), 2 Swell (rises into it)")\n'
             'DEFINE_UI_TOOLTIP(Beat Depth, "How far the driven sliders fall between hits; 100 to zero")\n')
    text = text[:last.end()] + rows + text[last.end():]
    f = re.search(r"\n(__DEVICE__|#include)", text[text.index("DEFINE_UI_TOOLTIP(Beat Depth"):])
    at = text.index("DEFINE_UI_TOOLTIP(Beat Depth") + f.start() + 1
    eng = engine_source(bake.data_block(packed, song))
    text = text[:at] + eng + "\n" + text[at:]
    hdr = (f"// Driven by the beat of {song or 'a song'} (effects/beat/drive.py): "
           f"{', '.join(sliders)} on the Beat sliders below.\n")
    text = hdr + text
    n = len(re.findall(r"^DEFINE_UI_PARAMS\(", text, re.M))
    if n > LIMIT:
        raise SystemExit(f"the driven effect would have {n} sliders; a DCTL plugin node takes {LIMIT} "
                         f"(the driver adds {len(DRIVER)})")
    if defaults:
        text = bake.set_defaults(text, defaults)
    return text

def load_packed(path):
    d = json.load(open(path, encoding="utf-8"))
    return d if "meta" in d else bake.pack(d)

def main():
    a = sys.argv[1:]
    arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    src, sliders, music, out = a[0], a[1].split(","), a[2], a[3]
    packed = load_packed(music)
    defaults = {"btSource": shp.SOURCES[arg("--source", "beats")], "btShape": shp.SHAPES[arg("--shape", "hit")],
                "btRelease": float(arg("--release", 250)), "btAttack": float(arg("--attack", 0)),
                "btAccent": float(arg("--accent", 40)), "btRate": float(arg("--rate", 3)),
                "btDepth": float(arg("--depth", 100)), "btFps": float(arg("--fps", 24)),
                "btStart": float(arg("--music-start", 0))}
    text = drive(open(src, encoding="utf-8").read(), sliders, packed,
                 bake.song_name(music).replace(".music", ""), defaults, "--motion" in a)
    open(out, "w", encoding="utf-8", newline="\n").write(text)
    print("wrote", out)

if __name__ == "__main__":
    main()
