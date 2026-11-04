# Develop art: print, ink and paint looks

Print and ink looks: halftone screens, hatching, etching, sketch, cartoon, mosaic and more. MIT License. A transform DCTL: Edit page OpenFX > ResolveFX Color > DCTL, or a DCTL plugin node; installed in `LUT\Develop\Art`.

| Mode | What it does |
|---|---|
| 0 Halftone | ink dots on a screen at Angle, a cosine spot (dots turn to holes past half tone), on paper |
| 1 Colour Halftone | cyan 15, magenta 75, yellow 0, black 45 degree screens printed as inks with a little crosstalk |
| 2 Halftone Rings | rings round the centre, as thick as the tone is dark |
| 3 Crosshatch | up to four layers of hand-drawn pen lines that wobble and break, the darkest filled in |
| 4 Etching | an engraver's line screen bent by the broad light, a second set crossing the darkest, sepia ink |
| 5 Sketch | pencil lines on the edges, light hatching in the shadows, graphite on paper |
| 6 Cartoon | smoothed, cut to Level steps of light, saturated, inked on its edges |
| 7 Mosaic | Roman tiles (jittered cells), bevelled, in grout |
| 8 Scatter | every pixel thrown up to Size away |
| 9 Posterize | each channel cut to few levels through an ordered dither |

Colour brings the picture's colour into the ink and paper. Boil redraws Crosshatch, Sketch and Scatter a few times a second; 0 holds them. Amount 0 gives the picture back exactly.

    python -I ../build.py .            # build
    node check.mjs                     # off is identity; repeats, Boil 0 holds, hand modes boil; tone order; what each mode is for
    python -I ../build.py . --install

