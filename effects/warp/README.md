# Develop warp: blur and warp dissolves

Blur and warp dissolves. MIT License. A Transition DCTL, installed in `LUT\Develop\Warp`: on the Edit page, a DCTL transition on a cut, its file `Develop\Warp\Develop Warp`.

| Style | What it does | Lay it |
|---|---|---|
| 0 Defocus | a rack to soft focus and back through the cut; a 48-tap lens blur in linear, highlights opening into bokeh (Glow) | 16 to 30 frames |
| 1 Prism | the picture parts into its spectrum along Angle, the shots cross in the split | 16 to 24 |
| 2 Melt | the outgoing shot drips away in broad tongues, smeared by speed, a wet light on its edge | 24 to 36 |
| 3 Smoke | rising, wispy smoke carries the incoming shot in, both softened inside it | 24 to 36 |
| 4 Vortex | a whirlpool twists the outgoing shot in and the incoming out | 16 to 30 |
| 5 Ripple | broad rings of water run out through both shots | 20 to 30 |

Every style starts exactly on the outgoing shot and ends exactly on the incoming one.

    python -I ../build.py .            # build
    node check.mjs                     # exact ends, the crossings, Defocus softest on the cut and its bokeh, Melt and Smoke's
                                       # shares grow, Melt falls and Smoke rises, Vortex about the centre, 30 slider sets
    python -I ../build.py . --install

