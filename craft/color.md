# Colour: how to grade

Grade after the picture is locked. A grade done early is redone. [practice]

## The order

1. **Get to Rec.709.** Log footage needs a Color Space Transform first. The looks here expect Rec.709.
2. **Balance each shot.** Set exposure and white balance so every shot is correct on its own. Do not reach for a look yet.
3. **Match neighbours.** Make shots in a scene read as one place and time.
4. **Apply one look** over the balanced shots. The look holds colour and mood. Exposure belongs to each shot, so keep it out of the look.
5. **Fix locally.** Faces, one colour, a bright window.
6. **Finish.** Deband if skies or gradients show steps, then fine grain last, as a dither and to tie mixed sources together.

One filter on everything, with no balancing, is the most common amateur grade. [practice]

## How to do it in this suite

- `develop_apply.py` puts a look file on a named timeline, shot by shot, on a new colour version. See `looks/README.md`.
- **Balance and look share one file.** The tool has no separate balance stage, and a look can judge only Bloom and night exposure per shot. So group clips by camera and scene, copy the look once per group, and change `expo`, `temp` and `tint` in each copy. Add your correction to the look's own `temp`. Run each group with `--clips` and the same `--version`, each with its own `--out`.
- **To measure shots before grading,** run a look with empty `values` on a version named "Measure", with `--no-review`. Its stills in `judge/` show the ungraded shots, and the run prints the clip numbers. Read them with `python -I tools/judge.py <still> --report`, which gives levels, clipping, cast and a suggested Temp and Tint. Its exposure advice aims the whole frame at a median, so expose faces by eye instead. Run `--revert` on this pass before the real grade.
- **Other sliders:** `contr`, `hilite`, `shadow`, `whites`, `blacks`, `vibr` and `satur`, and skin with `skinU` and `skinP`. Slider names are in `Develop.dctl`.
- **By hand only:** a look file cannot hold a window, a qualifier, Key Output gain or a Color Space Transform, and an apply replaces the clip's nodes on that version. A look with no per-shot values goes in as one baked node with no sliders. To change it, write a new look and run a new version.
- **Log footage:** stop and tell the user. It needs Resolve's colour management or a transform set up first, and that changes their project, so ask.
- **Other tracks:** `--track 2` grades B-roll on track 2. The default is track 1 only.
- Read the printed gate flags (`clip_added`, `crush_added`, `energy`, `halo_median`, `frozen`) and open the stills. A flag asks you to look, and it does not stop a run. The flags compare the whole grade against the look node alone, so they miss a face clipped by `expo` and a skin shift from `temp`: check those yourself.
- Always tell the user each run folder and `--revert`. Stacked runs revert newest first.
- Start with `Warm Film`, `Warm Interview`, `Deep Landscape`, `Day for Night` or `Clean Finish`, then copy and change. A bright window behind a face wants `"per_shot": {"bloomThr": "judge"}`, as in `Warm Film`.

## What to look at

Open stills from every scene at full size. Build a strip of neighbouring shots side by side. Bad matches show up when shots touch.

- **Exposure of the subject.** Faces land by skin tone: lighter skin around 60 to 70 percent on a waveform, darker skin around 40 to 55. [practice] Expose for the
  person, and let other parts of the frame fall where they fall.
- **Neighbouring shots.** Median brightness within about a sixth of a stop, unless the change means something. That is about 12 percent in linear light and about 5 percent on the display values that `--report` prints. [default]
- **Whites and blacks.** Keep detail you want. A crushed shadow can be a choice. A clipped face rarely is.
- **Colour cast.** Find something that should be neutral: a white wall, a grey shirt, a shadow.
- **Skin.** Skin of every ethnicity sits close to one hue on a vectorscope, between red and yellow, and differs mainly in brightness. [practice] Green or magenta faces read as wrong before anything else does. Check skin on every look, and pull the look back before you let it move a face.
- **Saturation.** Reduce saturated colours that draw the eye off the subject. Foliage and skies are the usual cases.

## Building a look

- Choose it from the feeling in the brief. Warm and soft reads as human and nostalgic. Cool and contrasty reads as tense or technical. Dense colour and deep shadow reads as cinematic. Low saturation reads as serious. Bright and clean reads as modern and open.
- A look is a small set of decisions: contrast shape, where shadows and highlights lean, which colours get richer. Two colours working against each other, usually warm against cool, give depth.
- Add density by darkening saturated colours, which reads like film. Adding plain saturation reads like a phone filter.
- Warm a shot by shifting hue. Raising saturation to warm it looks garish.
- Hold back. Most looks get better at 60 to 80 percent strength. Lower the look's values, or lower Key Output gain by hand.
- Grain: fine and even. Coarse grain falls apart in web compression. Test on the real delivery. [practice]
- Film effects such as halation and bloom come before grain. Use them where highlights exist. Generated light can read as pasted on, so see `EFFECTS.md`.
- Keep titles and graphics out of the grade. Put them on their own track with no look on them.
- A flat-colour brand film is usually not graded at all, since a grade moves exact brand colours. A light finish is safe: `looks/Clean Finish.json`.

## The look by job

| Job | Grade |
|---|---|
| Talking head, teaching | Clean, natural skin, gentle contrast, a little warmth |
| Interview, testimonial | Natural skin first, soft shadows, one look across all sittings |
| Documentary | Honest and consistent. Differences between places can stay |
| Promo with real footage | Punchy, brand colours safe, deep blacks |
| Wedding, event | Flattering skin and clean whites across very mixed light |
| Vlog, travel | The feeling of the place, one consistent colour family |
| Music video | Anything the song earns. Strong looks and changes between sections work here |
| Screen recording | No grade on the screen itself |

## Mixed sources

- Phone, camera, stock and generated footage need the most balancing. Lower contrast and saturation on the punchiest shot, and match toward the plainest good shot.
- Denoise waxy generated footage first, then grain. Shared fine grain across the timeline hides differences better than fixing each clip. `Grain Match` can copy a clip's grain to another.

## Delivery

- Grade for Rec.709 gamma 2.4 and tag the file 1-1-1. [practice] Macs may show lifted shadows, so check on one if the audience uses them.
- Render at a high bitrate. YouTube recommends about 8 Mbps for 1080p at 24 to 30 fps and 35 to 45 Mbps for 4K. Upload well above where you can. [standard]
- An upload above 1080p usually earns a better compressed stream, even for a viewer at 1080p. [practice]
- Deband before encoding, and let fine grain or noise act as the dither. Banding in skies and gradients is the first thing web compression breaks.
- Check the delivered file. Compare a frame from the export against the timeline.
