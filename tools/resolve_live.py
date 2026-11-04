"""Talking to a running DaVinci Resolve Studio through its external scripting API.

Resolve must allow it: Preferences > System > General > External scripting using: Local.
"""
import glob
import os
import re
import sys
import time

MODULES = [r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
           "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules",
           "/opt/resolve/Developer/Scripting/Modules"]


# Pauses that let Resolve finish work it does in the background (a still's image is written after GrabStill
# returns; an applied grade compiles its DCTLs).
SETTLE_APPLY = 1.0
SETTLE_GRAB = 0.3
SETTLE_DELETE = 0.2
# After the playhead moves, the viewer shows the new frame a moment later: GetCurrentTimecode already reads the new
# timecode while GrabStill still takes the old frame (a still meant for clip 1 of the shots
# timeline came back as clip 7, where the playhead had been). Every move waits this long before a grab.
SETTLE_SEEK = 1.0


class LiveError(Exception):
    pass


def connect():
    for m in MODULES:
        if os.path.isdir(m) and m not in sys.path:
            sys.path.append(m)
    try:
        import DaVinciResolveScript as dvr
    except ImportError:
        raise LiveError("DaVinciResolveScript not found: is DaVinci Resolve Studio installed?")
    resolve = dvr.scriptapp("Resolve")
    if resolve is None:
        raise LiveError("Resolve is not answering: start it and allow external scripting (Local)")
    version = re.match(r"(\d+)\.(\d+)", resolve.GetVersionString() or "")
    if version and (int(version.group(1)), int(version.group(2))) < (21, 1):
        raise LiveError(f"this needs DaVinci Resolve Studio 21.1 or newer, and {resolve.GetVersionString()} is running")
    return resolve


def fps_of(timeline):
    if str(timeline.GetSetting("timelineDropFrameTimecode")) not in ("0", "False", "false", ""):
        raise LiveError("drop-frame timecode is not supported")
    return int(round(float(timeline.GetSetting("timelineFrameRate"))))


def tc(frame, fps):
    s, f = divmod(int(frame), fps)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


def apply_grade(item, drx):
    """Graph.ApplyGradeFromDRX, once more after 1.5 s if the first call returns None. Returns a NEW Graph.

    Applying a grade destroys the clip's old graph, and the Graph object it was called on goes stale: any later call
    on it makes Resolve's main thread call into freed memory and the whole application crashes. So every Graph is fetched fresh from the item after an apply and never kept across one.
    """
    ok = item.GetNodeGraph().ApplyGradeFromDRX(drx, 0)
    if ok is None:
        time.sleep(1.5)
        ok = item.GetNodeGraph().ApplyGradeFromDRX(drx, 0)
    if not ok:
        raise LiveError(f"ApplyGradeFromDRX returned {ok!r} for {drx}")
    time.sleep(SETTLE_APPLY)
    return item.GetNodeGraph()


def _stills(folder, prefix):
    """The stills ExportStills wrote for exactly this prefix (<prefix>_1.1.2.png): never a longer prefix's
    (clearing "Streak" deleted "Streak100_1.1.2.png"), and a folder name with [ ] stays literal."""
    pat = re.compile(re.escape(prefix) + r"_\d+(?:\.\d+)*\.png", re.I)
    return [f for f in glob.glob(os.path.join(glob.escape(folder), glob.escape(prefix) + "_*.png"))
            if pat.fullmatch(os.path.basename(f))]


def grab(project, timeline, timecode, folder, prefix):
    """A still of the frame at timecode, exported as PNG; only the still this call grabbed is deleted."""
    os.makedirs(folder, exist_ok=True)
    for old in _stills(folder, prefix):
        os.remove(old)
    if timeline.GetCurrentTimecode() != timecode:
        timeline.SetCurrentTimecode(timecode)
        if timeline.GetCurrentTimecode() != timecode:     # a move right after another call can be dropped: one retry
            time.sleep(SETTLE_DELETE)
            timeline.SetCurrentTimecode(timecode)
    got = timeline.GetCurrentTimecode()
    if got != timecode:
        raise LiveError(f"playhead at {got}, wanted {timecode}")
    # always, also when a caller moved the playhead: the timecode reads right before the viewer shows that frame
    time.sleep(SETTLE_SEEK)
    still = timeline.GrabStill()
    if not still:
        raise LiveError(f"GrabStill failed at {timecode} (is the Color page open?)")
    time.sleep(SETTLE_GRAB)                   # the still's image is written in the background
    album = project.GetGallery().GetCurrentStillAlbum()
    try:
        ok = album.ExportStills([still], folder, prefix, "png")
    finally:
        album.DeleteStills([still])
        time.sleep(SETTLE_DELETE)
    files = _stills(folder, prefix)
    if not ok or len(files) != 1:
        raise LiveError(f"ExportStills gave {ok!r} and {len(files)} files for {prefix}")
    return files[0]


def grab_after(project, timeline, item, drx, timecode, folder, prefix):
    """Apply a grade to the item, then a still at timecode (the playhead must land on that item)."""
    apply_grade(item, drx)
    return grab(project, timeline, timecode, folder, prefix)


def refresh_luts(project):
    """Project.RefreshLUTList twice. A DCTL plugin node whose file changed its slider list at the same path keeps
    running the old layout after one refresh, waiting does not help, and the second refresh loads the new one."""
    for _ in range(2):
        project.RefreshLUTList()
        time.sleep(SETTLE_APPLY)


def validate(resolve, paths):
    """resolve.ValidateDCTL on each file: a DCTL that fails on a LUT node passes the picture through silently."""
    bad = {}
    for p in paths:
        err = resolve.ValidateDCTL(open(p, encoding="utf-8").read())
        if err is not None:
            bad[p] = err
    if bad:
        raise LiveError("DCTL does not validate: " + "; ".join(f"{os.path.basename(k)}: {v}" for k, v in bad.items()))
