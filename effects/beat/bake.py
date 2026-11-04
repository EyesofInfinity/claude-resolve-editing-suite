"""Bake a song into Develop Beat: the music analysis (effects/audio/link/music.py) packed into the constant
tables beat.h reads, written between the BT_DATA markers of a built DCTL, with the slider defaults each reaction
wants. Also the reference for the packing: unpack() gives back exactly what the DCTL decodes.

Packing (beat.h decodes it): each event is one float, its time in hundredths of a second times 128 plus 7 bits.
  beats:          tier (2 bits), place in the bar (3 bits), strength (2 bits)
  hits, low hits: tier (2 bits), on a downbeat (1 bit), strength (4 bits)
  curve:          bass, mids, highs as three bytes (bass * 65536 + mids * 256 + highs), CURVE_RATE times a second
Every value is a whole number under 2^24, so float32 holds it exactly; a song up to 21 minutes fits. The tables are
kept under 14000 floats (56 KB, under the 64 KB of constant memory a CUDA kernel has): the densest hits go first,
then the densest low hits, then the curve's rate halves.
MIT License.
"""
import os
import re

import numpy as np

CURVE_RATE = 8.0
BUDGET = 14000
MAX_CS = (1 << 24) // 128 - 1

REACTIONS = {
    "Glow":       {"btMode": 0, "btSource": 0, "btShape": 0, "btRelease": 380, "btAccent": 55, "btAmount": 60, "btRate": 3},
    "Punch In":   {"btMode": 1, "btSource": 0, "btShape": 0, "btRelease": 240, "btAccent": 75, "btAmount": 40, "btRate": 4},
    "Shake":      {"btMode": 2, "btSource": 3, "btShape": 0, "btRelease": 320, "btAccent": 40, "btAmount": 30, "btRate": 4},
    "Flash":      {"btMode": 3, "btSource": 1, "btShape": 0, "btRelease": 200, "btAccent": 0, "btAmount": 45, "btRate": 3},
    "Grade Lift": {"btMode": 4, "btSource": 0, "btShape": 0, "btRelease": 420, "btAccent": 60, "btAmount": 55, "btRate": 3},
    "Breathe":    {"btMode": 5, "btSource": 4, "btShape": 0, "btRelease": 250, "btAccent": 0, "btAmount": 55, "btFloor": 30, "btRate": 3},
    "Split":      {"btMode": 6, "btSource": 2, "btShape": 0, "btRelease": 140, "btAccent": 30, "btAmount": 40, "btRate": 4},
}

def pack(m, curve_rate=CURVE_RATE, budget=BUDGET):
    """The analysis as the four tables and the meta row (lists of whole-number floats)."""
    if m["duration"] * 100 > MAX_CS:
        raise SystemExit(f"the song is {m['duration'] / 60:.1f} minutes; Develop Beat holds 21. Bake a part with "
                         f"--start and --dur")
    if not 1 <= int(m["meter"]) <= 8:
        raise SystemExit(f"meter {m['meter']}: Develop Beat stores the bar position in 3 bits, meters 1 to 8")
    beats = []
    for t, bar, tier, st in zip(m["beats"], m["bar"], m["beat_tier"], m["beat_strength"]):
        if tier < 0:
            continue
        pay = tier + 4 * (bar % 8) + 32 * min(3, int(st * 3 + 0.5))
        beats.append(int(round(t * 100)) * 128 + pay)

    def events(times, tiers, strength, down, min_tier=0):
        out = []
        for t, tier, st, dn in zip(times, tiers, strength, down):
            if tier < min_tier:
                continue
            out.append(int(round(t * 100)) * 128 + tier + 4 * int(bool(dn)) + 8 * min(15, int(st * 15 + 0.5)))
        return out

    hit_min, kick_min = 0, 0
    while True:
        hits = events(m["hits"], m["hit_tier"], m["hit_strength"], m["hit_down"], hit_min)
        kicks = events(m["kicks"], m["kick_tier"], m["kick_strength"], m["kick_down"], kick_min)
        curve = curve_table(m, curve_rate)
        total = len(beats) + len(hits) + len(kicks) + len(curve)
        if total <= budget:
            break
        if hit_min < 1:
            hit_min = 1
        elif kick_min < 1:
            kick_min = 1
        elif curve_rate > 2.0:
            curve_rate /= 2
        elif hit_min < 3:
            hit_min += 1
        elif kick_min < 3:
            kick_min += 1
        else:
            raise SystemExit("the song does not fit Develop Beat's tables")
    meta = [len(beats), len(hits), len(kicks), len(curve), curve_rate, round(m["tempo"], 2), m["meter"],
            round(m["duration"], 2)]
    return {"meta": meta, "beat": beats, "hit": hits, "kick": kicks, "curve": curve,
            "dropped": {"hit_min_tier": hit_min, "kick_min_tier": kick_min, "curve_rate": curve_rate}}

def curve_table(m, rate):
    src_rate = m["curve_rate"]
    n_src = len(m["curves"]["low"])
    n = int(np.floor((n_src - 1) / src_rate * rate)) + 1
    t = np.arange(n) / rate * src_rate
    q = [np.clip(np.round(np.interp(t, np.arange(n_src), m["curves"][b]) * 255), 0, 255).astype(np.int64)
         for b in ("low", "mid", "high")]
    return [int(v) for v in q[0] * 65536 + q[1] * 256 + q[2]]

def fmt(vals):
    lines, cur = [], []
    for v in vals:
        cur.append(f"{float(v):.1f}f")
        if len(cur) == 12:
            lines.append(", ".join(cur))
            cur = []
    if cur:
        lines.append(", ".join(cur))
    return ",\n    ".join(lines) if lines else "0.0f"

def data_block(p, song=""):
    def arr(name, vals):
        return f"__CONSTANT__ float {name}[{max(1, len(vals))}] = {{\n    {fmt(vals) if vals else '0.0f'} }};"
    meta = p["meta"]
    return "\n".join([
        "// BT_DATA_BEGIN",
        f"// Develop Beat's music data, baked by effects/beat/beat.py from {song or 'a song'}: {meta[0]} beats, "
        f"{meta[1]} hits, {meta[2]} low hits, the bands {meta[4]:g} times a second over {meta[7]:.1f} s, "
        f"tempo {meta[5]:.1f}. MIT License.",
        "// meta: beats, hits, low hits, curve samples, curve samples a second, tempo, meter, seconds",
        "__CONSTANT__ float BT_META[8] = { " + ", ".join(f"{float(v):.2f}f" for v in meta) + " };",
        arr("BT_BEAT", p["beat"]), arr("BT_HIT", p["hit"]), arr("BT_KICK", p["kick"]), arr("BT_CURVE", p["curve"]),
        "// BT_DATA_END"])

def put_data(text, block):
    a, b = text.index("// BT_DATA_BEGIN"), text.index("// BT_DATA_END") + len("// BT_DATA_END")
    return text[:a] + block + text[b:]

def set_defaults(text, defaults):
    """Change slider defaults: DEFINE_UI_PARAMS(name, label, kind, default, lo, hi, step)."""
    for name, val in defaults.items():
        pat = re.compile(r"(DEFINE_UI_PARAMS\(\s*" + re.escape(name) + r"\s*,[^,]+,\s*DCTLUI_SLIDER_FLOAT\s*,\s*)"
                         r"([-0-9.]+)")
        if not pat.search(text):
            raise SystemExit(f"no slider {name}")
        text = pat.sub(lambda mm: mm.group(1) + f"{float(val):g}" + ("" if "." in f"{float(val):g}" else ".0"),
                       text, count=1)
    return text

def song_name(path):
    base = os.path.splitext(os.path.basename(path))[0]
    return re.sub(r"[^A-Za-z0-9 _-]+", "", base).strip()[:40] or "song"

def unpack(p, fps):
    """What beat.h decodes: per list, (frame, payload) pairs at a timeline rate."""
    out = {}
    for k in ("beat", "hit", "kick"):
        v = np.asarray(p[k], dtype=np.float64)
        cs = np.floor(v / 128)
        out[k] = (np.floor(cs * fps / 100 + 0.5), v - 128 * cs)
    return out
