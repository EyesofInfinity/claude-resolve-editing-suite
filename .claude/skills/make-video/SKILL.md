---
name: make-video
description: Make, edit or improve any video with the Claude Resolve Editing Suite. Use for every request about video in this folder, however small or plainly worded, including a cut, a grade, captions, titles, a thumbnail frame, sound, music, pacing, a promo, an ad, a Short, an explainer, motion graphics, effects, advice on making a video better, or anything to do with DaVinci Resolve. It decides which of the suite's skills and craft rules the job needs.
---

# Make a video

You run the whole job, as the editor. The user should be free to do other work while it runs, and they should never need to know this
suite's skills exist. Ask only what you need, in one batch.

## Run these without being asked

The user will ask for a video in plain words. They will not name a skill, because they do not know the names. Choosing and running the right
ones is your job. Do it at the matching moment, every time, with no prompting and no "should I use X?".

**The request sets the scope.** "Add captions" means captions: leave the cut, the grade and the sound alone. Run everything the job needs, and offer anything
else in one line at the end. The table says what to run when a job includes that stage.

| When | Run |
|---|---|
| Any video job, even a small one | `craft/README.md`, the file for this type, and `projects/<job name>/brief.md` |
| Any script, opening or ending | `craft/structure.md` |
| A brand with no `brand.md` yet | `builder/skills/brand-intake/SKILL.md` |
| Any animated film | `builder/skills/motion-brief-writer/SKILL.md`, then its format skill, and `craft/motion.md` |
| An illustrated story | `animation/animate/SKILL.md` |
| The user admires another video's motion | `animation/reanimate/SKILL.md` |
| A spoken take to tighten | The tools in `edit/README.md`, and `craft/cutting.md`. Never trim pauses out of vows, toasts or emotional lines |
| Footage to plan from | A contact sheet, read by you, and `craft/picture.md` |
| The job wants graphics over a speaker, and the line describes something to see | `animation/motion-broll/SKILL.md`. Personal and emotional lines keep the face |
| The job includes a grade | `craft/color.md`, then `looks/README.md` and `develop_apply.py`. Skip it on a flat-colour brand film |
| Any sound work | `craft/sound.md`. For a film with no recorded sound of its own, `animation/sound-pass/SKILL.md` |
| Any words on screen, and captions on all 9:16 work | `craft/text.md` |
| Any designed frame, title card, chart, interface or web page, before you show it | `.claude/skills/unslop/SKILL.md`, and `craft/motion.md` |
| Before you write a script, or say something cannot be done | `craft/resolve-tools.md` |
| Every render, before you call it finished | `craft/review.md` and `animation/motion-qa/motion_qa.py` |

**`sound_pass.py` replaces a film's audio.** Its mix holds only the music and effects, so a voice, vows or room sound would be lost. Never run it on a film
with sound you want to keep. There, use its licence and beat-grid steps, and mix in Resolve.

**Run a skill in full.** Open its file, follow its steps, and record it in the Skills line of the brief. Only write that you used a skill if its
steps ran. Reusing an earlier result is fine: say that you reused it.

**This file and `craft/` win when a skill disagrees.** The skills came from different authors.

- **Questions:** at most three at a time, in one batch. Merge a skill's questions into yours. Choose labelled defaults for anything a new user cannot answer, such as hex
  codes or reference frames. That still counts as running the skill.
- **Gaps:** where `brand-intake` says to write ASK ME and the user has no references, write a labelled default.
- **Who builds:** you are Claude Code. Where a skill says to paste a prompt into Claude Code, do the build yourself.
- **Length and shape:** the user's request and the type file set these. A skill's table is a starting point to re-time.
- **Sound:** recorded sounds are the default, and code-made sounds are allowed where `craft/sound.md` says so.
- **`unslop` in a film:** run its audit, direction and passes on the film's frames. Its layout and motion passes are written for apps and pages, so in a film `craft/motion.md` decides how things move. Put its audit and direction in your plan, with no separate stop unless the user wants one. Ask before an image tool that may cost money. Its story video and `snapshot.mjs` need Playwright, so make the video only when the user asks.

**Skip one only with a reason you can write down**, in the brief, in one line. The user can always tell you to skip something.

Asking still comes first for a download, an install, or anything that changes the user's project: that protects their work, and `CLAUDE.md` has those
rules. Plain craft and tool choices need no permission.

## 1. Find the job

Ask, unless the request already says:

- **What is it?** An animated video, or real footage? How long? Where will it be published?
- **What do you have?** A script, a voice take, footage, a logo, brand colours, reference videos?
- **What must it say?** The exact words and numbers that must stay fixed.

Then make the job's folder, `projects/<job name>/`. Run `python -I tools/doctor.py` first. If it reports anything missing, follow
`.claude/skills/setup/SKILL.md`.

Read `craft/README.md` and the file for this type. Write `projects/<job name>/brief.md` before any cut or render, with your decisions in it. A draft with open
lines is fine. Then pick one route below. A job that is one small thing, such as captions on a finished clip, takes only the steps it needs.

**When a step seems to have no tool.** Follow "The show must go on" in `CLAUDE.md`: search this folder, `craft/resolve-tools.md` and Resolve's docs, then search the web, then build one. Never stop at "can't". Tell the user when a step is
custom, because it may need more of their corrections.

## 2. Route A: an animated video

Use this for promos, explainers, launch films, charts, titles and logo stings. Build in `projects/<job name>/film/`, so a composition's `BRIEF.md` stays apart from
your `brief.md`. If music sets the clock, choose the track before you build.

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

## 3. Route B: one spoken take

Use this for talking heads, tutorials, single interviews and narration. If the user has not filmed yet, give them the shooting advice in `craft/picture.md`.

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

1. Read `craft/color.md`, then `looks/README.md`. Pick a look, or write one for this footage. Balance the shots before the look.
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

## 5. Route D: many clips, led by picture or music

Use this for weddings, events, documentaries, vlogs, music videos and anything assembled from many clips. Resolve's own tools are in `craft/resolve-tools.md`. Choosing the shots and the pace is your job.

1. **Inventory.** List the folder. Run `ffprobe` on each clip for length, frame rate, size, audio and colour transfer. Note variable-rate phone clips and log footage. Write it to the job folder.
2. **Read it.** Make a contact sheet per clip, at a rate set from its length (`craft/review.md`), and write one line on each.
3. **Find the words.** Run `edit/transcribe.py` on clips with speech, one clip at a time. It stops on a clip with no audio track. Use `--model medium` for speech that is not English.
4. **Find the music.** `effects/beat/beat.py` writes the song's beats and downbeats to a `.music.json`. You place the cuts: nothing here does it for you.
5. **Plan.** Write a shot plan in the job folder: clip, in, out, why. Show the user before any long job.
6. **Build.** `edit/to_resolve.py` lays out one source only. For many clips, use Resolve's `CreateTimelineFromClips` or `AppendToTimeline` on a new timeline. Test it on a few clips first.
7. **Sync.** Use Resolve's `AutoSyncAudio` for a separate recorder and `CreateMulticamClip` for several cameras.
8. **Finish.** Route C for the grade. Mix in Resolve, keeping the real sound. Then review.

## 6. Captions

Resolve Studio makes captions itself. Use it first. Rules for groups, size and timing are in `craft/text.md`.

1. Read the open project and timeline, as `CLAUDE.md` rule 1 says. Put the clip on a new timeline, and set its size to 1080 by 1920 for 9:16.
2. Create the captions with `timeline.CreateSubtitlesFromAudio`. Pass `resolve.SUBTITLE_LANGUAGE`, `SUBTITLE_CAPTION_PRESET`, `SUBTITLE_CHARS_PER_LINE`, `SUBTITLE_LINE_BREAK` and `SUBTITLE_GAP`. For 9:16, use 16 characters a line on one line: at the default size, 20 characters reach the edges of the frame. It returns at once, so poll `project.GetCreateSubtitlesFromAudioStatus()` until `JobStatus` reads `Complete`. On 40 seconds of speech it took under a minute.
3. Read the text back with `timeline.GetItemListInTrack("subtitle", 1)`; each item's name is its text. Check names and terms. Have the user spell names, and correct them in Resolve's subtitle inspector, which has search and replace.
4. **The user does two things by hand, because scripts cannot.** Tell them exactly what and why:
   - **Position:** on 9:16 Resolve's default sits at about y 1540, under the platform's buttons. Raise it above y 1400 in the subtitle track's style in the Inspector.
   - **An animated style, if wanted:** Resolve has styles such as Word Highlight in the titles list. Drag one onto the subtitle track. Scripts can only insert them on a video track, as an empty title that pushes the clip along, so never do that.
5. Render with `SetRenderSettings({"ExportSubtitle": True, "SubtitleFormat": "BurnIn", ...})`. Use `"SeparateFile"` for a caption file on long YouTube videos. Delete only your own render job afterwards.
6. Look at frames at phone size.

**Without Resolve Studio,** which is the edition that generates captions: run `edit/transcribe.py` for word timings. `medium.en` is English only. Write a job script that groups the words into an ASS file, check that FFmpeg has the `subtitles` filter (`ffmpeg -filters`), burn a still first, then the whole clip, to a new file. Phone clips in HDR can wash out when re-encoded: read the colour transfer first.

## 7. Review

Follow `craft/review.md`. Look at contact sheets and the frames around cuts, run the checks, and fix the three worst defects. A rendered file
is a draft until this is done.

## 8. Deliver

Tell the user, in plain words:

- what they can open now, with the file or timeline name;
- what you decided on their behalf, and which parts of the suite you ran;
- what the checks measured;
- what you did not check, and anything they should look at or listen to themselves.
