# Develop FX: glows, glints, lightning, rays, kaleidoscopes

Light and stylize effects: glows, star glints, lightning, light rays and kaleidoscopes. MIT License. Every one is a transform DCTL: Edit page OpenFX > ResolveFX Color > DCTL on a clip or adjustment clip, or a DCTL plugin node on the Color page; installed in `LUT\Develop\Fx`.

| File | Modes |
|---|---|
| `Develop Glow FX.dctl` | 0 Darks, 1 Edges, 2 Rainbow, 3 Rings, 4 Noise, 5 Orthicon |
| `Develop Glint.dctl` | star glints on small bright points, 4 to 8 points, Spin, Twinkle, Rainbow |
| `Develop Zap.dctl` | lightning from Start to End, branches, re-strikes (Rate), hue |
| `Develop Rays.dctl` | 0 Point, 1 Edge, 2 Sweep, 3 Puffy |
| `Develop Kaleido.dctl` | 0 Radial, 1 Mirror Tiles, 2 Fly's Eye, 3 Tile Scramble |

    python -I ../build.py .            # build
    node check.mjs                     # off is identity, repeat identical, the next frame moves, 25 random slider sets in range
    python -I ../build.py . --install

