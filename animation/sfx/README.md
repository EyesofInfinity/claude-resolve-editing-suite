# sfx: sound effects made in code

Every sound is synthesized in pure Python (standard library only, nothing to install): clicks, keystrokes, blips,
pops, chimes, whooshes, risers, impacts, pencil scratch and a music pad. A cue sheet places them on the same timeline
JSON the picture reads, so retiming the picture retimes the sound. The mix masters itself to -14 LUFS with the true
peak at or under -2 dBFS, so an AAC export stays under -1 dBTP. The same score renders byte for byte the same.

From the `animation` folder:

```
python -m sfx --list
python -m sfx sfx/examples/effort.py --timeline sfx/examples/timeline.json --out out.wav
```

`python -I` leaves the current folder off the import path, so run it without `-I`.

`SOUND-DESIGN.md` is the upstream guide: which sound goes with which visual event, the gain hierarchy, panning and
key. Its `npm run sfx` lines belong to the upstream example project; use the commands above.

From claude-motion by whaleyxbt (MIT, see LICENSE), copied from upstream commit e627941 unchanged.
