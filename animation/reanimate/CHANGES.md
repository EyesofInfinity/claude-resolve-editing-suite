# Changes from upstream

reanimate by Niaz Morshed (MIT, see LICENSE; https://github.com/NiazMorshed2007/reanimate), copied from upstream commit 522a353 with the changes below: it runs on Windows as well as macOS and Linux, and its compare tool judges loops and easing peaks. The upstream `site/` folder (the examples page) is not included.

## What changed

- `scripts/lib.ts`: ffmpeg is ffmpeg-static's `ffmpeg.exe` on Windows, else `$FFMPEG`, else an ffmpeg on PATH. A new `toUrl()` turns a local path into a proper `file:///` URL. Upstream read a drive letter (`C:\...`) as a URL scheme and built `file://C:\...`, which fails.
- `scripts/capture.ts`: uses `toUrl()`; with `--gpu hardware` on Windows, Chromium runs ANGLE on Direct3D 11; `assets.json` paths use forward slashes on every OS.
- `scripts/setup.mjs` (new): the cross-platform twin of `setup.sh`. Runs on Node 24+ or Bun, uses bun when it is on PATH and npm otherwise.
- `SKILL.md` and `references/`: commands read `node <skill>/scripts/...`; `bun` still works.

No Bun is needed on Windows: Node 24+ runs the `.ts` scripts directly by stripping their types.

## Tested on Windows 11, Node 24.21.0

| Check | Result |
|---|---|
| `setup.mjs` | npm install, Chromium headless shell 156, ffmpeg-static 6.1.1: ready |
| `capture.ts` on a `C:\...\anim.html` path, virtual clock, `--gl`, tracked elements | 51 frames, 119 track samples, canvas 2d traced |
| The same capture twice, `compare.ts` | 0.00% mismatch, timing error 0 s (seeded `Math.random` included) |
| `easing.ts` on a CSS `cubic-bezier(0.16,1,0.3,1)` 900 ms, 200 ms delay | fitted easeOutExpo ~907 ms, delay 183 ms |
| `easing.ts` on a JS spring, 300 ms delay | spring-like, 33% overshoot, delay 300 ms |
| `sheet.ts compare`, `frames.ts --probe` and extraction, `gl.ts summary` | all ran |
| Real-clock capture (`video.webm`) with `--gpu hardware` | 43 frames; renderer ANGLE Direct3D11 |

## Live test: a loop from scenario.com/explorations/motion-loops

The first hero loop: a spiral of nested squares, a 2d canvas at 789,165, 292x164 in a 1440x900 viewport.

1. `capture.ts --trigger none --clock virtual --duration 12000 --fps 25 --gl`: 306 frames, plus the canvas draw log (`gl/canvas2d-c81.txt`).
2. The draw log gave the whole model: 25 squares, each 0.78 the size of the one outside it and turned 0.22 rad further; the stack zooms by one square every 2 s and the two colours swap each period.
3. A rebuild from those numbers alone (the page's code was not read), about 30 lines of canvas.
4. `compare.ts`: first pass, 0.01% mean mismatch with the copy 5 frames early; after moving its start 200 ms, offset 0 and 306 of 306 frames at 0.01% mean. The worst frame rounds to 0.0%. The only differing pixels are edge smoothing.

Upstream limit found, then fixed: `compare.ts` reported a continuous loop's copy as "not moving" and failed the timing check. Its motion window ignores frame-to-frame changes under 0.2% of the frame, and a slow loop stays under that every frame.

## compare.ts fixes (beyond the port)

1. **Loop mode.** On by itself when the reference moves in at least 90% of its frames (counted above a floor of a quarter of its median change, so grain or sparkle noise does not count); `--loop` and `--no-loop` force it. It passes when the clone moves in as much of the window, at a similar rate of change, without a longer stall.
2. **The peak counts.** Upstream measured the peak (the fastest moment) but never failed on it, so a linear copy of an ease-out passed. It now counts when the reference has a clear peak.

| Case | Before | After |
|---|---|---|
| Spiral copy (right) | timing FAIL ("not moving") | PASS: moving 99% / 100%, rate 0.75, no stall |
| Spiral at double speed | FAIL | FAIL: rate 6.2 |
| Spiral with a 1 s pause | FAIL | FAIL: 1 s stall against 0.04 s |
| Entrance, two identical captures | PASS | PASS (stays in start/end mode) |
| Entrance, title made linear | **PASS** | FAIL: peak 0.4 s late |
| Spiral with `--no-loop` | FAIL | FAIL (the old check, on request) |

Not tested: `--assets`, WebGL/WebGPU shader capture, worker tracing, `setup.mjs` under Bun on Windows.

Upstream behaviour worth knowing: `compare.ts` judges the whole frame against a 5% threshold, so a small element with the wrong easing can still PASS (our deliberate linear copy of the title scored 0.76%). Crop tight with `--selector` and check each element with `easing.ts`.
