"""Snap an EDL's cut points to real quiet in the audio, then render it with short fades at every join.

Transcript word times run tens of ms off on real speech, so a cut placed exactly on them lands inside a word: a
clipped ending, a chopped onset, a click. For each kept range this moves the end later to the first moment the audio
falls quiet (30 ms below a threshold) and the start earlier to the last quiet moment before the word, within a window,
never into the neighbouring kept range. Every join then gets an 8 ms fade out and in.

An edge made by a mistake cut ("end_at_cut", "start_at_cut", from compose_edl.py) has removed speech on its far side, so
it may only move into the kept side, and only CUT_WIN: an end moves earlier to where the quiet before the removed
speech ends, a start moves later to where the quiet after the removed speech begins. Where no quiet is found, a cut
stays where it was: moving it the whole window put 0.3 s of a removed take back in at two of four mistake cuts on a real
take.

Quiet is measured against the room: 30 dB under speech, or just over the room's own floor in a take whose room is
louder than that. The source and any earlier output are never replaced without --overwrite.

With a video source, every cut is then moved to the nearest frame, so the render and a Resolve timeline match the EDL. A voice take
with no picture renders sound only. An edge's mistake-cut mark stays in the output, so snapping again keeps to the kept side.

usage: python -I snap_edl.py <source media> <edl.json with keep_ranges> <out_edl.json> [<out.mp4>] [--track n] [--overwrite]
Tested on a real narration take: joins inside a word went from 19 of 31 to 0. MIT License."""
import json, os, subprocess, sys
import numpy as np

SR, HOP = 48000, 240                     # 5 ms analysis hop
END_WIN, START_WIN = 0.30, 0.25          # how far a cut may move to find quiet
CUT_WIN = 0.06                           # how far an edge at a mistake cut may move, into the kept side only
QUIET_DB, HOLD = 30.0, 0.03              # quiet = 30 dB under speech, held for 30 ms
ROOM_DB, MIN_DROP = 6.0, 12.0            # or within 6 dB of the room's floor, when that floor is at least 12 dB under speech
MARGIN, FADE = 0.02, 0.008


def same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def frame_rate(path):
    """The source's frame rate, or None when it has no picture. A still of cover art is not a picture."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "json", path],
                       capture_output=True, text=True)
    streams = json.loads(r.stdout or "{}").get("streams") or []
    if not streams:
        return None
    num, den = streams[0]["r_frame_rate"].split("/")
    fps = float(num) / float(den) if float(den) else 0.0
    return fps if 0.0 < fps < 240.0 else None


overwrite = "--overwrite" in sys.argv
argv = [a for a in sys.argv[1:] if a != "--overwrite"]
track = "0"
if "--track" in argv:
    k = argv.index("--track")
    track = argv[k + 1]
    del argv[k:k + 2]
if len(argv) < 3:
    sys.exit(__doc__)
src, edl_in, edl_out = argv[0], argv[1], argv[2]
out_video = argv[3] if len(argv) > 3 else None
if same_file(edl_out, src) or same_file(edl_out, edl_in):
    sys.exit(f"the output EDL {edl_out} must be a new file, not an input")
if os.path.exists(edl_out) and not overwrite:
    sys.exit(f"{edl_out} already exists: pick another name, or pass --overwrite")
if out_video:
    if same_file(out_video, src):
        sys.exit(f"the output video {out_video} is the source video: pick another name")
    if os.path.exists(out_video) and not overwrite:
        sys.exit(f"{out_video} already exists: pick another name, or pass --overwrite")
fps = frame_rate(src)
# from the file's clock zero, as the cuts are: an audio stream that starts late is padded, or every time would read early
pcm = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", src, "-map", f"0:a:{track}", "-af", "aresample=async=1:first_pts=0",
                      "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
if pcm.returncode:
    sys.exit(f"{src} has no audio track {track}, or FFmpeg cannot read it: {pcm.stderr.decode(errors='replace')[-200:]}")
raw = pcm.stdout
x = np.frombuffer(raw, np.float32).astype(np.float64)
n = len(x) // HOP
if n < 10:
    sys.exit(f"{src}: the audio track is empty")
env = 20 * np.log10(np.sqrt((x[: n * HOP].reshape(n, HOP) ** 2).mean(1)) + 1e-9)
speech = np.median(env[env > np.percentile(env, 60)])
floor = np.percentile(env, 5)
quiet = env < max(speech - QUIET_DB, min(floor + ROOM_DB, speech - MIN_DROP))
hold = int(HOLD * SR / HOP)
idx = lambda t: int(round(t * SR / HOP))

edl = json.load(open(edl_in, encoding="utf-8"))
keep = [dict(r) for r in edl.get("keep_ranges") or []]
if not keep:
    sys.exit(f"{edl_in} has no keep ranges")
moved, unsnapped = [], 0
for k, r in enumerate(keep):
    lo = keep[k - 1]["end"] + MARGIN if k else 0.0
    hi = keep[k + 1]["start"] - MARGIN if k + 1 < len(keep) else len(x) / SR
    s0, e0 = r["start"], r["end"]
    e = None
    if r.get("end_at_cut"):
        # end before removed speech: last frame at or before the cut whose preceding HOLD is quiet (the onset), at most
        # CUT_WIN back: further would cut a kept word
        for f in range(min(n, idx(e0 + 0.02)), max(hold, idx(e0 - CUT_WIN)), -1):
            if quiet[f - hold:f].all():
                e = f * HOP / SR - MARGIN; break
    else:
        # end after a word: first frame at or after the transcript end where quiet holds for HOLD
        for f in range(max(0, idx(e0 - 0.02)), min(n - hold, idx(e0 + END_WIN))):
            if quiet[f:f + hold].all():
                e = f * HOP / SR + MARGIN; break
    r["end"] = max(s0, min(hi, e if e is not None else e0))
    s = None
    if r.get("start_at_cut"):
        # start after removed speech: first quiet at or after the cut, at most CUT_WIN in; earlier would bring removed
        # speech back
        for f in range(max(0, idx(s0 - 0.02)), min(n - hold, idx(s0 + CUT_WIN))):
            if quiet[f:f + hold].all():
                s = f * HOP / SR; break
    else:
        # start: last frame at or before the transcript start whose preceding HOLD is quiet
        for f in range(idx(s0 + 0.02), max(hold, idx(s0 - START_WIN)), -1):
            if quiet[f - hold:f].all():
                s = f * HOP / SR - MARGIN; break
    r["start"] = min(r["end"], max(lo, s if s is not None else s0))
    unsnapped += (e is None) + (s is None)
    moved.append((r["start"] - s0, r["end"] - e0))
# ranges that now touch merge
merged = []
for r in keep:
    if merged and r["start"] <= merged[-1]["end"] + 0.01:
        merged[-1]["end"] = max(merged[-1]["end"], r["end"])
        merged[-1].pop("end_at_cut", None)
        if r.get("end_at_cut"):
            merged[-1]["end_at_cut"] = True
    else:
        merged.append(r)
# on whole frames, so the render's length and a Resolve timeline's match the EDL
if fps:
    for r in merged:
        r["start"], r["end"] = round(r["start"] * fps) / fps, round(r["end"] * fps) / fps
    merged = [r for r in merged if r["end"] > r["start"]]
edl["keep_ranges"] = [{"start": round(r["start"], 4), "end": round(r["end"], 4), **{k: True for k in ("start_at_cut", "end_at_cut") if r.get(k)}}
                      for r in merged]
# the totals and the removed list follow the snapped keep list
total = edl.get("source_duration")
if total is not None:
    kept_s = sum(r["end"] - r["start"] for r in edl["keep_ranges"])
    edl["edited_duration"], edl["removed"] = round(kept_s, 3), round(total - kept_s, 3)
    gaps, cur = [], 0.0
    for r in edl["keep_ranges"]:
        if r["start"] > cur:
            gaps.append({"start": round(cur, 3), "end": r["start"]})
        cur = r["end"]
    if total > cur:
        gaps.append({"start": round(cur, 3), "end": total})
    edl["delete_ranges"] = gaps
edl["snapped"] = {"quiet_db_below_speech": QUIET_DB, "end_window": END_WIN, "start_window": START_WIN, "fade": FADE}
json.dump(edl, open(edl_out, "w", encoding="utf-8"), indent=1)
ms = np.array(moved) * 1000
print(f"{len(keep)} ranges, {len(merged)} after merging; starts moved {ms[:, 0].min():.0f} to {ms[:, 0].max():.0f} ms, ends moved {ms[:, 1].min():.0f} to {ms[:, 1].max():.0f} ms")
if unsnapped:
    print(f"{unsnapped} cut points found no quiet within the window and stay where they were: run join_check.py and listen")
print(f"kept {sum(r['end'] - r['start'] for r in merged):.2f} s")

if out_video:
    parts, labels = [], []
    for i, r in enumerate(merged):
        d = r["end"] - r["start"]
        if fps:
            parts.append(f"[0:v]trim={r['start']:.6f}:{r['end']:.6f},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[0:a:{track}]atrim={r['start']:.6f}:{r['end']:.6f},asetpts=PTS-STARTPTS,afade=t=in:d={FADE},afade=t=out:st={max(0, d - FADE):.4f}:d={FADE}[a{i}]")
        labels.append(f"[v{i}][a{i}]" if fps else f"[a{i}]")
    join = f"concat=n={len(merged)}:v=1:a=1[v][a]" if fps else f"concat=n={len(merged)}:v=0:a=1[a]"
    graph = ";".join(parts) + ";" + "".join(labels) + join
    script = edl_out + ".filter.txt"
    open(script, "w", encoding="utf-8").write(graph)
    maps = ["-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast"] if fps else ["-map", "[a]"]
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", src, "-/filter_complex", script, *maps, "-c:a", "aac", "-b:a", "192k", out_video], check=True)
    print("rendered", out_video)
