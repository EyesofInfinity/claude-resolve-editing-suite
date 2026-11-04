# Develop light effects

Film light leaks, film burns and light dissolves. MIT License.

| File | Kind | Use in Resolve |
|---|---|---|
| `Develop Leak.dctl` | transform, moves by frame | Edit page: OpenFX > ResolveFX Color > DCTL on a clip or an adjustment clip, pick the file. Color page: a DCTL plugin node. |
| `Develop Burn.dctl` | transform, moves by frame | The same. Burn 100 covers the frame; lay it on the two frames before a cut for a short burn. |
| `Develop Light Dissolve.dctl` | transition | Edit page: OpenFX > Transition > ResolveFX Color > DCTL on a cut, pick the file. Style 0 Flash Burn, 1 Leak, 2 Burn Through, 3 Flash. |

Palettes (all three): 0 Violet Burn (measured from real film burn), 1 Classic warm, 2 Lucid, 3 Night blue.

A LUT node freezes the moving two (TIMELINE_FRAME_INDEX is fixed there). Run them as plugins.
