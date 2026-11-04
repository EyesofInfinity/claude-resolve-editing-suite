# sound-pass: real sound effects placed on cues, measured

110 recorded sound effects in `sfx/`, all CC0 (Kenney packs and Freesound; every file's author and source page are in
`LICENSES.md`), and `scripts/sound_pass.py`, which places one on each cue of a silent video and mixes in a music track:

- checks librosa's beat grid against the kick drum under 120 Hz and shifts the whole grid when it is off
- moves where the music starts so hard cuts and reveals land on beats, and reports the error per cut in ms
- loops loudness on the exported MP4 itself to -16 LUFS with the true peak under -4 dBFS, and checks the mono downmix
- writes a before and after frame and the waveform for every cue (`checks/`), `SOUND.md` with five timestamps to check
  on headphones, `CREDITS.txt`, a licence check, and `report.html` with a play button and swaps for every cue

```
python scripts/sound_pass.py --video silent.mp4 --cues cues.json --music track.mp3 --manifest sfx/manifest.json --out out
```

`cues.json` is a list like `[{"t": 2.0, "type": "scene_cut", "desc": "cut to card"}]`; the types and the sound each
gets are in `SKILL.md`. Needs ffmpeg and the Python packages librosa, soundfile, numpy, scipy and matplotlib.

The default kit's typing sound is a Mixkit file that the script downloads at run time into the output folder; Mixkit's
licence allows it in videos but forbids redistributing it, so it is never bundled here. `--swaps` can point a cue at a
bundled CC0 typing sound instead.

`animation/sfx` is the other route: every sound synthesized in code. Both master to a measured loudness.

From motion-graphics by Bart (Barty-Bart, MIT, see LICENSE; the sounds are CC0 as listed), upstream commit 3d83d98
. Changes here, for Windows: the check files go under the output folder (it wrote to `/tmp`), and
`SOUND.md`, `CREDITS.txt` and `report.html` are written as UTF-8. Tested on Windows 11: 16 s for a 12 s
video with seven cues, -16.5 LUFS, peak -5.2 dBFS on the exported MP4; the grid was 164 ms off the kick and was shifted.
