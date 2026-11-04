# animate: short animated pieces drawn in code, in a chosen look

Explainers, histories and little stories drawn on one canvas, frame by frame, with their own synthesized score. A look
is a plug-in in `styles/` (its rules in `STYLE.md`, its drawing kit in `kit.js`, a sample and a demo); seven ship:
cut paper, crosshatch ink, sketchbook, math, pixel, isometric line art and riso print. A new look can be measured from
your own references (`new-style.md`, `tools/measure/`, `tools/compare.mjs`). `SKILL.md` is the workflow: intake, a
story check, a look check and a storyboard you approve before anything is animated.

Setup, once, in this folder:

```
npm install
npx playwright install chromium
```

Then, for example:

```
node tools/build.mjs styles/riso/demo
node tools/export.mjs styles/riso/demo --gpu
node tools/review.mjs styles/riso/demo
```

`export.mjs` writes frames, the score with music and SFX stems, loudness to about -14 LUFS, every format laid out
per shape (`--formats 9:16,1:1,16:9`) and optional sub-frame blur (`--blur 4`). `review.mjs` checks cut-off or
overlapping text, safe zones, dead beats, the payoff's loudness, and writes a phone-size sheet. Needs Node 18+ and
ffmpeg on PATH; the voice-over tool also needs Python with faster-whisper.

From animate by cth9191 (MIT, see LICENSE), upstream commit 7e5eb56, copied unchanged except: the worked
example `examples/history-of-ai` (it names real companies and products) is not copied and the two docs that point to
it now point upstream, and `package.json` was added so Playwright installs here instead of globally. Tested on Windows
11: all seven demos built and exported on the GPU in about 14 s each; the riso and pixel reviews passed.
