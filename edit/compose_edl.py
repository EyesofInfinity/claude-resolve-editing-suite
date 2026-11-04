"""Take approved mistake cuts (times on the silenced timeline of a silence EDL), map them back to the source timeline,
and remove them from a keep list, so the whole edit renders once from the source.
usage: python -I compose_edl.py <silence_edl> <base_edl> <approved-cuts.json> <out_edl>
<silence_edl> maps the silenced timeline; <base_edl> gives the keep ranges to cut from (the same file, or a snapped
copy of it). A range edge made by a mistake cut is marked ("end_at_cut", "start_at_cut"): there the removed side is
speech, so snap_edl.py looks for quiet on the kept side instead of past the edge. MIT License."""
import json, os, re, sys
if len(sys.argv) != 5:
    sys.exit(__doc__)
if os.path.normcase(os.path.abspath(sys.argv[4])) in {os.path.normcase(os.path.abspath(a)) for a in sys.argv[1:4]}:
    sys.exit(f"the output {sys.argv[4]} must be a new file, not an input")
old = json.load(open(sys.argv[1], encoding="utf-8"))["keep_ranges"]
snap = json.load(open(sys.argv[2], encoding="utf-8"))
cuts = json.load(open(sys.argv[3], encoding="utf-8"))["cuts"]


def seconds(v):
    """A time as a number of seconds, or as the candidates' page prints it, 01:02.08."""
    if isinstance(v, str):
        m = re.fullmatch(r"(?:(\d+):)?(\d+(?:\.\d+)?)", v.strip())
        if not m:
            sys.exit(f"cannot read the time {v!r}: use seconds, or mm:ss.xx")
        return int(m.group(1) or 0) * 60 + float(m.group(2))
    return float(v)


def to_source(t):
    acc = 0.0
    for r in old:
        d = r["end"] - r["start"]
        if t <= acc + d + 1e-6:
            return r["start"] + (t - acc)
        acc += d
    return old[-1]["end"]

dels = sorted((to_source(seconds(c["start"])), to_source(seconds(c["end"]))) for c in cuts)
keep = []
for r in snap["keep_ranges"]:
    pieces = [(r["start"], r["end"], bool(r.get("start_at_cut")), bool(r.get("end_at_cut")))]
    for a, b in dels:
        nxt = []
        for s, e, sc, ec in pieces:
            if b <= s or a >= e:
                nxt.append((s, e, sc, ec)); continue
            if a > s: nxt.append((s, a, sc, True))
            if b < e: nxt.append((b, e, True, ec))
        pieces = nxt
    for s, e, sc, ec in pieces:
        if e - s > 0.05:
            keep.append({"start": round(s, 3), "end": round(e, 3), **({"start_at_cut": True} if sc else {}),
                         **({"end_at_cut": True} if ec else {})})
snap["keep_ranges"] = keep
# the totals and the removed list follow the new keep list, or a review page reads the old ones
total = snap.get("source_duration")
if total is not None:
    kept = sum(r["end"] - r["start"] for r in keep)
    snap["edited_duration"] = round(kept, 3)
    snap["removed"] = round(total - kept, 3)
    gaps, cur = [], 0.0
    for r in keep:
        if r["start"] > cur:
            gaps.append({"start": round(cur, 3), "end": r["start"]})
        cur = r["end"]
    if total > cur:
        gaps.append({"start": round(cur, 3), "end": total})
    snap["delete_ranges"] = gaps
json.dump(snap, open(sys.argv[4], "w", encoding="utf-8"), indent=1)
print("mistake cuts on the source timeline:", [(round(a, 2), round(b, 2)) for a, b in dels], "| kept", round(sum(r["end"] - r["start"] for r in keep), 2), "s")
