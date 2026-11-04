# Craft: how to make a good video

The tools in this suite do what they are told. These files hold the judgment: what to tell them. Claude reads them before it plans a
video, without being asked, because the user may have never edited one and is relying on Claude to make the calls an experienced editor would
make. `.claude/skills/make-video/SKILL.md` says which of the suite's skills to run at each moment.

## How to use this folder

1. Name the type of video from the table below and read its file.
2. Read [principles.md](principles.md). It applies to every video.
3. Write `projects/<job name>/brief.md` from the template below.
4. At each stage, read the matching topic file, then do the work.
5. Review the result with [review.md](review.md) before anyone calls it finished.

The user's words and taste win over every rule here. A rule may also be broken on purpose: write the reason in the brief. A rule broken
by accident is a mistake.

These rules describe good work, and some have no tool behind them yet. `.claude/skills/make-video/SKILL.md` says what to do then, and which route fits.

## Which type is this

| The job | Read |
|---|---|
| A person talking to camera: YouTube video, lesson, update, opinion | [types/talking-head.md](types/talking-head.md) |
| Showing how to do something, often on a screen | [types/tutorial.md](types/tutorial.md) |
| Explaining an idea with narration and visuals, no face needed | [types/explainer.md](types/explainer.md) |
| Showing off a product or launch, 15 to 90 seconds | [types/promo.md](types/promo.md) |
| A paid ad that must make a stranger act | [types/ad.md](types/ad.md) |
| TikTok, Reels or Shorts | [types/short-form.md](types/short-form.md) |
| A customer story, testimonial or interview film | [types/interview.md](types/interview.md) |
| A true story told over minutes, with real people and places | [types/documentary.md](types/documentary.md) |
| A personal film: vlog, travel, day in a life | [types/vlog.md](types/vlog.md) |
| A wedding, conference, concert or other real event | [types/event.md](types/event.md) |
| A long conversation, or clips cut from one | [types/podcast.md](types/podcast.md) |
| A video that sells a high-priced offer | [types/sales-video.md](types/sales-video.md) |
| Picture cut to a song | [types/music-video.md](types/music-video.md) |

If a job fits two types, the one that names its goal wins. A testimonial used as a paid ad reads [ad](types/ad.md) first and takes its
interview craft from [interview](types/interview.md).

## The topic files

| Stage | Read |
|---|---|
| Script, opening, order, ending, length | [structure.md](structure.md) |
| Shooting advice, choosing shots, framing, camera moves, light | [picture.md](picture.md) |
| Cuts, pacing, B-roll, transitions | [cutting.md](cutting.md) |
| Grade | [color.md](color.md) |
| Voice, music, sound effects, loudness | [sound.md](sound.md) |
| Captions, titles, on-screen words | [text.md](text.md) |
| Animation and motion graphics | [motion.md](motion.md) |
| Checking the work | [review.md](review.md) |

## When the user is new to this

- Ask at most three questions at a time, in plain words. Each type file ends with questions: choose the ones that change this job. Ask what the video is for, who will
  watch it and where they will see it, unless the request already says.
- "New" here means new to video. It does not mean new to this suite, which is what sends a user to setup.
- The request sets the scope. Someone who asks for captions wants captions. Offer anything else in one line at the end.
- Never ask a question that needs editing knowledge to answer. "What pace do you want?" is a bad question. Pick a pace, say what it
  will feel like in one sentence, and offer to change it.
- Make the decisions in the type file yourself and list them in the brief. The user can overrule any line.
- Show a plan in plain words before any long render. Offer two options at most, with your pick first and one reason.
- When the footage has a problem, say what it is and what you did about it. Tell the user how to avoid it next time in one sentence, once.
- Say what you cannot judge. Claude reads frames and numbers, and it cannot hear or watch in real time. Give the user the exact moments
  to check with their own eyes and ears.

## The brief

Write this before any cut or render. An empty line is a question to ask or a default to choose and label.

```
Type:             the row from the table above
One sentence:     what the viewer should remember
Viewer:           who, and what they already know
Published on:     platform, shape (16:9, 9:16, 1:1), sound on or off
Length:           a starting estimate
What it must do:  the one action or feeling wanted at the end
Fixed words:      exact words, numbers and claims that may not change
Real assets:      footage, logo, screens, music, voice takes, with rights confirmed
References:       videos the user admires, and what to take from each
Decisions:        pace, look, music, captions, each with a one-line reason
Skills:           each suite skill run, or skipped with a one-line reason
Rules broken:     any rule in this folder broken on purpose, and why
```

## How sure each number is

Every number here is tagged, so nothing is mistaken for a law.

- **[standard]** a published standard or a platform's own documentation.
- **[measured]** a study or a measured dataset. The numbers describe averages.
- **[practice]** what named working editors and creators report. One person's method may not transfer.
- **[default]** a starting value chosen for this suite. Change it when the material asks.

Platform facts move. Check one against the platform's current page before quoting it to a user as fact.

## Where this comes from

Rewritten from public sources and working practice. Credit where a method has a clear author:

- Walter Murch, *In the Blink of an Eye*, for the order of priorities in a cut.
- Tony Zhou and Taylor Ramos, *Every Frame a Painting*, on rhythm, feeling and when an image should land.
- Thomas Flight, *Video Essay Voiceover Guide* and his pacing essays, on breaths, compression and music under a voice.
- Transom, *Remember to Breathe*, on breaths in narration.
- Torcoli and others, AES 2019, *Background Ducking to Produce Esthetically Pleasing Audio for TV with Clear Speech*.
- Netflix Timed Text Style Guide, BBC subtitle guidelines, EBU R 95 and WCAG 2.2 for text, safe areas and flashes.
- YouTube Help on retention and upload settings; YouTube staff and working strategists on packaging and openings, among them Paddy
  Galloway, Kai Plunk and Colin and Samir.
- O'Keefe and Hoeken 2021 on what persuasion research can and cannot promise.
- Eugene Schwartz, *Breakthrough Advertising*, for the awareness stages.
- Thomas and Johnston, *The Illusion of Life*, for the principles of animation. LottieFiles' motion design skill for their use in code.
- The motion-design writing shared in 2026 by working Claude Code users, for the brief, gate and contact-sheet habits in
  [motion.md](motion.md) and [review.md](review.md). The sound pass in `animation/sound-pass` carries its own credits.
