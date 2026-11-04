"""Lay an EDL's cut on a new DaVinci Resolve timeline, on the original media, so the edit stays open to change.

It reads the keep ranges of an EDL (from cut-silences.mjs, compose_edl.py or snap_edl.py) and appends them end to end on
a new timeline in the project open in Resolve, picture and sound linked. The timeline takes the clip's frame rate and
size. Each sound join gets a one-frame fade. Nothing that exists is changed: the timeline name must be new, and the file
is imported only when the media pool does not hold it yet. The project is not saved, so closing Resolve without saving
leaves no trace.

usage: python -I to_resolve.py <source media> <edl.json> --timeline <new name>

Needs DaVinci Resolve Studio running with external scripting set to Local and a project open. Use a constant frame rate
source: a phone's variable rate drifts against the EDL's seconds. MIT License."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import resolve_live as rl  # noqa: E402


def args():
    a = sys.argv[1:]
    if "--timeline" not in a or a.index("--timeline") + 1 >= len(a):
        sys.exit(__doc__)
    k = a.index("--timeline")
    name = a[k + 1]
    rest = a[:k] + a[k + 2:]
    if len(rest) != 2 or not name.strip():
        sys.exit(__doc__)
    return os.path.abspath(rest[0]), rest[1], name


def find_clip(folder, path):
    """The media pool item holding this file, in any folder, or None."""
    want = os.path.normcase(os.path.normpath(path))
    for clip in folder.GetClipList() or []:
        have = clip.GetClipProperty("File Path") or ""
        if have and os.path.normcase(os.path.normpath(have)) == want:
            return clip
    for sub in folder.GetSubFolderList() or []:
        found = find_clip(sub, path)
        if found:
            return found
    return None


def frames_of(ranges, fps):
    """Each keep range as (first frame, end frame). AppendToTimeline's endFrame is exclusive: measured live on Resolve
    21.1, startFrame 30 and endFrame 90 lays 60 frames."""
    out = []
    for r in ranges:
        first, end = int(round(r["start"] * fps)), int(round(r["end"] * fps))
        if end > first:
            out.append((first, end))
    return out


def match_clip(timeline, clip, fps):
    """Give the new timeline the clip's rate and size. It must run before any clip is on the timeline."""
    done = bool(timeline.SetSetting("useCustomSettings", "1"))
    done = bool(timeline.SetSetting("timelineFrameRate", f"{fps:g}")) and done
    size = str(clip.GetClipProperty("Resolution") or "").lower().split("x")
    if len(size) == 2 and all(s.strip().isdigit() for s in size):
        done = bool(timeline.SetSetting("timelineResolutionWidth", size[0].strip())) and done
        done = bool(timeline.SetSetting("timelineResolutionHeight", size[1].strip())) and done
    return done


def main():
    src, edl_path, name = args()
    if not os.path.isfile(src):
        sys.exit(f"no such file: {src}")
    ranges = json.load(open(edl_path, encoding="utf-8")).get("keep_ranges")
    if not ranges:
        sys.exit(f"{edl_path} has no keep_ranges")
    resolve = rl.connect()
    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None:
        sys.exit("no project is open in Resolve")
    for i in range(1, project.GetTimelineCount() + 1):
        if project.GetTimelineByIndex(i).GetName() == name:
            sys.exit(f"project {project.GetName()!r} already has a timeline named {name!r}: pick a new name. Nothing was changed.")
    pool = project.GetMediaPool()
    clip = find_clip(pool.GetRootFolder(), src)
    imported = False
    if clip is None:
        got = pool.ImportMedia([src])
        if not got:
            sys.exit(f"Resolve could not import {src}")
        clip, imported = got[0], True
    fps = float(clip.GetClipProperty("FPS") or 0)
    if fps <= 0:
        sys.exit(f"Resolve reports no frame rate for {src}")
    spans = frames_of(ranges, fps)
    if not spans:
        sys.exit("every keep range is shorter than a frame")
    was = project.GetCurrentTimeline()
    timeline = pool.CreateEmptyTimeline(name)
    if not timeline:
        sys.exit(f"Resolve could not make a timeline named {name!r}")
    project.SetCurrentTimeline(timeline)
    matched = match_clip(timeline, clip, fps)
    placed = pool.AppendToTimeline([{"mediaPoolItem": clip, "startFrame": a, "endFrame": b} for a, b in spans])
    if not placed:
        sys.exit(f"Resolve placed no clips on {name!r}. The empty timeline stays; delete it by hand.")
    video = [t for t in (timeline.GetItemListInTrack("video", 1) or []) if t.GetType() != "transition"]
    audio = timeline.GetItemListInTrack("audio", 1) or []
    laid = video or audio
    for k, t in enumerate(audio):             # a click guard at every join; the very first and last edge stay as cut
        t.SetFades({"FadeIn": 0 if k == 0 else 1, "FadeOut": 0 if k == len(audio) - 1 else 1})
    timeline_fps = float(timeline.GetSetting("timelineFrameRate") or fps)
    want = sum(b - a for a, b in spans) / fps
    have = sum(t.GetDuration() for t in laid) / timeline_fps
    print(f"project {project.GetName()!r}: new timeline {name!r} is open; the timeline that was open is unchanged"
          + (f" ({was.GetName()!r})" if was else ""))
    print(f"{src}: {'imported' if imported else 'already in the media pool'}, {fps:g} fps; timeline {timeline_fps:g} fps"
          + (f", {timeline.GetSetting('timelineResolutionWidth')}x{timeline.GetSetting('timelineResolutionHeight')}" if matched else ""))
    print(f"{len(spans)} keep ranges: {len(video)} video clips, {len(audio)} audio clips, {have:.2f} s laid, {want:.2f} s asked")
    if len(laid) != len(spans) or abs(have - want) > max(2 / timeline_fps, 0.002 * want):
        sys.exit("the timeline does not match the EDL: check it by eye before you use it")
    if not matched or abs(timeline_fps - fps) > 0.01:
        print(f"note: the timeline could not take the clip's settings, so Resolve fits the clip's {fps:g} fps to {timeline_fps:g} fps")


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")
    try:
        main()
    except rl.LiveError as e:
        sys.exit(f"stopped: {e}")
