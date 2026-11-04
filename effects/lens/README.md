# Develop lens: defocus, bokeh and a lens's character

Lens defocus and bokeh, and a lens's character: distortion, chromatic aberration, vignetting and camera shake. MIT License. Transform DCTLs: Edit page OpenFX > ResolveFX Color > DCTL, or a DCTL plugin node; installed in `LUT\Develop\Lens`. `lens.h` holds the shared sampling, aperture and spectrum.

| File | What it does |
|---|---|
| `Develop Bokeh.dctl` | 0 Lens Defocus (a lens blur in linear whose taps fill an aperture of Blades, Rotation and Round, turned and jittered per pixel; highlights open into discs with brighter rims; cat's eyes toward the edges), 1 Prism Defocus (red focused wider than blue), 2 Bokeh Lights (drifting shaped lights over the softened picture), 3 Split Field (a sharp band at Focus) |
| `Develop Lens.dctl` | one lens model: Distortion (barrel zoomed to keep corners filled, or pincushion), Aberration (12 wavelengths magnified apart), Fringe (purple round hard highlights), Vignette (cos^4), Edge Softness, Edge Stretch, Shake |

Amount 0 gives the picture back exactly.

    python -I ../build.py .            # build
    node check.mjs                     # off is identity; disc size and hexagon; prism rims; cat's eyes; the split band;
                                       # lens parts at 0 give the picture back; vignette; aberration rims; barrel; shake
    python -I ../build.py . --install

Sliders exist only inside the main function in Resolve: helpers take every value as an argument (the harness refuses a slider read elsewhere), and no comment above the main function names it.
