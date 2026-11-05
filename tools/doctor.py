"""Check this computer for what the Claude Resolve Editing Suite needs. It changes nothing.

usage: python -I tools/doctor.py [--resolve]
--resolve also connects to a running Resolve and reads its name, version and open project. It reads only.
Exit 0 when every part of the suite is in place: the suite needs all of it.
"""
import glob
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
        base = os.path.join(site.getusersitepackages(), mod)
        return os.path.isdir(base) or os.path.isfile(base + ".py")
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
    line(os.name == "nt" or None, "Windows" if os.name == "nt" else f"this is {sys.platform}; this suite is for Windows only")
    line(sys.version_info >= (3, 10), f"Python 3.10 or newer (tested on 3.12)", "" if sys.version_info >= (3, 10) else "install Python 3.12 from python.org")
    line(os.path.isfile(RESOLVE), "DaVinci Resolve", "" if os.path.isfile(RESOLVE) else "install DaVinci Resolve Studio; its scripting and DCTL effects are Studio features")
    installed = os.path.isfile(os.path.join(LUT, "Develop", "Develop 1 Light.dctl"))
    line(installed, "the suite's effects are installed", "" if installed else "double-click Install.bat in this folder")
    line(os.path.isdir(VST3), "the audio plugins are installed", "" if os.path.isdir(VST3) else "double-click Install.bat in this folder, and click Yes on the Windows prompt")
    for mod, pkg in (("numpy", "numpy"), ("cv2", "opencv-python"), ("faster_whisper", "faster-whisper"), ("scipy", "scipy"), ("soundfile", "soundfile"),
                     ("librosa", "librosa"), ("numba", "numba"), ("av", "av"), ("PIL", "Pillow"), ("matplotlib", "matplotlib"), ("pyloudnorm", "pyloudnorm"),
                     ("torch", "torch"), ("transformers", "transformers")):
        found = importlib.util.find_spec(mod) is not None
        fix = "python -m pip install -r requirements.txt -r requirements-shot-tools.txt"
        if not found and user_site_has(mod):
            fix = "it is installed for this user only, which python -I does not read: see step 2 of .claude/skills/setup/SKILL.md"
        line(found, f"Python package {pkg}", "" if found else fix)
    node = version(["node", "--version"])
    m = re.match(r"v(\d+)\.(\d+)", node or "")
    have = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    good = have >= (24, 0)
    line(good, f"Node 24 or newer ({node or 'not found'})", "" if good else "install the current Node LTS from nodejs.org")
    line(shutil.which("git") is not None, "Git, which brings bash", "" if shutil.which("git") else "winget install -e --id Git.Git")
    for tool in ("ffmpeg", "ffprobe"):
        line(shutil.which(tool) is not None, tool, "" if shutil.which(tool) else "install FFmpeg and put it on PATH (winget install Gyan.FFmpeg)")
    m = re.match(r"ffmpeg version n?(\d+)\.", version(["ffmpeg", "-version"]) or "")
    if m and int(m.group(1)) < 7:
        line(False, f"FFmpeg 7 or newer (found {m.group(1)})", "the cut tools need it: winget upgrade Gyan.FFmpeg")
    hub = os.environ.get("HF_HUB_CACHE") or os.path.join(os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface"), "hub")
    # the weights file, since an interrupted download leaves the folder behind
    for folder, weights, label in (("models--Systran--faster-whisper-medium.en", "model.bin", "the speech model"), ("models--depth-anything--Depth-Anything-V2-Small-hf", "model.safetensors", "the depth model")):
        found = bool(glob.glob(os.path.join(glob.escape(os.path.join(hub, folder)), "snapshots", "*", weights)))
        line(found, label, "" if found else "step 2 of .claude/skills/setup/SKILL.md downloads it")
    root = os.path.dirname(HERE)
    for folder, label in (("animation/animate", "the animation tools"), ("animation/reanimate/scripts", "the motion copier")):
        found = os.path.isdir(os.path.join(root, folder, "node_modules", "playwright"))
        line(found, label, "" if found else "step 7 of .claude/skills/setup/SKILL.md installs it")
    browsers = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
    found = bool(glob.glob(os.path.join(glob.escape(browsers), "chromium-*")))
    line(found, "the animation browser", "" if found else "step 7 of .claude/skills/setup/SKILL.md installs it")
    npm = shutil.which("npm")
    cache = (version([npm, "config", "get", "cache"]) if npm else None) or os.path.join(os.environ.get("LOCALAPPDATA", ""), "npm-cache")
    found = False
    for package in glob.glob(os.path.join(glob.escape(cache), "_npx", "*", "node_modules", "hyperframes", "package.json")):
        try:
            with open(package, encoding="utf-8") as f:
                found = found or json.load(f).get("version") == "0.8.206"
        except (OSError, ValueError):
            pass
    line(found, "HyperFrames 0.8.206", "" if found else "step 6 of .claude/skills/setup/SKILL.md installs it")
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
