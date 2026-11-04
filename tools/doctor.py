"""Check this computer for what the Claude Resolve Editing Suite needs. It changes nothing.

usage: python -I tools/doctor.py [--resolve]
--resolve also connects to a running Resolve and reads its name, version and open project. It reads only.
Exit 0 when the core is ready (Resolve found, suite installed, Python packages, Node, FFmpeg).
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

LUT = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "Blackmagic Design", "DaVinci Resolve", "Support", "LUT")
RESOLVE = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Blackmagic Design", "DaVinci Resolve", "Resolve.exe")
VST3 = os.path.join(os.environ.get("CommonProgramFiles", r"C:\Program Files\Common Files"), "VST3", "Develop")
problems = 0


def line(ok, what, fix=""):
    global problems
    if ok is False:
        problems += 1
    mark = {True: "ok     ", False: "MISSING", None: "note   "}[ok]
    print(f"{mark} {what}" + (f": {fix}" if fix else ""))


def user_site_has(mod):
    """The package sits in this user's own site folder, which python -I leaves out."""
    try:
        import site
        return os.path.isdir(os.path.join(site.getusersitepackages(), mod))
    except Exception:  # noqa: BLE001
        return False


def version(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip().splitlines()[0]
    except (OSError, IndexError, subprocess.SubprocessError):
        return None


def main():
    sys.stdout.reconfigure(errors="backslashreplace")
    print(f"Python {sys.version.split()[0]} at {sys.executable}")
    line(os.name == "nt" or None, "Windows" if os.name == "nt" else f"this is {sys.platform}; the suite is built and tested on Windows only")
    line(sys.version_info >= (3, 10), f"Python 3.10 or newer (tested on 3.12)", "" if sys.version_info >= (3, 10) else "install Python 3.12 from python.org")
    line(os.path.isfile(RESOLVE), "DaVinci Resolve", "" if os.path.isfile(RESOLVE) else "install DaVinci Resolve Studio; its scripting and DCTL effects are Studio features")
    installed = os.path.isfile(os.path.join(LUT, "Develop", "Develop 1 Light.dctl"))
    line(installed, "the suite's effects are installed", "" if installed else "double-click Install.bat in this folder")
    line(os.path.isdir(VST3) or None, "the audio plugins are installed" if os.path.isdir(VST3) else "the audio plugins are not installed; Install.bat offers them")
    for mod, pkg in (("numpy", "numpy"), ("cv2", "opencv-python"), ("faster_whisper", "faster-whisper")):
        found = importlib.util.find_spec(mod) is not None
        fix = "python -m pip install -r requirements.txt"
        if not found and user_site_has(mod):
            fix = "it is installed for this user only, which python -I does not read: run the tools without -I"
        line(found, f"Python package {pkg}", "" if found else fix)
    node = version(["node", "--version"])
    m = re.match(r"v(\d+)\.(\d+)", node or "")
    have = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    good = have >= (23, 8) or (22, 15) <= have < (23, 0)
    line(good, f"Node 22.15 or newer ({node or 'not found'})", "" if good else "install the current Node from nodejs.org")
    for tool in ("ffmpeg", "ffprobe"):
        line(shutil.which(tool) is not None, tool, "" if shutil.which(tool) else "install FFmpeg and put it on PATH (winget install Gyan.FFmpeg)")
    m = re.match(r"ffmpeg version n?(\d+)\.", version(["ffmpeg", "-version"]) or "")
    if m and int(m.group(1)) < 7:
        line(False, f"FFmpeg 7 or newer (found {m.group(1)})", "the cut tools need it: winget upgrade Gyan.FFmpeg")
    for mod in ("scipy", "soundfile", "librosa", "av", "PIL", "matplotlib"):
        if importlib.util.find_spec(mod) is None:
            line(None, f"optional package {mod} is not installed (only the shot tools need it): python -m pip install -r requirements-shot-tools.txt")
    if "--resolve" in sys.argv:
        import resolve_live as rl
        try:
            r = rl.connect()
            p = r.GetProjectManager().GetCurrentProject()
            t = p.GetCurrentTimeline() if p else None
            name = r.GetProductName()
            line("Studio" in name, f"{name} {r.GetVersionString()} answers; open project {p.GetName() if p else None!r}, open timeline {t.GetName() if t else None!r}",
                 "" if "Studio" in name else "the suite needs DaVinci Resolve Studio; the free edition has no scripting or DCTL")
        except rl.LiveError as e:
            line(False, "Resolve scripting", f"{e}. In Resolve: Preferences > System > General > External scripting using: Local. "
                 "The free edition has no scripting: the suite needs Resolve Studio")
    print("Ready." if not problems else f"{problems} things to fix first.")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
