# motion-broll: motion-graphic B-roll timed to your words

A video and its transcript in, B-roll clips out, each timed to the line it covers: full-frame cutaways as MP4 and
transparent side panels as ProRes 4444 `.mov` for a track above the footage in Resolve. Every clip renders frame by
frame with 4 sub-frames on a 180 degree shutter, so fast moves carry real motion blur. It also writes a preview
composite, `viewer.html` (step through the clips), `compare.html` (original against the version with B-roll) and
`TIMING.md` (every clip's in and out point for the editor).

Needs Node 18+, Python 3, ffmpeg with the `prores_ks` encoder. `scripts/setup.sh <project>/motion` (run it in Git
Bash on Windows) installs Playwright and Chromium into that folder. `SKILL.md` is the workflow; `reference/engine-api.md`
is how to write a clip.

From motion-graphics by Bart (Barty-Bart, MIT, see LICENSE), upstream commit 3d83d98. Changes here:
- Windows: `engine/render.js` opens a proper file URL (it built `file://C:\...`); every script reads and writes UTF-8
  (the page writers crashed on "·" and curly quotes in the Windows code page); `setup.sh` tests that Python runs, so
  the Microsoft Store `python` placeholder is skipped.
- The upstream example (six clips for one real video) is not copied; the docs point to it upstream, and the sample
  plan uses neutral names.

Tested on Windows 11: setup, build, a full-frame clip (MP4) and a panel clip (ProRes 4444 with alpha),
the composite over a stand-in source, and the review pages.
