# edit: cut a talking take from its transcript

Silences trimmed to a breath, stutters, false starts and retakes found for your review, every cut snapped to real
quiet in the audio with a short fade, and the whole edit rendered once from the source. Everything runs locally.

```
python -I transcribe.py take.mp4 work/take.json
node cut-silences.mjs work/take.json --pace natural --out-dir work
node find-cut-candidates.mjs work/take.silence-transcript.json --out-dir work
```

Read `work/take.cut-candidates.md`. Each candidate shows what it removes and what it keeps, with a recommendation
(`cut` or `review`); deliberate repetition must stay. Write the ones you approve to `work/approved-cuts.json` as
`{"cuts": [{"start": 12.3, "end": 14.1, "reason": "false start"}]}`. Times are in seconds, as `take.cut-candidates.json` gives them;
the page's `01:02.08` form works too. Then:

```
python -I compose_edl.py work/take.silence-edl.json work/take.silence-edl.json work/approved-cuts.json work/combined.json
python -I snap_edl.py take.mp4 work/combined.json work/final-edl.json final.mp4
python -I join_check.py take.mp4 work/final-edl.json final.mp4
```

`join_check.py` lists every join cut through sound, every possible click and the level step at each join, worst
first: listen to those. `build-edl-review.mjs` makes a review page from an EDL.

To keep working on the cut in DaVinci Resolve Studio, lay it on a new timeline on the original media:

```
python -I to_resolve.py take.mp4 work/final-edl.json --timeline "Take, first cut"
```

The tools refuse to write over their source media and input files. `snap_edl.py`, `cut-silences.mjs` and `apply-cuts.mjs` also refuse an
existing render or EDL unless you pass `--overwrite`. `python -I test_snap.py` checks that, and the snapping, on synthetic audio. For a
take with several audio tracks, pass `--track n` to `transcribe.py`, `snap_edl.py` and `join_check.py`.

## Settings

- `--pace tight | natural | relaxed | N` (cut-silences): how much of each trimmed pause stays. tight keeps 0.14 s
  (0.20 s after a sentence, 0.24 s after a long pause), natural twice that, relaxed three times. On a 150 s narration
  take: 116 s, 122 s, 127 s. tight is the upstream default; a narrator who likes room to breathe picks natural.
- `--gap` (default 0.55 s): pauses shorter than this are never touched.
- `transcribe.py --model`: medium.en by default. The smaller models tidy away fillers and abandoned half-lines, which
  are exactly what the mistake finder needs to see.

## Needs

Node 18+, Python 3 with numpy and faster-whisper, ffmpeg on PATH. The first transcript downloads the speech model, about 1.5 GB.
faster-whisper's GPU route needs the CUDA 12
libraries (`cublas64_12.dll` on Windows); without them `transcribe.py` runs on the CPU (about 40 s for 150 s of
speech with medium.en).

## Where it comes from

`cut-silences.mjs`, `find-cut-candidates.mjs`, `apply-cuts.mjs` and `build-edl-review.mjs` are from Herk Edit Kit by
Nate Herk (upstream nateherkai/herk-edit-kit, commit 10511e5): the original kit is MIT (`LICENSE`), its editing
pipeline is shared under `PIPELINE-USE-PERMISSION.txt`, whose notice must stay with these files, with
`THIRD_PARTY_NOTICES.md`. Changes here, all tested on a real narration take on Windows 11:

- `find-cut-candidates.mjs`: catches a phrase restarted inside one breath ("today I will show you, um, today I will show
  you"), which the segment pass never compared; sends a retake said again with a change to review; starts a retake's
  cut where the restarted line begins, not at the top of its segment (that deleted a good sentence); de-duplicates
  overlapping proposals (described upstream, never done); lists everything a cut removes, and sends a cut that spans
  other segments to review.
- `build-edl-review.mjs`: file links that work on Windows.
- `cut-silences.mjs`: `--pace`, recorded in the EDL params; `--overwrite`, and a refusal to write over the source.
- `apply-cuts.mjs`: `--overwrite`, and a refusal to write over the source.

`transcribe.py`, `compose_edl.py`, `snap_edl.py`, `join_check.py`, `to_resolve.py` and `test_snap.py` are ours (MIT).
