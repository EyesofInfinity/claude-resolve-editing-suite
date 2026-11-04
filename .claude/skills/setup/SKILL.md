---
name: setup
description: Set up the Claude Resolve Editing Suite on this computer for a new user, start to finish, automatically. Use when the user says set up, install, get started or first time, or when tools/doctor.py reports anything missing.
---

# Set up the suite

You do this for the user. They do only what a person must do: give one OK, install Resolve Studio if it is missing, click Yes on
one Windows prompt, and set one preference in Resolve.

Work in order. For each step: check first, skip it if it is done, then verify. Tell the user in one short line what you are doing.
Run every command from this folder.

## 0. Get one OK

Tell the user, in plain words, and wait for a yes:

> I will set up the suite on this computer. I will install what is missing: Python, Node and FFmpeg with Windows' own installer
> (winget), the Python packages, HyperFrames with its browser (about 160 MB plus Chrome), and the animation tools (about 700 MB). Then I
> will put the effects and audio plugins into DaVinci Resolve. Windows will ask you once for admin rights, for the plugins. The first
> talking-head cut also downloads a speech model of about 1.5 GB. I will also add HyperFrames' guides to your Claude folder. Nothing else
> on your computer changes. Shall I go ahead?

If the user says no to a part, skip that part and say what will not work.

## 1. Python, Node, FFmpeg

Check each one:

```
python --version
node --version
ffmpeg -version
```

Python must be 3.10 or newer (a line that says the Microsoft Store, or no version, means it is missing). Node must be 22.15 or
newer. Install what is missing, one at a time:

```
winget install -e --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements
winget install -e --id OpenJS.NodeJS.LTS --source winget --accept-package-agreements --accept-source-agreements
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
python -m pip install -r requirements.txt
```

Install `requirements-shot-tools.txt` too only when the user asks for Beat, Grain Match, Depth, Light Comp, Particles camera match, Time FX
or Datamosh. It is large.

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

Tell the user: "Windows will now ask for admin rights, once, for the audio plugins. Please click Yes." Then run the installer:

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

It downloads on first use and lists what it found. Only FFmpeg, FFprobe and Chrome matter here. Docker and the voice and music lines are
optional, so a "Some checks failed" line about them is fine. If it says a newer version exists, keep 0.8.206: that is the tested one. If
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

The B-roll tool and the motion copier set themselves up on first use: their `SKILL.md` files say how.

## 8. Prove it

Run these and read the results:

```
python -I tools/doctor.py --resolve
python -I edit/test_snap.py
```

Then render the two-second test film. It should show 120 frames at 60 fps, with no failure from the check:

```
npx --yes hyperframes@0.8.206 render builder/smoke --fps 60 --output builder/smoke/smoke.mp4
python -I animation/motion-qa/motion_qa.py builder/smoke/smoke.mp4
```

Delete `builder/smoke/smoke.mp4` after.

## 9. Tell the user

Say what is ready, what was skipped, and what they can ask for now, in plain words. For example:

> You are set up. You can ask me to make a 60 second promo, cut a talking-head take, or grade a timeline in Resolve. Tell me what you want to
> make.

Also tell them the current recommendation: run everything on Claude Opus 5.5 at high effort. Other effort settings work, but results may vary,
and this changes with each model release, so it is worth testing.

From here, follow `.claude/skills/make-video/SKILL.md`.
