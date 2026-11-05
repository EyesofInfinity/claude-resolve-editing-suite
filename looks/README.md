# Looks

A look is a small file of slider values. `develop_apply.py` puts a look on a timeline, shot by shot, in a running DaVinci
Resolve Studio. Each clip gets a new colour version, so its other grades stay.

```
python -I develop_apply.py "looks/Warm Film.json" --timeline "My Timeline" --version "Grade 1"
python -I develop_apply.py --revert "runs/My Timeline 20260101-120000"
```

Add `--clips 1,3,7` for some clips only. Every run writes a folder under `runs/` with the grades, the stills and `run.json`.

| Look | For |
|---|---|
| `Warm Film` | Warm daylight footage: soft bloom judged per shot, a film print, moving grain |
| `Warm Interview` | Faces and rooms: a gentle warm grade that keeps skin natural. Check skin on each clip |
| `Deep Landscape` | Dense colour and deep skies on landscapes. A sky that is already blown can turn salmon: check each shot |
| `Day for Night` | Daylight footage made to read as night |
| `Clean Finish` | Deband and fine grain only. Safe over a finished film, and close to safe on flat brand colour |
| `Warm Film with Leak` | An example of a look that carries an effect |

These looks were tuned on Rec.709 footage. For log footage, see `craft/color.md`: a grade replaces the clip's nodes, so a transform added to the clip first is lost. Treat each look as a
starting point: copy the file, change the values, give it a new name.

## The file

```json
{
  "schema": "develop.look/0",
  "name": "My Look",
  "values": {"contr": 18, "hilite": -35, "bloomAmt": 40, "bloomThr": 55, "filmGrain": 22},
  "per_shot": {"bloomThr": "judge"},
  "effects": [{"effect": "Develop Leak", "values": {"lkAmount": 30, "lkEdge": 200}}]
}
```

- **values:** slider names are the first word in each `DEFINE_UI_PARAMS` line of `Develop.dctl` and of the node files in `nodes/`.
  A slider left out stays neutral.
- **per_shot:** values judged from each clip's own stills. `bloomThr` raises the Bloom threshold on bright shots. `bloomRoll`
  softens the shoulder where that happened. `ntStops` sets how dark each shot goes in a night look.
- **effects:** optional. Any effect from `effects/<family>/build/`, in order, after the grade. Slider names are the first word in
  each `DEFINE_UI_PARAMS` line of that effect's file. A slider left out keeps its default. Keep light effects low.
- **gate:** optional. Limits for the quality flags (`clip_added`, `crush_added`, `energy`, `halo_median`, `frozen`). A flag never
  stops a run. Read the flags and look at the stills.
