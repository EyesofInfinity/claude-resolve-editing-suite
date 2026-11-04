# Develop glitch effects

Glitch transitions and pixel sorting. MIT License.

| File | Kind | Use in Resolve |
|---|---|---|
| `Develop Glitch.dctl` | transition | Edit page: OpenFX > Transition > ResolveFX Color > DCTL on a cut, pick the file. Style 0 Snap (a 5-frame glitch cut: lay it 5 frames), 1 Block Tear, 2 Chroma Slip, 3 Static, 4 Channel Change (vertical roll with the blanking bar, skew, static), 5 Crunch (blocks rebuilt from a DC level and two slopes, colour crushed). Grit and Dither on every style. |
| `Develop Pixel Sort.dctl` | transform, Drift moves it by frame | Edit page: OpenFX > ResolveFX Color > DCTL on a clip or adjustment clip. Color page: a DCTL plugin node. Direction 0 right, 1 down, 2 left, 3 up. |

Block Tear is a stuck-block look, not a true datamosh: a true one carries the outgoing shot's pixels along the incoming shot's motion, which needs neighbouring frames (a Fuse or Fusion's optical flow), not a single transition frame.
