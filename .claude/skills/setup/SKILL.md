---
name: setup
description: Set up the Claude Resolve Editing Suite on this computer for a new user, start to finish, automatically. Use when the user says set up, install, get started or first time, or when tools/doctor.py reports anything missing.
---

# Set up the suite

You do this for the user. They do only what a person must do: give one OK, install Resolve Studio if it is missing, click Yes on
the Windows prompts, and set one preference in Resolve.

**Nothing in this suite is optional. Install all of it, in this one run.** Never call a part "optional" or an "extra", and never offer to add it later. A user who asks for
a video must never wait on an install.

Work in order. For each step: check first, skip it if it is done, then verify. Tell the user in one short line what you are doing.
Run every command from this folder.

This suite is for Windows only. If this computer is not Windows (your environment lists the platform), tell the user that, and stop.

## 0. Get one OK

Tell the user, in plain words, and wait for a yes:

> I will set up the whole suite on this computer, so nothing is left to install later. You need DaVinci Resolve Studio, the paid edition. I will install what is missing: Python, Node, Git and FFmpeg
> with Windows' own installer (winget), all the Python packages including PyTorch (a few GB), HyperFrames with its browser (about 160 MB plus
> Chrome), the animation tools (about 700 MB), a speech model (about 1.5 GB) and a depth model (about 99 MB). Then I will put the effects and
> audio plugins into DaVinci Resolve. Windows will ask for admin rights for the plugins, and also for Node and Git if they are missing: click Yes each time. I will also add HyperFrames' guides to your
> Claude folder, and ask you to set one preference in Resolve. This can take a while, and you can do other work while it runs. Nothing else on your computer changes. Shall I go ahead?

If the user says no, install nothing. Tell them the suite needs all of it, and that they can say yes at any time.

## 1. Python, Node, FFmpeg

Check each one:

```
python --version
node --version
git --version
ffmpeg -version
```

Python must be 3.10 or newer (a line that says the Microsoft Store, or no version, means it is missing). Node must be 24 or
newer. Git brings the `bash` that the B-roll tool runs. Install what is missing, one at a time:

```
winget install -e --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements
winget install -e --id OpenJS.NodeJS.LTS --source winget --accept-package-agreements --accept-source-agreements
winget install -e --id Git.Git --source winget --accept-package-agreements --accept-source-agreements
winget install -e --id Gyan.FFmpeg --source winget --accept-package-agreements --accept-source-agreements
```

A new install is not on this session's PATH yet. In PowerShell, reload it inside the same command:

```
$env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User"); python --version
```

If a tool still reads as missing, ask the user to close and reopen Claude Code, then carry on from this step. If winget is not on the
computer, send the user to python.org, nodejs.org and gyan.dev/ffmpeg/builds, one link at a time.

## 2. Python packages

```
nvidia-smi
```

If that prints an NVIDIA card, install PyTorch's GPU build first, so the depth and shot tools run on the graphics card:

```
python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
```

Then install everything:

```
python -m pip install -r requirements.txt -r requirements-shot-tools.txt
```

If pip says "Defaulting to user installation", this Python's folder is read-only, and the suite's `python -I` commands cannot read the user folder. Stop, install Python 3.12
for this user with python.org's "Install Now", put it first on PATH, and run this step again.

Then download the models now, so no job stops for them later:

```
python -c "from faster_whisper import WhisperModel; WhisperModel('medium.en', device='cpu', compute_type='int8')"
python -c "from huggingface_hub import snapshot_download; snapshot_download('depth-anything/Depth-Anything-V2-Small-hf')"
```

## 3. DaVinci Resolve Studio

Run `python -I tools/doctor.py` and read the line for DaVinci Resolve. If it is missing, stop this step and tell the user:

> You need DaVinci Resolve Studio, the paid edition. The free edition has no scripting or DCTL. Get it from
> blackmagicdesign.com/products/davinciresolve, install it, open it once to activate it, close it, and tell me when that is done.

You cannot buy or activate it for them. Wait for their word, then check again.

## 4. Install the effects and plugins

Ask the user to close Resolve. Check that it is closed:

```
powershell -NoProfile -Command "if (Get-Process Resolve -ErrorAction SilentlyContinue) { 'still open' } else { 'closed' }"
```

Tell the user: "Windows will now ask for admin rights for the audio plugins. Please click Yes." Then run the installer:

```
powershell -NoProfile -ExecutionPolicy Bypass -File installer/install.ps1 -Yes
```

It prints how many files went where: 65 effects, 43 Fusion tools, 6 audio plugins. If the user clicks No, the effects still install and the
audio plugins do not. Run `python -I tools/doctor.py` and check the two lines for the effects and the plugins.

## 5. Turn on scripting in Resolve

The user must do this once. Ask them to:

1. Open DaVinci Resolve and open or create any project.
2. Open the menu DaVinci Resolve > Preferences > System > General.
3. Set **External scripting using** to **Local**, and click Save.
4. Close Resolve and open it again, with a project open, and tell you when the project is on screen.

Then connect once, and only after they say so. Polling while Resolve starts can stop its script server:

```
python -I tools/doctor.py --resolve
```

It must print DaVinci Resolve Studio, its version and the open project. If it says Resolve is not answering, check the preference. If the product
name has no "Studio", this is the free edition: go back to step 3.

## 6. HyperFrames

`.claude/settings.json` in this folder keeps its usage reports off. If you run it from anywhere else, set `HYPERFRAMES_NO_TELEMETRY=1`.

```
npx --yes hyperframes@0.8.206 doctor
```

It downloads on first use and lists what it found. Only FFmpeg, FFprobe and Chrome matter here. This suite does not use Docker or HyperFrames' voice and music
lines, so a "Some checks failed" line about them is fine. If it says a newer version exists, keep 0.8.206: that is the tested one. If
Chrome is missing, the render in step 8 fetches it.

Then add HyperFrames' guides for Claude, which the animated videos follow. This one command writes into the user's Claude folder, so it needs
the OK from step 0:

```
npx --yes hyperframes@0.8.206 skills
```

## 7. The animation tools

```
cd animation/animate
npm install
npx playwright install chromium
```

Back in this folder, set up the motion copier:

```
node animation/reanimate/scripts/setup.mjs
```

The B-roll tool makes its own folder in each job, and its first step there uses this same browser.

## 8. Prove it

Run these and read the results:

```
python -I tools/doctor.py --resolve
python -I edit/test_snap.py
```

The doctor must end with "Ready." with nothing missing. If it lists anything, go back and install it.

Then render the two-second test film. It should show 120 frames at 60 fps, with no failure from the check:

```
npx --yes hyperframes@0.8.206 render builder/smoke --fps 60 --output builder/smoke/smoke.mp4
python -I animation/motion-qa/motion_qa.py builder/smoke/smoke.mp4
```

Delete `builder/smoke/smoke.mp4` after.

## 9. Tell the user

Say what is ready and what they can ask for now, in plain words. Mention anything the user told you to skip, and nothing else as left out. For example:

> You are set up. You can ask me to make a 60 second promo, cut a talking-head take, or grade a timeline in Resolve. Tell me what you want to
> make.

Also tell them the current recommendation: run everything on Claude Opus 5.5 at high effort. Other effort settings work, but results may vary,
and this changes with each model release, so it is worth testing.

From here, follow `.claude/skills/make-video/SKILL.md`.
