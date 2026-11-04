# Third-party credits

The Claude Resolve Editing Suite is our own code under the MIT License (see `LICENSE`), except the folders listed here, which
keep their own licences. This file lists what it builds on.

## Shipped in the release

| Part | Used for | Licence |
|---|---|---|
| Steinberg VST3 SDK 3.8.1 (github.com/steinbergmedia/vst3sdk) | Building the six audio plugins in `plugins/prebuilt/` from the sources in `plugins/` (the SDK itself is not included) | MIT |
| ACES Reference Gamut Compression (Academy of Motion Picture Arts and Sciences) | Gamut compression in Develop 2 Color, written from the published specification | CC BY 4.0 |
| Oklab (Björn Ottosson) | The published Oklab matrices, in the colour effects | Public domain reference values |
| claude-motion-design (Raphaël Aubry, Howseen AI) | The pop, one-frame flash and loop seam rules in `animation/motion-qa/`, rewritten to stream frames, with a flash rule that also works mid-move | MIT (its notice is `animation/motion-qa/LICENSE`) |
| huashu-art-motion (alchaincyf), its `film_gate.py` | The blank-stretch and blue-purple rules and thresholds in `animation/motion-qa/`; the palette rule kept as a warning only, with a higher brightness floor | MIT (its notice is in `animation/motion-qa/LICENSE`) |
| claude-motion (whaleyxbt), the `sfx` engine in `animation/sfx/` | Sound effects and a pad made in code, placed on the picture's timeline, mastered to -14 LUFS | MIT (its notice is `animation/sfx/LICENSE`) |
| motion-graphics (Bart, Barty-Bart), in `animation/sound-pass/` and `animation/motion-broll/` | The measured sound pass, and B-roll clips timed to a transcript; our changes are listed in each folder's `README.md` | MIT (its notice is the `LICENSE` in each folder) |
| 109 sound effects in `animation/sound-pass/sfx/` (Kenney audio packs and Freesound, each author and source in `animation/sound-pass/LICENSES.md`) | The sound pass's library | CC0 1.0 |
| Geist and Geist Mono (Vercel), in `animation/motion-broll/engine/fonts/` | The B-roll clips' type | SIL Open Font License 1.1 (`OFL-Geist.txt` beside them) |
| Lucide icons, in `animation/motion-broll/engine/motion.js` | Icon paths in the B-roll clips | ISC (`animation/motion-broll/LICENSE-Lucide.txt`) |
| Herk Edit Kit (Nate Herk), four scripts in `edit/` | Silence and mistake cuts from a transcript, and the EDL review page; our changes are listed in `edit/README.md` | MIT for the original kit (`edit/LICENSE`); the editing pipeline under the kit's use permission, whose notices stay with it (`edit/PIPELINE-USE-PERMISSION.txt`, `edit/THIRD_PARTY_NOTICES.md`) |
| animate (cth9191), in `animation/animate/` | Short animated pieces drawn in code in seven looks, their scores and review tools; our changes are listed in its `README.md` | MIT (its notice is `animation/animate/LICENSE`) |
| Motion Graphics Skill Pack (Charlie Hills), in `builder/skills/` | Brand intake, the brief writer and eight format workflows; what was left out is listed in `builder/README.md` | MIT (its notice is `builder/LICENSE`) |
| reanimate (Niaz Morshed), in `animation/reanimate/` | Copying a motion from a website, video or GIF and measuring the copy against it; our changes are listed in its `CHANGES.md` | MIT (its notice is `animation/reanimate/LICENSE`) |
| unslop (Damir Sokolovsky, @heydamir, heydamir.design/unslop), upstream heydamir/unslop commit 4652254, in `.claude/skills/unslop/` | The design pass: audit, direction and nine passes that turn AI-looking screens into designed ones. Copied unchanged; the suite's `make-video` skill says how it applies to a film | CC BY 4.0 (`.claude/skills/unslop/LICENSE`) |

VST is a registered trademark of Steinberg Media Technologies GmbH.

## Downloaded by setup, for the shot tools and reanimate

| Part | Used for | Licence |
|---|---|---|
| Depth Anything V2 Small (depth-anything/Depth-Anything-V2-Small-hf on Hugging Face) | Depth for the Particles camera match, about 99 MB, fetched once | Apache-2.0 |
| Python packages: numpy, scipy, Pillow, opencv-python, soundfile, librosa, numba, PyAV | The shot tools (Beat, Grain Match, Depth, Light Comp, Particles camera match, Time FX, Datamosh) | BSD, MIT, Apache-2.0 or ISC, each as its project states |
| PyTorch and Hugging Face transformers | Running the depth model | BSD-3-Clause and Apache-2.0 |
| FFmpeg | Reading and writing video in the shot tools | LGPL or GPL, as your FFmpeg build states |
| faster-whisper and the Whisper medium.en model | `edit/transcribe.py`, the word transcript for the cut tools; setup downloads the model (about 1.5 GB) | MIT |
| Python packages for the sound pass: librosa, soundfile, numpy, scipy, matplotlib | `animation/sound-pass/scripts/sound_pass.py` | ISC, BSD and PSF-based, each as its project states |
| Playwright and its Chromium for motion-broll | `animation/motion-broll/scripts/setup.sh` installs them into your project's `motion/` folder | Apache-2.0 |
| The Mixkit typing sound in the sound pass's default kit | Downloaded at run time into your output folder, never bundled | Mixkit Sound Effects Free License (no redistribution) |
| npm packages for reanimate: Playwright and its Chromium, pixelmatch, pngjs, ffmpeg-static | Recording pages, comparing frames, and an FFmpeg binary if none is on PATH; fetched by `animation/reanimate/scripts/setup.mjs`, about 250 MB | Apache-2.0, ISC, MIT, and GPL-3.0-or-later (ffmpeg-static) |

HyperFrames (HeyGen, Apache-2.0), which renders the animated videos, is fetched from npm by `npx`; it is not part of this
repository. The larger Depth Anything V2 models (Base, Large, Giant) are under a non-commercial licence. This suite never
uses them.

## Methods from published work

Written from the papers and specifications, with no code copied: the Planckian locus by Krystek's approximation (1985),
CAT16 chromatic adaptation (CIECAM16), Rayleigh sky polarisation, the SuperFlux onset detector (Böck and Widmer, 2013),
the Jiles-Atherton magnetic hysteresis model, and DIS optical flow as OpenCV implements it.
