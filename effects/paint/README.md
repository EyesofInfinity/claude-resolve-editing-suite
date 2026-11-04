# Develop paint: strokes, watercolour, tile mosaic, spray

Paint looks: brush strokes, watercolour, an edge-following tile mosaic and spray paint. Built from scratch. MIT License. A transform DCTL: Edit page OpenFX > ResolveFX Color > DCTL, or a DCTL plugin node; installed in `LUT\Develop\Paint`. `paint.h` holds the strokes, washes, tiles and spray (on `lens.h`, `light.h`, `glitch.h`).

| Mode | What it does | Taps a pixel |
|---|---|---|
| 0 Oil Paint | two layers of brush strokes laid along the picture's edges and the flow of its light (a broad layer, then half-size strokes where the colour changes); each stroke one colour taken under it, bowed a little, with bristle streaks, ragged sides, a dry end and impasto lit from the top left; strokes stop short of a hard edge as a painter cuts in | 145 |
| 1 Cartoon Paint | the same strokes in flat colour cut to five tones (black stays black), saturated, inked where the edge holds at two sizes | 161 |
| 2 Watercolour | washes laid in layers (the picture softened through a slow wobble and settled on terraces), the darker wash pooling pigment at its border, the darkest small marks laid over, pigment settling into the paper's tooth, highlights left as paper | 42 |
| 3 Tile Mosaic | square tiles laid square to the frame, turned along the picture's edges and cut where its colour changes; each tile the colour of its own side of an edge, bevelled, in grout that also runs along the edges | 55 |
| 4 Spray Paint | the picture airbrushed and pulled toward stencil tones, then round droplets of three sizes each carrying the paint from where it was aimed (up to 2.5 Size away), so every border is oversprayed; a fine mist | 22 |

Size: stroke, wash, tile or overspray size. Detail: how far small strokes go into detail, how strongly washes settle into steps, how hard tiles cut, how many spray tones. Angle: the strokes' run where the picture is flat (they wander slowly about it). Flow: how far strokes and tiles turn to follow the picture's edges. Colour: saturation. Texture: bristles and impasto, paper and granulation, grout and tile surface, mist. Boil repaints Oil, Cartoon and Spray a few times a second (25: every 11 frames); 0 holds them. Watercolour and Mosaic never move by themselves. Amount 0 gives the picture back exactly.

Cost: taps are texture reads. Oil and Cartoon also hash about 27 stroke centres a pixel and draw the few that cover it three times (for the impasto's slope), so they are the heaviest: on the CPU harness a 1080 frame takes about 20 s for each against 2.4 s for Watercolour, 3.8 s for Mosaic and 0.8 s for Spray.

    python -I ../build.py .            # build
    node check.mjs                     # off is identity; repeats, Boil 0 holds, Oil, Cartoon and Spray boil; strokes follow
                                       # edges (structure tensor) and stop at a hard edge; Cartoon's line; paper, granulation
                                       # and the wet edge; tiles cut and grouted along an edge; overspray reach; range
    python -I ../build.py . --install

Sliders exist only inside the main function in Resolve: helpers take every value as an argument (the harness refuses a slider read elsewhere), and no comment above the main function names it.
