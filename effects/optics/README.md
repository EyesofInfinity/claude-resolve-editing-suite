# Develop optics: pastel, pencil, rainbow, soft light, star and flag

Six looks: Pastel, Pencil, Rainbow, Soft Light, Star and Flag / Dot. Each is built from what the real thing is, in our own words and code. MIT License. A transform DCTL: Edit page OpenFX > ResolveFX Color > DCTL on a clip or adjustment clip, or a DCTL plugin node; installed in `LUT\Develop\Optics`. `optics.h` holds the strokes, the flow of the forms, the paper's tooth, the point test and the shapes, on top of `lens.h`.

| Mode | What it does |
|---|---|
| 0 Pastel | soft chalk laid in two layers of strokes on toned paper: each stroke one colour, laid along strong edges (Angle where the picture is flat), giving way at the picture's edges; the chalk lifted and matte, catching on the tooth and in grooves along the stroke |
| 1 Pencil | a graphite drawing whose whole tone is strokes: they follow a clean edge and hatch at Angle across tangled detail (foliage), a second set crosses them in the darks, contour lines where a form turns dark; Softness stumps it smooth, Colour makes it coloured pencil |
| 2 Rainbow | a primary bow at 42 degrees round Position (Y the bow's top), red outside, each of twelve wavelengths its own band; a faint supernumerary inside, the sky brighter inside, the dark band, the reversed secondary at 51 degrees; faded by the rain along the arc and striped by falling shafts |
| 3 Soft Light | a big soft source: what sits darker than the light around it is filled toward it, the brights diffuse a little and glow, and a broad light from Position, coloured by Warmth, lights the picture |
| 4 Star | a star filter: compact lights over Threshold (standing well above a dark surround, so a sky, a pale disc or a gap between branches throws nothing; a speck in a field of other bright gaps counts for little) throw Points arms at Angle, on 8 the second four shorter. Taps a pixel apart run every arm unbroken to its tip; where many lights' arms cross, the far parts are shared out, so foliage sparkles without a mesh. Red reaches further than blue so the tips part into faint beads (Colour) |
| 5 Flag / Dot | a flag (Round 0) or a dot (Round 100) set in the light, Size, Aspect and Angle, at Position: up to three stops of key light cut (Level) with a soft penumbra (Softness), the brights cut more than the shadows the key never reached, the shade a little cool from the fill (Colour) |

Pencil sits beside ART's Sketch (edge lines over light hatching): Pencil builds the whole tone from strokes that follow the forms. Star sits beside FX's Glint (twinkling, spinning glints on small points): Star is the fixed filter on a lens, every arm a falling diffraction spike with its colours parting. Boil redraws the Pastel and Pencil strokes every few frames (Boil 30 every 10 frames, 100 every 2), as a drawn film boils: strokes held still over moving footage slide like a screen door. 0 holds them; the paper's tooth never moves. The other four modes hold still, as a filter on a lens does. Amount 0 gives the picture back exactly.

    python -I ../build.py .            # build
    node check.mjs                     # off is identity in every mode; repeats, boils or holds still; Pastel's strokes run the hand's way,
                                       # lift and keep a colour, stop at an edge; Pencil's tone order, strokes follow the forms, differs
                                       # from Sketch; the bows' colour order and dark band; the shadow filled, Warmth; Star's arms by
                                       # Points, colours parting, no wall off a bright sky, exact below Threshold; Flag / Dot's stops,
                                       # round and square, brights cut more than deep shadows; range
                                       # its frame-to-frame change over the shot's own, raw and over each one's gradient (near 1 is no shimmer)
    python -I ../build.py . --install

Sliders exist only inside the main function in Resolve: helpers take every value as an argument (the harness refuses a slider read elsewhere), and no comment above the main function names it.
