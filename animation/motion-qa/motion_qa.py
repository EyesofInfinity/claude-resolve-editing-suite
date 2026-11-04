"""Motion QA for a rendered video: single-frame pops, one-frame flashes, and a loop's seam, from the frames
alone, so it works on any render (HyperFrames, Resolve, a browser capture).

What it finds, on frames scaled to 180x180 grey:
  pops       a frame-to-frame change at least 3 times both neighbouring changes (and above 2 grey levels): a jump in
             a move, an element that pops in for one frame, or a hard cut. Intended cuts show up too; they are
             listed, never hidden, so check each against the edit
  flashes    one frame that is further from each of its neighbours than they are from each other (a blank frame, a
             stray render, a wrong-frame insert), also in the middle of a move; two big changes side by side hide
             this from the pop test, so it has its own
  frozen     no frame differs from the one before (under 0.1 grey levels): a render whose timeline never ran fails.
             --still allows a film that is meant to hold still
  loop       with --loop: the seam from the last frame back to the first must look like an ordinary step (position)
             and the motion into the first frame must match the motion out of it (speed)
  blank      a stretch of 0.3 s or more mid-film with almost no edges (under 0.2% of pixels with a Sobel gradient over
             24, on grey frames 320 wide at 12 fps), skipping the first and last 0.5 s and the frames at hard cuts.
             Judged by edges, not colour, so a dark frame with thin lines or a formula is not blank. A deliberate fade
             through black of 0.3 s or more reads as blank too: check it
  palette    the share of the film that is mostly blue-purple, the stock "AI" background (2 fps, 160 wide: a frame
             counts when 30% of its pixels have hue 225 to 300 degrees, saturation 0.30 or more, value 0.15 to 0.90);
             0.12 or more is reported as a WARN, never a failure: it is taste, and three of the seven animate looks
             (cut paper, crosshatch, pixel) read 42 to 50% at huashu's value floor of 0.06 while their author's
             reviewer judged them incredible. The 0.15 floor clears dark navy night scenes (crosshatch and pixel go to
             0%); cut paper's periwinkle night still reads 44%. --allow-blue-purple "reason" records why a film needs it

usage: python -I motion_qa.py <video> [--loop] [--allow-blue-purple "reason"] [--json out.json]
Exit code 1 when a flash or a blank stretch is found or the loop seam fails; pops and the palette never fail the
run, since cuts make pops and the palette is taste.

The pop, flash and loop rules are ported from claude-motion-design by Raphael Aubry (Howseen AI, MIT) and rewritten to
stream frames; the blank and palette rules and their thresholds from film_gate.py in huashu-art-motion by alchaincyf
(MIT), whose author calibrated them on films they had judged (none of the 9 approved had two blank frames in a row;
approved films scored at most 0.10 blue-purple, rejected ones 0.46 to 1.00). Both notices are in LICENSE in this
folder. MIT License.
"""
import json
import re
import subprocess
import sys

import numpy as np

S = 180  # analysis size: small enough to ignore grain and sharpening, big enough to see a word pop


def fps_of(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"(\d+(?:\.\d+)?) fps", err)
    if not m:
        sys.exit(f"motion_qa: no video stream in {path}")
    return float(m.group(1))


def frames(path):
    """Yield each frame as a float32 SxS grey array, one at a time."""
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", path, "-vf", f"scale={S}:{S},format=gray", "-f", "rawvideo", "-"]
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as p:
        while True:
            buf = p.stdout.read(S * S)
            if len(buf) < S * S:
                break
            yield np.frombuffer(buf, np.uint8).reshape(S, S).astype(np.float32)


def scan(path, loop=False):
    fps = fps_of(path)
    steps, flashes = [], []
    first, second, prev2, prev = None, None, None, None
    n = 0
    for f in frames(path):
        if first is None:
            first = f
        elif second is None:
            second = f
        if prev is not None:
            steps.append(float(np.abs(f - prev).mean()))
        # frame n-1 is a one-frame flash when it is further from each neighbour than they are from each other. In
        # smooth motion a frame sits between its neighbours (ratio about 0.5 to 0.85 on real renders); a white frame
        # inserted mid-move measured 1.75. The ported rule asked the neighbours to match (ratio above 2.86), which
        # misses a flash during motion.
        if prev2 is not None:
            a, b = steps[-2], steps[-1]
            skip = float(np.abs(f - prev2).mean())
            if min(a, b) > 2.0 and min(a, b) > 1.25 * skip:
                flashes.append({"frame": n - 1, "t": round((n - 1) / fps, 3), "change": round(min(a, b), 2), "either_side": round(skip, 2)})
        prev2, prev = prev, f
        n += 1
    if n < 3:
        sys.exit(f"motion_qa: {path} has {n} frames, too few to judge")
    d = steps
    pops = []
    for i in range(1, len(d) - 1):
        nb = max(d[i - 1], d[i + 1], 0.3)
        if d[i] > 3 * nb and d[i] > 2.0:
            pops.append({"frame": i + 1, "t": round((i + 1) / fps, 3), "change": round(d[i], 2), "neighbours": round(nb, 2)})
    out = {"video": path, "fps": fps, "frames": n, "median_step": round(float(np.median(d)), 3), "pops": pops, "flashes": flashes,
           "max_step": round(float(np.max(d)), 3) if len(d) else 0.0}
    if loop:
        med = float(np.median(d)) or 0.3
        seam = float(np.abs(prev - first).mean())
        v_in, v_out = d[-1], d[0]
        out["loop"] = {
            "seam": round(seam, 2), "seam_ok": seam <= 2 * med,
            "speed_in": round(v_in, 2), "speed_out": round(v_out, 2),
            "speed_ok": abs(v_in - v_out) <= max(1.0, 0.5 * max(v_in, v_out)),
        }
    return out


def frame_size(path):
    """The first video stream's width and height. Read from ffprobe's JSON "streams" list: an MP4 from DaVinci
    Resolve also carries a stream group, and in CSV output ffprobe prints the stream once for the group and once on
    its own, so "1920,1080" came back on two lines and the old parse read "1080\\n\\n1920" as the height."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", path],
                         capture_output=True, text=True).stdout
    streams = json.loads(out or "{}").get("streams") or []
    if not streams:
        sys.exit(f"motion_qa: no video stream in {path}")
    return int(streams[0]["width"]), int(streams[0]["height"])


def decode(path, fps, width, pix):
    """Yield the frames at fps, width wide (height by aspect, even), one at a time as uint8 arrays: grey HxW or RGB
    HxWx3. One at a time: the whole film in memory needed about 1.5 GB per 105 s, 9 GB for a 10-minute video."""
    w, h = frame_size(path)
    hh = max(2, int(round(h * width / w / 2)) * 2)
    ch = 3 if pix == "rgb24" else 1
    size = width * hh * ch
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", path, "-vf", f"fps={fps},scale={width}:{hh}:flags=area", "-pix_fmt", pix, "-f", "rawvideo", "-"]
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as p:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            a = np.frombuffer(buf, np.uint8)
            yield a.reshape(hh, width, 3) if ch == 3 else a.reshape(hh, width)
        p.stdout.close()
    if p.returncode:
        raise subprocess.CalledProcessError(p.returncode, cmd)


def blank_runs(path, fps=12, width=320, grad=24.0, frac=0.002, edge_s=0.5, min_s=0.3):
    """Mid-film stretches with almost no edges, as [(start s, end s)], at least min_s long."""
    blank, cut, prev = [], [], None
    for g in decode(path, fps, width, "gray"):
        F = g.astype(np.float32)
        # 3x3 Sobel on the interior, the same filter the thresholds were calibrated with
        gx = (F[:-2, 2:] + 2 * F[1:-1, 2:] + F[2:, 2:]) - (F[:-2, :-2] + 2 * F[1:-1, :-2] + F[2:, :-2])
        gy = (F[2:, :-2] + 2 * F[2:, 1:-1] + F[2:, 2:]) - (F[:-2, :-2] + 2 * F[:-2, 1:-1] + F[:-2, 2:])
        E = np.hypot(gx, gy) > grad
        # A letterbox or pillarbox edge is a straight line across the whole frame; it is not content, and without this
        # a blank picture inside 2.35 bars never reads as blank.
        E &= ~(E.mean(axis=1, keepdims=True) > 0.9)
        E &= ~(E.mean(axis=0, keepdims=True) > 0.9)
        blank.append(E.mean() < frac)
        if prev is not None:
            cut.append(np.abs(F - prev).mean() > 30)  # a hard cut: the frames on both sides are not judged
        prev = F
    if len(blank) < 3:
        return []
    blank = np.array(blank)
    ok = np.ones(len(blank), bool)
    e = int(round(edge_s * fps))
    ok[:e] = False
    ok[max(0, len(blank) - e):] = False
    for i in np.where(cut)[0]:
        ok[i] = ok[i + 1] = False
    runs, s0 = [], None
    for i, v in enumerate(list(blank & ok) + [False]):
        if v and s0 is None:
            s0 = i
        elif not v and s0 is not None:
            if (i - s0) / fps >= min_s - 1e-9:
                runs.append((round(s0 / fps, 2), round(i / fps, 2)))
            s0 = None
    return runs


def blue_purple(path, fps=2, width=160, vmin=0.15):
    """Share of frames that are mostly blue-purple, and those stretches as [(start s, end s)]."""
    bad = []
    for fr in decode(path, fps, width, "rgb24"):
        F = fr.astype(np.float32) / 255
        r, g, b = F[..., 0], F[..., 1], F[..., 2]
        mx, mn = F.max(-1), F.min(-1)
        d = mx - mn + 1e-6
        sat = d / (mx + 1e-6)
        hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
        m = (hue >= 225) & (hue <= 300) & (sat >= 0.30) & (mx >= vmin) & (mx <= 0.90)
        bad.append(m.mean() >= 0.30)
    if not bad:
        return 0.0, []
    bad = np.array(bad)
    spans, start = [], None
    for i, x in enumerate(list(bad) + [False]):
        if x and start is None:
            start = i
        if not x and start is not None:
            if i - start >= 2:
                spans.append((round(start / fps, 1), round(i / fps, 1)))
            start = None
    return round(float(bad.mean()), 3), spans


def report(r):
    print(f"{r['video']}: {r['frames']} frames at {r['fps']:g} fps, median change {r['median_step']} grey levels per frame")
    print(f"pops: {len(r['pops'])}" + (" (hard cuts show up here too; check each against the edit)" if r["pops"] else ""))
    for p in r["pops"]:
        print(f"  frame {p['frame']} at {p['t']}s: change {p['change']}, neighbours {p['neighbours']}")
    print(f"one-frame flashes: {len(r['flashes'])}")
    for f in r["flashes"]:
        print(f"  frame {f['frame']} at {f['t']}s: change {f['change']}, frames either side differ by {f['either_side']}")
    if "loop" in r:
        lp = r["loop"]
        print(f"loop seam: last to first {lp['seam']} against median {r['median_step']} -> {'OK' if lp['seam_ok'] else 'JUMP at the seam'}")
        print(f"loop speed: into frame 0 {lp['speed_in']}, out of it {lp['speed_out']} -> {'OK' if lp['speed_ok'] else 'SPEED BREAK at the seam'}")
    print(f"blank stretches mid-film (0.3 s or more): {len(r['blank'])}" + "".join(f"\n  {a}s to {b}s" for a, b in r["blank"]))
    bp = r["blue_purple"]
    verdict = "WARN (check the look on purpose)" if bp["share"] >= 0.12 and not bp["allowed"] else "OK"
    print(f"blue-purple share: {bp['share']:.0%} -> {verdict}" + (f" (allowed: {bp['allowed']})" if bp["allowed"] else "")
          + "".join(f"\n  {a}s to {b}s" for a, b in bp["spans"][:6]))


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    r = scan(args[0], loop="--loop" in args)
    r["blank"] = blank_runs(args[0])
    share, spans = blue_purple(args[0])
    allowed = args[args.index("--allow-blue-purple") + 1] if "--allow-blue-purple" in args else None
    r["blue_purple"] = {"share": share, "spans": spans, "allowed": allowed}
    report(r)
    if "--json" in args:
        with open(args[args.index("--json") + 1], "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=1)
    frozen = r["max_step"] < 0.1 and "--still" not in args
    if frozen:
        print(f"FROZEN: the picture never moves (largest change {r['max_step']} grey levels). If the film should move, its timeline did not run.")
    fail = frozen or bool(r["flashes"]) or bool(r["blank"]) or ("loop" in r and not (r["loop"]["seam_ok"] and r["loop"]["speed_ok"]))
    sys.exit(1 if fail else 0)
