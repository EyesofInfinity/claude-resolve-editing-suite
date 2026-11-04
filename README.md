# Claude Resolve Editing Suite

Claude makes and edits your videos in DaVinci Resolve. Free and open source. For Windows, with DaVinci Resolve Studio.

Open this folder in [Claude Code](https://claude.com/claude-code) and say what you want:

> Make me a 60 second promo for my product.

> Cut this talking head take. Remove the pauses and the false starts.

> Grade my timeline "Interview" with a warm film look.

Claude cuts the take, builds the animation, grades every shot and checks the result. You get a finished file, or a real Resolve timeline
you can change by hand. You can do other work while it runs.

## What you need

To use this to its full potential, you need all three:

- **[Claude Code](https://claude.com/claude-code)** runs the whole system.
- **[DaVinci Resolve Studio](https://www.blackmagicdesign.com/products/davinciresolve)**, the paid edition, holds the edit. The
  free edition lacks scripting and DCTL, so the grade and the effects do not run in it.
- **[HyperFrames](https://github.com/heygen-com/hyperframes)** renders the animated videos. It is free and open source, and it
  downloads on first use.

Claude can set up the rest with you: Python, Node and FFmpeg. This works on Windows only.

It may work just as well in Codex. That has not been tested.

**Which model:** the current recommendation is to run everything on Claude Opus 5.5 at high effort. Other effort settings work, but your
results may vary. Test and experiment, because this changes with each model release. The suite is built to stay compatible with new
model releases for the medium term.

## What is in it

- **Cutting.** Silences, stutters, false starts and retakes found from the transcript. The cut lands on a new Resolve timeline.
- **Animation.** Promos, explainers, charts, titles and illustrated stories, made in code at 60 fps with motion blur.
- **Grading.** A photo-style grade and film looks, judged shot by shot, with a way back.
- **Effects.** 65 effects, transitions and grade nodes, 43 Fusion tools and 6 audio plugins, all inside Resolve. See [EFFECTS.md](EFFECTS.md).
- **Sound.** Sound effects, a mastered mix, and a library of free recorded sounds.
- **Checks.** Flash frames, bad joins, clipped pixels and loudness, measured on the real file.

## Install

1. Click the green **Code** button on this page, then **Download ZIP**. Unzip it. Or clone the repository.
2. Open the folder in Claude Code and say: **Set this up.**

Claude follows the steps in [`.claude/skills/setup/SKILL.md`](.claude/skills/setup/SKILL.md). It checks your computer, installs what is
missing and tests the result. You do only what a person must do: give one OK, install Resolve Studio if you do not have it, click Yes on
one Windows prompt, and set one preference in Resolve.

**By hand:** close Resolve and double-click `Install.bat`. Windows may show a blue warning because the script is not signed. Click **More
info**, then **Run anyway**. Windows asks once for admin rights, for the audio plugins only. Then in Resolve, open Preferences > System >
General and set **External scripting using** to **Local**.

To remove the effects and plugins, double-click `Uninstall.bat`. It removes only the files the installer put in place.

## It protects your work

- A cut goes on a new timeline. A grade goes on a new colour version. Your other grades stay.
- The tools never write over a source file or an existing render unless you say so.
- A grade run keeps a way back on disk, even if the run stops part way.
- Claude asks before it installs or downloads anything.

## Good to know

- Tested on DaVinci Resolve Studio 21.1.
- Effects and audio plugins appear in Resolve under the name **Develop**.
- The grade and looks expect Rec.709 footage. Log footage needs a Color Space Transform first.
- Claude and you make the choices. Look and listen before you publish.

## Licence

MIT, see [LICENSE](LICENSE). Folders with their own licence keep it. Credits are in [THIRD-PARTY.md](THIRD-PARTY.md).

This is an independent project. Anthropic and Blackmagic Design did not make it and do not endorse it. Claude is a trademark of
Anthropic. DaVinci Resolve is a trademark of Blackmagic Design.
