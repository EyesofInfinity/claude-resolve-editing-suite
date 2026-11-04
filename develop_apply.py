"""Apply a Develop look across a timeline, shot by shot, in a running DaVinci Resolve Studio.

usage: python -I develop_apply.py <look.json> --timeline <name> [options]
       python -I develop_apply.py --revert <run folder or run.json>

It works in the project open in Resolve and grades only the timeline you name. Without --timeline it lists the
timelines and changes nothing. Each clip gets a new colour version, so its other grades stay as they were.

For every clip on the track, in order:
  1. switch the clip to its own colour version (default "Develop"); the clip's other versions keep their grades,
  2. apply the look node alone and grab stills at frames spread over the clip,
  3. judge each per-shot value from those stills and keep the most cautious (rule one, tools/judge.py: Bloom
     Threshold keeps the look's value, raised until at most --budget of the frame is above it; with
     "bloomRoll": "judge" a shot whose threshold was raised also gets Bloom Rolloff 50; with "ntStops": "judge"
     Night Exposure pulls the night picture's median halfway to the night key, the fewest stops kept),
  4. apply the whole look; the nodes that carry per-shot values are DCTL plugin nodes, so the values sit in the
     grade and a slider in Resolve shows them; no DCTL file is made per shot (a look node that carries per-shot
     values goes in as two plugin nodes, Develop 1 Light then Develop 2 Color, since one plugin node takes at most
     64 sliders and Develop.dctl has 67; develop_template.py sends each value to every node that declares it),
  5. grab the graded middle frame for review, and run the quality gate (tools/gate.py) on it against the look node
     alone: newly clipped and crushed pixels, the light added, edge halos. The gate flags; it never stops a run.
     A look file can set its own limits: "gate": {"energy": 1.0}.
Everything lands in the run folder: the grades, the stills and run.json. run.json is written before each clip changes,
so a stopped run keeps its way back. --revert puts every clip of a run back on the version it was on before.

options:
  --timeline <name>   the timeline to grade (required)
  --track <n>         video track (default 1)
  --clips <list>      clip numbers on the track, 1-based, comma separated (default: all)
  --frames <n>        frames judged per clip (default 3)
  --budget <share>    rule one's limit on the share of a frame above the threshold (default 0.30)
  --version <name>    the colour version that receives the grade (default Develop). A clip that already has a version
                      of this name stops the run before anything changes: pick a new name, or pass --overwrite
  --overwrite         replace the grade in an existing version of that name (the old grade in it is lost)
  --out <dir>         the run folder (default runs/<timeline> <date>-<time>)
  --no-review         skip the graded still (and with it the quality gate)

A look file: {"schema": "develop.look/0", "name": "Warm Film", "values": {...}, "per_shot": {"bloomThr": "judge"},
"effects": [{"effect": "Develop Leak", "values": {"lkAmount": 30}}]} (looks/README.md). Needs DaVinci Resolve Studio with
external scripting set to Local, numpy and opencv-python, and Node 22.15 or newer on PATH.
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
from develop_template import Look, LookError, PAT  # noqa: E402
from drxlib import check_node  # noqa: E402
from judge import auto_threshold, night_stops  # noqa: E402
import gate as qgate  # noqa: E402
import resolve_live as rl  # noqa: E402

RULES = {("bloomThr", "judge"), ("bloomRoll", "judge"), ("ntStops", "judge")}
ROLL_RAISED = 50.0      # bloomRoll: judge: the Rolloff on shots whose threshold the judge raised
gate_limits = {}        # a look file's own quality-gate limits ("gate": {...}), over gate.LIMITS


def args():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "--revert":
        if len(a) != 2:
            sys.exit("--revert <run folder or run.json>")
        return {"revert": a[1]}
    opts = {"look": a[0], "track": "1", "frames": "3", "budget": "0.30", "version": "Develop", "review": True,
            "overwrite": False}
    known = {"timeline", "track", "clips", "frames", "budget", "version", "out"}
    i = 1
    while i < len(a):
        if a[i] == "--no-review":
            opts["review"] = False
        elif a[i] == "--overwrite":
            opts["overwrite"] = True
        elif a[i].startswith("--") and a[i][2:] in known and i + 1 < len(a):
            opts[a[i][2:]] = a[i + 1]
            i += 1
        else:
            sys.exit(f"unknown or incomplete option {a[i]} (known: --no-review, --overwrite, --"
                     + ", --".join(sorted(known)) + ")")
        i += 1
    return opts


def load_look(path):
    d = json.load(open(path, encoding="utf-8"))
    if d.get("schema") != "develop.look/0":
        sys.exit(f"{path}: schema must be develop.look/0")
    values = {k: float(v) for k, v in d.get("values", {}).items()}
    per_shot = dict(d.get("per_shot", {}))
    for var, rule in per_shot.items():
        if (var, rule) not in RULES:
            sys.exit(f"{path}: no per-shot rule {var}: {rule} (known: " + ", ".join(f"{v}: {r}" for v, r in RULES) + ")")
        if var not in values:
            sys.exit(f"{path}: per-shot {var} needs the look's own value in values")
    if "bloomRoll" in per_shot and "bloomThr" not in per_shot:
        sys.exit(f"{path}: bloomRoll: judge rides on bloomThr: judge (it acts where the threshold was raised)")
    global gate_limits
    gate_limits = {k: float(v) for k, v in d.get("gate", {}).items()}
    unknown = set(gate_limits) - set(qgate.LIMITS)
    if unknown:
        sys.exit(f"{path}: unknown gate limits {sorted(unknown)} (known: {sorted(qgate.LIMITS)})")
    effects = d.get("effects", [])
    probe = Look(d["name"], values, effects=effects)
    declared = {key: {m.group(2) for m in PAT.finditer(text)} for key, text in probe.baked.items()}
    unused = [v for v in per_shot if not any(v in s for s in declared.values())]
    for v in unused:
        print(f"note: no node of this look uses {v} (is Bloom off?), so it is not judged")
        del per_shot[v]
    live = [key for key, s in declared.items() if s & set(per_shot)]
    return Look(d["name"], values, live, effects=effects), per_shot


def judge_frames(start, end, n):
    dur = end - start
    return sorted({start + min(dur - 1, int((k + 0.5) * dur / n)) for k in range(max(1, n))})


def way_back(item, name):
    """The version to go back to: the one the clip is on, or, when it is already on `name` from an earlier run, its
    only other local version (None when that is not unambiguous)."""
    before = item.GetCurrentVersion()
    if before and before.get("versionName") == name:
        others = [v for v in (item.GetVersionNameList(0) or []) if v != name]
        before = {"versionName": others[0], "versionType": 0, "inferred": True} if len(others) == 1 else None
    return before


def use_version(item, name):
    """Switch the clip to version `name`, made if the clip has none of that name."""
    if name not in (item.GetVersionNameList(0) or []):
        if not item.AddVersion(name, 0):
            raise rl.LiveError(f"AddVersion {name} failed on {item.GetName()}")
    if not item.LoadVersionByName(name, 0):
        raise rl.LiveError(f"LoadVersionByName {name} failed on {item.GetName()}")
    time.sleep(rl.SETTLE_APPLY)


def save_run(run, out):
    """run.json, written whole and then moved into place, so a run stopped at any moment leaves a readable way back."""
    path = os.path.join(out, "run.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(run, f, indent=1)
    os.replace(tmp, path)


def mean_added(a_png, b_png):
    import numpy as np
    a = qgate.imread(a_png).astype(np.float64)
    b = qgate.imread(b_png).astype(np.float64)
    return float((b - a).mean())


def open_frames(tl, it, fps, n):
    """Up to n frames of the clip, spread over it, where this clip is the top picture: a title or a B-roll clip on a
    higher track may cover part of it. Empty when it is covered at every place tried."""
    good = []
    for f in judge_frames(it.GetStart(), it.GetEnd(), max(n * 4, 12)):
        tl.SetCurrentTimecode(rl.tc(f, fps))
        cur = tl.GetCurrentVideoItem()
        if cur is not None and cur.GetUniqueId() == it.GetUniqueId():
            good.append(f)
    if len(good) <= n:
        return good
    return [good[int((k + 0.5) * len(good) / n)] for k in range(n)]


def find_timeline(project, name):
    for i in range(1, project.GetTimelineCount() + 1):
        t = project.GetTimelineByIndex(i)
        if t.GetName() == name:
            return t
    sys.exit(f"no timeline {name!r} in project {project.GetName()!r}: " + timeline_list(project))


def timeline_list(project):
    cur = project.GetCurrentTimeline()
    names = [project.GetTimelineByIndex(i).GetName() for i in range(1, project.GetTimelineCount() + 1)]
    return f"open timeline {cur.GetName() if cur else 'none'!r}; timelines: " + ", ".join(repr(n) for n in names)


def revert(path):
    run = json.load(open(os.path.join(path, "run.json") if os.path.isdir(path) else path, encoding="utf-8"))
    resolve = rl.connect()
    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None:
        sys.exit("no project is open in Resolve")
    if run.get("project") and project.GetName() != run["project"]:
        sys.exit(f"this run was on project {run['project']!r} and {project.GetName()!r} is open: open that project first")
    tl = find_timeline(project, run["timeline"])
    project.SetCurrentTimeline(tl)
    items = {it.GetUniqueId(): it for it in tl.GetItemListInTrack("video", run["track"]) or []}
    failed = 0
    for c in run["clips"]:
        if c.get("skipped"):
            continue
        it = items.get(c["id"])
        before = c.get("version_before") or {}
        if it is None or not before:
            print(f"{c['n']} {c['name']}: not found or no earlier version recorded, left as it is")
            failed += 1
            continue
        ok = it.LoadVersionByName(before["versionName"], before["versionType"])
        print(f"{c['n']} {c['name']}: back on {before['versionName']}: {ok}")
        failed += 0 if ok else 1
    print("The project is not saved. Save it in Resolve when you are happy.")
    if failed:
        sys.exit(f"{failed} clips did not go back")


def main():
    opts = args()
    if "revert" in opts:
        return revert(opts["revert"])
    try:
        look, per_shot = load_look(opts["look"])
    except (LookError, ValueError) as e:
        sys.exit(str(e))
    budget, nframes, track = float(opts["budget"]), int(opts["frames"]), int(opts["track"])
    if nframes < 1 or not 0.0 < budget < 1.0:
        sys.exit("--frames must be 1 or more and --budget between 0 and 1")
    try:
        wanted = {int(x) for x in opts["clips"].split(",")} if "clips" in opts else None
    except ValueError:
        sys.exit("--clips takes clip numbers separated by commas, such as 1,3,7")
    check_node()                              # the grade files need it: a clear stop before anything is installed
    resolve = rl.connect()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if project is None:
        sys.exit("no project is open in Resolve")
    if not opts.get("timeline"):              # never a guess: the grade lands only on the timeline you name
        sys.exit(f"Name the timeline to grade with --timeline. Nothing was changed.\n"
                 f"Project {project.GetName()!r}: " + timeline_list(project))
    tl = find_timeline(project, opts["timeline"])
    fps = rl.fps_of(tl)                       # refuses drop-frame before anything changes
    # dissolves list as items of type "transition"; clips are numbered without them
    items = [it for it in (tl.GetItemListInTrack("video", track) or []) if it.GetType() != "transition"]
    if wanted and not wanted <= set(range(1, len(items) + 1)):
        sys.exit(f"--clips names clips the track does not have (it has {len(items)})")
    # a clip already on the target version (an earlier run not reverted) has a way back only when one other local
    # version exists; otherwise --revert could not return it (a run on top of an unreverted run lost it)
    taken = []
    for n, it in enumerate(items, 1):
        if (wanted and n not in wanted) or it.GetMediaPoolItem() is None or not it.GetClipEnabled():
            continue                          # the run skips these clips, so they never block it
        names = it.GetVersionNameList(0) or []
        if any(v.casefold() == opts["version"].casefold() for v in names):
            taken.append(n)
        cur = (it.GetCurrentVersion() or {}).get("versionName")
        others = [v for v in names if v != opts["version"]]
        if cur == opts["version"] and len(others) != 1:
            sys.exit(f"clip {n} is already on version {cur} and has {len(others)} other versions, so the run could "
                     f"not record the way back: --revert the earlier run first, or switch the clip back by hand")
    if taken and not opts["overwrite"]:
        sys.exit(f"clips {taken} already have a colour version named {opts['version']!r}, and a run would replace that "
                 f"grade. Nothing was changed. Use --version with a new name, or --overwrite to replace it.")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.abspath(opts.get("out") or os.path.join(HERE, "runs", f"{re.sub(r'[^A-Za-z0-9 _-]', '_', tl.GetName())} {stamp}"))
    if os.path.exists(os.path.join(out, "run.json")):
        sys.exit(f"{out} already holds a run, and its way back would be lost: pick another --out")
    for sub in ("grades", "judge", "review"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    # the look's nodes: bake, validate (before anything reaches Resolve's LUT folder), install what changed, refresh
    folder = look.write_nodes(out)
    rl.validate(resolve, [os.path.join(folder, f) for f in look.files.values()] + [fx.path for fx in look.effects])
    dest = look.install(folder)
    rl.refresh_luts(project)
    look_only = look.grade(os.path.join(out, "grades", "look only.drx"), look_only=True)
    expect = look.node_count()

    was = {"timeline": project.GetCurrentTimeline(), "page": resolve.GetCurrentPage()}
    was["timecode"] = was["timeline"].GetCurrentTimecode()
    project.SetCurrentTimeline(tl)
    resolve.OpenPage("color")
    run = {"look": {"file": os.path.abspath(opts["look"]), "name": look.name, "values": look.values,
                    "per_shot": per_shot, "live": sorted(look.live)},
           "project": project.GetName(), "timeline": tl.GetName(), "track": track, "version": opts["version"],
           "overwrite": opts["overwrite"], "budget": budget, "frames": nframes, "started": stamp, "clips": []}
    save_run(run, out)
    print(f"{look.name} on project {project.GetName()!r}, timeline {tl.GetName()!r} track {track}: {len(items)} clips; "
          f"live nodes {sorted(look.live)}; {look.installed} node files written to {dest}")
    try:
        # each wanted clip's judge frames are found before any clip changes: a title or a B-roll clip on a higher track may
        # cover part of a clip, so judge where this clip shows. A clip covered at every place tried is skipped and named.
        judged = {}
        for n, it in enumerate(items, 1):
            if (wanted and n not in wanted) or it.GetMediaPoolItem() is None or not it.GetClipEnabled():
                continue
            judged[n] = open_frames(tl, it, fps, nframes)
        for n, it in enumerate(items, 1):
            if wanted and n not in wanted:
                continue
            t0 = time.time()
            rec = {"n": n, "name": it.GetName(), "id": it.GetUniqueId(), "start": it.GetStart(), "end": it.GetEnd()}
            run["clips"].append(rec)
            if it.GetMediaPoolItem() is None or not it.GetClipEnabled():
                rec["skipped"] = "not a media clip, or disabled"
                print(f"{n:3d} {it.GetName()}: skipped ({rec['skipped']})")
                continue
            frames = judged[n]
            if not frames:
                rec["skipped"] = "covered by a higher track at every place tried; grade that track with --track"
                print(f"{n:3d} {it.GetName()}: skipped ({rec['skipped']})")
                continue
            rec["version_before"] = way_back(it, opts["version"])
            save_run(run, out)                # the way back is on disk before this clip changes
            use_version(it, opts["version"])
            shot, rec["judged"] = {}, []

            def still_pass(tag):
                got = {}
                for f in frames:
                    tc = rl.tc(f, fps)
                    tl.SetCurrentTimecode(tc)
                    cur = tl.GetCurrentVideoItem()
                    if cur is None or cur.GetUniqueId() != it.GetUniqueId():
                        raise rl.LiveError(f"clip {n} is covered at {tc} by {cur.GetName() if cur else 'nothing'} "
                                           f"on a higher track; judge the top track")
                    # the tag before the frame: grab() clears <prefix>*.png first, so "001_86424" would also delete a
                    # night still named "001_86424_night_..." (every night judge still was lost that way)
                    got[f] = rl.grab(project, tl, tc, os.path.join(out, "judge"), f"{n:03d}{tag}_{f}")
                return got

            first = look_only
            if "ntStops" in per_shot:
                # the night key first: the stills go through Night at the look's own stops; the fewest stops of the
                # judged frames is kept (the most cautious: the least darkening)
                rl.apply_grade(it, look_only)
                for f, png in still_pass("_night").items():
                    st, med = night_stops(png, look.values["ntStops"])
                    rec["judged"].append({"frame": f, "still": os.path.relpath(png, out), "ntStops": st,
                                          "night_median": round(med, 4)})
                    shot["ntStops"] = min(shot.get("ntStops", st), st)
                # everything else is judged on the picture at the shot's own Night Exposure
                first = look.grade(os.path.join(out, "grades", f"{n:03d} look only.drx"),
                                   {"ntStops": shot["ntStops"]}, look_only=True)
            rl.apply_grade(it, first)
            stills = still_pass("")
            for f, png in stills.items():
                j = {"frame": f, "timecode": rl.tc(f, fps), "still": os.path.relpath(png, out)}
                if "bloomThr" in per_shot:
                    thr, share = auto_threshold(png, look.values["bloomThr"], budget)
                    j["bloomThr"], j["share_above_look"] = thr, round(share, 4)
                    shot["bloomThr"] = max(shot.get("bloomThr", thr), thr)
                rec["judged"].append(j)
            if "bloomRoll" in per_shot:
                # rule one's companion: a shot bright enough to raise the threshold also gets the soft shoulder
                own = look.values["bloomRoll"]
                raised = shot.get("bloomThr", look.values["bloomThr"]) > look.values["bloomThr"]
                shot["bloomRoll"] = max(own, ROLL_RAISED) if raised else own
            rec["shot"] = shot
            grade = look.grade(os.path.join(out, "grades", f"{n:03d}.drx"), shot)
            graph = rl.apply_grade(it, grade)
            rec["grade"] = os.path.relpath(grade, out)
            rec["nodes"] = graph.GetNumNodes()
            if rec["nodes"] != expect:
                raise rl.LiveError(f"clip {n}: {rec['nodes']} nodes after the apply, expected {expect}")
            if opts["review"]:
                mid = sorted(stills)[len(stills) // 2]
                png = rl.grab(project, tl, rl.tc(mid, fps), os.path.join(out, "review"), f"{n:03d}_{mid}")
                rec["review"] = {"frame": mid, "look_only": os.path.relpath(stills[mid], out),
                                 "graded": os.path.relpath(png, out),
                                 "mean_added": round(mean_added(stills[mid], png), 3)}
                # the quality gate on the look node alone against the whole look; flags only, never a stop
                g = qgate.gate(qgate.load(stills[mid]), qgate.load(png))
                g["flags"] = [k for k, lim in dict(qgate.LIMITS, **gate_limits).items() if k in g and g[k] > lim]
                rec["gate"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in g.items()}
            rec["seconds"] = round(time.time() - t0, 1)
            vals = ", ".join(f"{k} {v:g}" for k, v in shot.items()) or "no per-shot values"
            added = f", review {rec['review']['mean_added']:+.2f}/255" if "review" in rec else ""
            if "gate" in rec:
                added += f", gate: clip {rec['gate']['clip_added'] * 100:+.1f}%, energy {rec['gate']['energy'] * 100:+.0f}%" \
                         + (f", flags {rec['gate']['flags']}" if rec["gate"]["flags"] else "")
            print(f"{n:3d} {it.GetName()}: {vals}{added} ({rec['seconds']} s)", flush=True)
            save_run(run, out)
    finally:
        save_run(run, out)
        project.SetCurrentTimeline(was["timeline"])
        was["timeline"].SetCurrentTimecode(was["timecode"])
        resolve.OpenPage(was["page"])
        print("run log:", os.path.join(out, "run.json"))
        print("The project is not saved. Save it in Resolve when you are happy.")


if __name__ == "__main__":
    # a clip or project name outside the console's code page must never stop a run half way
    sys.stdout.reconfigure(errors="backslashreplace")
    sys.stderr.reconfigure(errors="backslashreplace")
    try:
        main()
    except rl.LiveError as e:
        sys.exit(f"stopped: {e}")
