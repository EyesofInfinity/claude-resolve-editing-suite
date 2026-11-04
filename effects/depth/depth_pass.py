"""The depth pass: Resolve 21's own AI Depth Map (the Fusion DepthMap tool) run over a clip and rendered as a
16-bit lossless movie (FFV1 RGBA 16-bit in a .mov), grey with near white. Develop Depth's renderer (depthfx.py)
reads it beside the picture.

A scratch timeline "Develop depth pass" in the open project is rebuilt for every run at the clip's own frame rate
(a 29.97 clip on a 24 fps timeline would drop frames and the depth would stop lining up with the picture), 1920 x
1080, the clip letterboxed as Resolve fits it (the same fit as apply.py). The clip gets a Fusion comp MediaIn ->
DepthMap -> MediaOut; only the render job this script adds is deleted afterwards.

usage: python -I depth_pass.py <clip or b-roll catalog idx> <out.mov> [--start s] [--dur s] [--mode Better|Faster] [--deflicker 1]
"""
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools"))
import resolve_live as rl

sys.path.insert(0, os.path.join(REPO, "tools"))
import develop_paths

NAME = "Develop depth pass"
PROJECT = os.environ.get("DEVELOP_PROJECT") or None
CATALOG = develop_paths.broll_catalog()
RATES = {23.976: "24", 24.0: "24", 25.0: "25", 29.97: "30", 30.0: "30", 50.0: "50", 59.94: "60", 60.0: "60"}

def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=r_frame_rate,nb_frames", "-of", "default=nw=1:nk=1", path],
                       capture_output=True, text=True, check=True).stdout.split()
    a, b = r[0].split("/") if "/" in r[0] else (r[0], "1")
    return float(a) / float(b)

def rate_string(fps):
    best = min(RATES, key=lambda k: abs(k - fps))
    if abs(best - fps) > 0.01:
        sys.exit(f"no timeline rate for {fps:.3f} fps")
    return RATES[best]

def key(p):
    return os.path.normcase(os.path.normpath(p))

def find_clip(folder, path):
    for c in folder.GetClipList() or []:
        if key(c.GetClipProperty("File Path") or "") == key(path):
            return c
    for s in folder.GetSubFolderList() or []:
        h = find_clip(s, path)
        if h:
            return h
    return None

def catalog_path(idx):
    return develop_paths.clip_from_index(idx)

def arg(a, name, default):
    return a[a.index(name) + 1] if name in a else default

def main():
    a = sys.argv[1:]
    src, out = (catalog_path(int(a[0])) if a[0].isdigit() else os.path.abspath(a[0])), os.path.abspath(a[1])
    start, dur = float(arg(a, "--start", 0)), float(arg(a, "--dur", 0))
    mode, deflicker = arg(a, "--mode", "Better"), float(arg(a, "--deflicker", 1))
    fps = probe(src)
    resolve = rl.connect()
    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None:
        sys.exit("open a project in Resolve first")
    if PROJECT and project.GetName() != PROJECT:
        sys.exit(f"wrong project {project.GetName()!r} (DEVELOP_PROJECT asks for {PROJECT!r})")
    page = resolve.GetCurrentPage() or "edit"
    resolve.OpenPage("edit")
    mp = project.GetMediaPool()
    root = mp.GetRootFolder()
    for i in range(project.GetTimelineCount(), 0, -1):
        if project.GetTimelineByIndex(i).GetName() == NAME:
            mp.DeleteTimelines([project.GetTimelineByIndex(i)])
    mp.SetCurrentFolder(root)
    clip = find_clip(root, src) or (mp.ImportMedia([src]) or [None])[0]
    if clip is None:
        sys.exit(f"Resolve did not import {src}")
    pool_fps = float(clip.GetClipProperty("FPS"))
    tl = mp.CreateEmptyTimeline(NAME)
    project.SetCurrentTimeline(tl)
    for k, v in (("useCustomSettings", "1"), ("timelineResolutionWidth", "1920"),
                 ("timelineResolutionHeight", "1080"), ("timelineFrameRate", rate_string(pool_fps)),
                 ("timelineOutputResolutionWidth", "1920"), ("timelineOutputResolutionHeight", "1080")):
        if not tl.SetSetting(k, v):
            print(f"timeline setting {k}={v} refused", flush=True)
    got = float(tl.GetSetting("timelineFrameRate"))
    if abs(got - pool_fps) > 0.04:
        sys.exit(f"timeline runs at {got} fps, the clip at {pool_fps:.3f} in the pool: frames would not line up")
    total = int(clip.GetClipProperty("Frames") or 0)
    s0 = int(np.ceil(start * fps - 1e-6))
    n = int(round(dur * fps)) if dur else total - s0
    item = mp.AppendToTimeline([{"mediaPoolItem": clip, "startFrame": s0, "endFrame": s0 + n, "trackIndex": 1,
                                 "recordFrame": tl.GetStartFrame(), "mediaType": 1}])[0]
    comp = item.AddFusionComp()
    mi, mo = comp.FindTool("MediaIn1"), comp.FindTool("MediaOut1")
    dm = comp.AddTool("DepthMap", -32768, -32768)
    if not (mi and mo and dm):
        sys.exit("the Fusion comp is missing MediaIn, MediaOut or DepthMap")
    dm.ConnectInput("Input", mi)
    mo.ConnectInput("Input", dm)
    dm.SetInput("Mode", mode)
    dm.SetInput("DepthMapPreview", 1)
    dm.SetInput("DetailRecovery", deflicker)
    got_n = item.GetDuration()
    if got_n != n or item.GetLeftOffset() != s0:
        sys.exit(f"the timeline holds {got_n} frames from {item.GetLeftOffset()}, asked {n} from {s0}")
    print(f"depth: {os.path.basename(src)} frames {s0} to {s0 + n - 1} (file {fps:.3f} fps, pool {pool_fps:g}), "
          f"mode {dm.GetInput('Mode')}, "
          f"deflicker {dm.GetInput('DetailRecovery')}", flush=True)
    resolve.OpenPage("deliver")
    before = {j["JobId"] for j in project.GetRenderJobList()}
    if not project.SetCurrentRenderFormatAndCodec("mov", "FFV1RGBA_16"):
        sys.exit("FFV1 RGBA 16-bit refused")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    stem = os.path.splitext(os.path.basename(out))[0]
    if not project.SetRenderSettings({"SelectAllFrames": True, "TargetDir": os.path.dirname(out), "CustomName": stem,
                                      "ExportVideo": True, "ExportAudio": False, "FormatWidth": 1920,
                                      "FormatHeight": 1080}):
        sys.exit("SetRenderSettings refused")
    job = project.AddRenderJob()
    t0, status = time.time(), None
    try:
        if not job or not project.StartRendering(job):
            sys.exit(f"render did not start (job {job})")
        while project.IsRenderingInProgress():
            time.sleep(1)
        status = project.GetRenderJobStatus(job).get("JobStatus")
        print(f"render {status} in {time.time() - t0:.0f} s -> {out}", flush=True)
    finally:
        if job:
            project.DeleteRenderJob(job)
        print("other render jobs untouched:", {j["JobId"] for j in project.GetRenderJobList()} == before)
        resolve.OpenPage(page)
        resolve.GetProjectManager().SaveProject()
    if status != "Complete":
        sys.exit(1)
    made = [f for f in os.listdir(os.path.dirname(out)) if f.startswith(stem)]
    if os.path.basename(out) not in made:
        sys.exit(f"Resolve wrote {made}, not {os.path.basename(out)}")

if __name__ == "__main__":
    main()
