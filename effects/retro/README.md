# Develop retro effects

A worn VHS tape and an old CRT tube. MIT License.

| File | What it does | Use in Resolve |
|---|---|---|
| `Develop VHS.dctl` | Line jitter, a tracking band rolling up the frame, head-switching smear in the bottom rows, colour bleeding and lagging right of the brightness, softened picture with lifted blacks, tape noise, white dropouts, grain and Bayer dither | Edit page: OpenFX > ResolveFX Color > DCTL on a clip or adjustment clip. Color page: a DCTL plugin node. Moves by frame. |
| `Develop CRT.dctl` | Barrel curve with black corners outside the tube, scanlines that thin in the shadows, an aperture grille, phosphor glow, per-frame flicker, vignette, Bayer dither | The same. |

Build, check, install:

    python -I ../build.py .            # build/<name>.dctl
    node check.mjs                     # off is identity, a frame repeats exactly and the next moves, 25 random slider sets stay in range
    python -I ../build.py . --install  # LUT\Develop\Retro; refresh the LUT list in Resolve

