# builder: from a request to a finished animated video

The front door of the general video builder: who the brand is, what the film says, which format makes it, and how
it is rendered, scored, checked and finished. Each step below names the folder that does it.

## The chain

1. **Brand, once per brand:** `skills/brand-intake`. Seven questions in two batches and 3 to 5 reference frames become
   `brand.md` (who, for whom, what is promoted, assets, never) and `MOTION.md` (every colour with its job, type,
   timing, how things move, texture, five nevers, one example shot by shot). Where the frames cannot answer, it writes
   ASK ME instead of guessing. Every later step reads both files first.
2. **The brief:** `skills/motion-brief-writer` turns a rough idea into one build prompt: size and length, four timed
   states, the exact words and numbers marked fixed, sample figures labelled "Illustrative data" (a target is never
   shown as a result), and a self-contained HTML file with `window.seek(seconds)`. From a video you admire:
   `../animation/reanimate` measures a motion exactly and proves the copy matches. Take its moves, and leave its logo,
   copy and colours.
3. **The format:** `skills/launch-video`, `vox-explainer`, `animated-chart`, `milestone-reveal`, `motion-effects`
   (16 effects), `title-sequence-3d`, `loop-cover`, `reel-export`. For an illustrated look (cut paper, crosshatch,
   sketchbook, math, pixel, isometric, riso, or one measured from references): `../animation/animate`. For B-roll over a
   talking take: `../animation/motion-broll`.
4. **Render at 60 fps with motion blur.** Films in this style read as 120 fps or more because they render at 60 fps
   with sub-frame motion blur; at 30 fps with none they look stepped. In HyperFrames (0.8.206): `data-fps="60"` and
   `data-motion-blur="on"` on the composition root (capture blur; the render command has no blur flag), then
   `render --fps 60`. Give every moving group a real box (a width and height): blur copies the element's box, and a
   zero-size group that only holds positioned children drew nothing while it moved. Very fast fine stripes smear to
   mud; slow them or widen them. `animate` takes `--blur 4`.

   **The page must be a composition.** HyperFrames does not call `window.seek`. A bare page stops with "zero duration",
   and with only the attributes added it renders a frozen picture. The root needs `data-composition-id`, `data-start`,
   `data-duration`, `data-width`, `data-height`, `data-fps` and `data-motion-blur`, and the page must register a paused
   GSAP timeline in `window.__timelines["<id>"]`. The skills here build a page around `window.seek(seconds)`; add this
   adapter, with your film's length as `D`:

   ```js
   const clock = { t: 0 };
   const tl = gsap.timeline({ paused: true });
   tl.to(clock, { t: D, duration: D, ease: "none", modifiers: { t: (v) => { window.seek(parseFloat(v)); return v; } } }, 0);
   window.__timelines = window.__timelines || {};
   window.__timelines["root"] = tl;
   ```

   `smoke/index.html` is the smallest whole example; its one network line loads GSAP, which is fine here even where a
   skill says no network. `npx hyperframes@0.8.206 docs compositions` prints the full contract and writes nothing. Then
   run `motion_qa.py`: it fails a frozen render. Three more traps: an `autoplay` in a render page fails `hyperframes
   check`, so remove it; HyperFrames may swap a system font (Georgia came out as EB Garamond from Google Fonts), so check
   the type in the frames; and the skills' lengths and looping last frames are defaults, so the user's request wins.
5. **Sound:** `../animation/sfx` makes every sound in code on the picture's timeline; `../animation/sound-pass` places
   recorded CC0 sounds on cues and fits the music's beats to the cuts. Both master to a measured loudness.
6. **Check:** `../animation/motion-qa` on the render (pops, one-frame flashes, blank stretches, loop seams, and a
   warning on a mostly blue-purple palette).
7. **Finish in Resolve** with the suite: the grade, the effects, the audio plugins, delivery at 60 fps. Skip the grade
   on a flat-colour brand film: it moves the brand's exact hex colours.

Real footage instead of animation: `../edit` cuts a talking take from its transcript (silences, retakes, snapped
joins, one render from the source).

## Notes for this suite

- HyperFrames setup is in the root `CLAUDE.md`. Check it with `npx hyperframes@0.8.206 --version`.
- HyperFrames' own entry skill runs an intent interview that asks again what brand-intake and the brief already
  answered. Write the brief as the project's `BRIEF.md` (front matter `workflow: general-video`, `flow: companion`), and
  HyperFrames reads it instead of interviewing.
- In a composition, change text with tweened properties (`innerText` with a `modifiers` formatter, or one element per
  value switched with `set`), never with `onUpdate` or `call` callbacks: a renderer that seeks to a frame need not run
  them.
- Every `<video>` needs an `id`, `data-start`, `data-duration` and `data-track-index`: clips made in script without an
  id render black. Swap text by crossfading two finished lines; a `maxWidth` tween on struck words leaves them unshown
  at every frame.
- Under capture blur, an element moving fast enough to smear is drawn over the elements in front of it: a photo
  zooming at a cut can cover its own panel and title for frames. Keep photo pushes under half a pixel a frame, keep
  panels still, and land every cut on a finished frame; check with a strip of the first six frames after each cut of
  the real render, since a snapshot alone can miss it.
- Sound for a professional promo: recorded sounds (`../animation/sound-pass/sfx`, CC0) placed by their measured peaks,
  as accents at the music's level. The code-made blips, pops and chimes of `../animation/sfx` read as childish there;
  keep them for playful pieces.

## Where it comes from

`skills/` is from Motion Graphics Skill Pack by Charlie Hills (charlie947/motion-graphics-skills, MIT, see LICENSE),
upstream commit 229022e, copied unchanged except the install lines, which point at the root `CLAUDE.md`. Left out:
apple-launch-film (it rebuilds one company's own interface), model-showdown (it needs accounts with other AI
providers), motion-prompt-writer and reference-to-motion (they write for another tool), newsletter-promo and the pack's
prompts folder. This README is ours (MIT).
