# Claude Resolve Editing Suite

This folder is a video editing system. You, Claude, run it for the user. It works on Windows with DaVinci Resolve Studio.
Read `.claude/skills/make-video/SKILL.md` before any video job. The user may have no technical background: use plain
words, and show results, not logs.

## First, every session

```
python -I tools/doctor.py
```

It lists what is missing and changes nothing. **If anything is missing, or the user is new, or Python is not installed yet, follow
`.claude/skills/setup/SKILL.md` step by step.** It sets up the whole system for them. The commands here use `python -I`, which keeps
other files from loading as code. `-I` does not see packages installed with `pip --user`: if one reads as missing after you installed
it, run the tool without `-I`.

## What the user can ask for

| The user wants | Use | Start at |
|---|---|---|
| An animated video from an idea, a script or a brand (promo, explainer, chart, title, launch film) | the builder chain, rendered with HyperFrames | `builder/README.md` |
| A short illustrated story (cut paper, crosshatch, sketchbook, math, pixel, isometric, riso) | animate | `animation/animate/SKILL.md` |
| A talking-head or voice take cut clean (silences, false starts, retakes) | the cut tools, then a real Resolve timeline | `edit/README.md` |
| Motion graphics timed to a speaker's words | motion-broll | `animation/motion-broll/SKILL.md` |
| A timeline graded shot by shot, with a look and effects | `develop_apply.py` | `looks/README.md` |
| Sound effects and a mix on a finished picture | sfx, sound-pass | `animation/sfx/README.md`, `animation/sound-pass/SKILL.md` |
| An effect, transition or audio plugin explained | the effect list | `EFFECTS.md` |
| A check of a finished render | motion-qa | `python -I animation/motion-qa/motion_qa.py <video>` |

## Rules

These protect the user's work. Never skip them.

0. **Every job gets a folder.** Work in `projects/<job name>/`, which git ignores. `brand.md`, `MOTION.md`, scripts, renders and notes
   for that job go there. Never edit this `CLAUDE.md` or the suite's own files for one job.

1. **Read Resolve before you change it.** Run `python -I tools/doctor.py --resolve` and tell the user which project and
   timeline are open. Change only what the user named. If you are unsure, ask.
2. **Never guess a timeline.** `develop_apply.py` needs `--timeline`. Ask the user which one.
3. **New, never replace.** A new timeline for each cut. A new colour version for each grade. Pass `--overwrite` only when
   the user says to replace that exact thing. Never write over a source file.
4. **Offer the way back.** After a grade, tell the user the run folder and that `--revert` restores the clips.
5. **Check, then look.** Run `motion_qa.py` on every render, and `join_check.py` on every cut. Look at the frames
   yourself before you call a result good. Report the numbers. A check that fails stops the delivery.
6. **Fixed words stay fixed.** The user's exact words, numbers and claims go on screen unchanged. A sample number is labelled
   "Illustrative data". A target is never shown as a result.
7. **Rights.** Use footage, music, logos and fonts the user has the rights to. Before a copied motion or a stock clip goes in
   a public video, ask the user to confirm the licence.
8. **Ask before you install or download.** The first run of some tools downloads a model or a browser. Tell the user the
   size first. Never run `npx skills add`; it writes into the user's global Claude folders.

## HyperFrames

The animated videos render with HyperFrames, which is not part of this folder. It downloads from npm on first use, about 160 MB,
plus its own Chrome. Use the tested version, `npx hyperframes@0.8.206`. `.claude/settings.json` in this folder keeps its usage reports
off (`HYPERFRAMES_NO_TELEMETRY=1`).

Render at 60 fps with motion blur. The page must be a composition: `builder/README.md`, step 4, has the rules and the adapter, and
`builder/smoke/index.html` is the smallest working film. HyperFrames also has its own guides for Claude. Ask the user first, then run
`npx hyperframes@0.8.206 skills`, because that command adds folders to the user's Claude setup.

## Resolve facts

- External scripting must be on: Preferences > System > General > External scripting using: Local.
- Effects run as DCTL plugin nodes, so moving effects keep moving. A LUT node freezes them.
- Transitions cannot be placed by script. Tell the user which file to drag onto which cut.
- These scripts change the open project: `develop_apply.py`, `edit/to_resolve.py`, `effects/depth/depth_pass.py`. The first
  two add a colour version or a new timeline. The third rebuilds its own scratch timeline, "Develop depth pass".
- The effects and looks expect Rec.709 footage. For log footage, add a Color Space Transform before the grade.
