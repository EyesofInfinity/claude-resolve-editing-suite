---
name: make-video
description: Make or finish a video with the Claude Resolve Editing Suite. Use when the user asks for a video, an edit, a cut, a grade, a promo, an explainer, motion graphics, effects, or anything to do with DaVinci Resolve in this folder.
---

# Make a video

You run the whole job. The user should be free to do other work while it runs. Ask only what you need, in one batch.

## 1. Find the job

Ask, unless the request already says:

- **What is it?** An animated video, or real footage? How long? Where will it be published?
- **What do you have?** A script, a voice take, footage, a logo, brand colours, reference videos?
- **What must it say?** The exact words and numbers that must stay fixed.

Then make the job's folder, `projects/<job name>/`, and pick one route below. Run `python -I tools/doctor.py` first. If it reports
anything missing, follow `.claude/skills/setup/SKILL.md`.

## 2. Route A: an animated video

Use this for promos, explainers, launch films, charts, titles and logo stings.

1. **Brand.** `builder/skills/brand-intake/SKILL.md` writes `brand.md` and `MOTION.md`. Do this once per brand. Read both first
   on every later step. If the user has no reference frames, fill the gaps with sensible defaults, label them as defaults, and
   show the user.
2. **Brief.** `builder/skills/motion-brief-writer/SKILL.md` turns the idea into one build prompt.
3. **Format.** Pick the format skill in `builder/skills/`: `launch-video`, `vox-explainer`, `animated-chart`, `milestone-reveal`,
   `motion-effects`, `title-sequence-3d`, `loop-cover`, `reel-export`.
4. **Render.** HyperFrames at 60 fps with motion blur. `builder/README.md`, step 4, has the composition rules, the adapter a
   `window.seek` page needs, and the traps. A render with no adapter comes out frozen.
5. **Sound.** `animation/sound-pass/SKILL.md` for recorded sounds and music, the default for professional work.
   `animation/sfx/README.md` makes sounds in code: keep those for playful pieces. Sound effects are accents, at the music's level.
   The sound pass needs music with a clear beat. If the user has no licensed music, say so and ask. A code-made bed works as a placeholder.
6. **Check.** `python -I animation/motion-qa/motion_qa.py <render>`. Then look at the frames around every cut.
7. **Finish.** Skip the grade on a flat-colour brand film, because a grade moves exact brand colours. A light finish is
   safe: `looks/Clean Finish.json`.

For an illustrated story, use `animation/animate/SKILL.md` for steps 3 and 4.

## 3. Route B: real footage with a voice

Use this for talking heads, tutorials and narration.

1. **Cut.** Follow `edit/README.md`, in the `edit/` folder:
   `transcribe.py`, `cut-silences.mjs`, `find-cut-candidates.mjs`. Read the candidates. Deliberate repetition stays. Show the
   user anything marked `review`. Then `compose_edl.py` and `snap_edl.py`.
2. **Check the joins.** `join_check.py` lists the joins to listen to. Fix or flag them.
3. **Put it in Resolve.** `python -I edit/to_resolve.py <take> <final-edl.json> --timeline "<new name>"` makes a real timeline
   on the original media, so the user can change any cut.
4. **Motion graphics.** `animation/motion-broll/SKILL.md` makes clips timed to the words.
5. **Grade.** Route C.
6. **Render from Resolve**, then run `motion_qa.py` on the file.

## 4. Route C: grade and effects in Resolve

1. Read `looks/README.md`. Pick a look, or write one for this footage.
2. Run `python -I tools/doctor.py --resolve` and tell the user the open project and timeline.
3. Grade the timeline the user named:

   ```
   python -I develop_apply.py "looks/Warm Film.json" --timeline "<name>" --version "Grade 1"
   ```

4. Read the printed gate flags and open the stills in the run folder. Change the look if a shot fails, and run again with a
   new `--version` name.
5. Tell the user how to go back: `python -I develop_apply.py --revert "<run folder>"`.

Add effects inside the look file, on the clips that need them with `--clips`. `EFFECTS.md` says which effect suits which job.
Place light effects with a low Amount: they must belong to the scene, not sit on top of it.

## 5. Deliver

Tell the user, in plain words:

- what they can open now, with the file or timeline name;
- what the checks measured;
- what you did not check, and anything they should look at or listen to themselves.
