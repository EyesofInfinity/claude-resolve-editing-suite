# Develop Blur Dissolve and Develop Kaleido Polar

Camera blur and warp dissolves in one Transition DCTL, and the two kaleidoscopes Develop Kaleido lacks in one transform
DCTL. Our own code, built from what a camera, a soap film, a ball, a fluid and a mirror do. MIT
License. Install with `python -I ../build.py . --install`. Then lay the dissolve on a cut from
Edit page > Effects > Video Transitions > ResolveFX > DCTL and pick `Develop\Blurdis\Develop Blur Dissolve`; put Kaleido
Polar on a clip as an OpenFX DCTL effect or a DCTL plugin node.

## Develop Blur Dissolve

| Style | What it does | Lay it |
|---|---|---|
| 0 Bubble | soap bubbles blow up over the outgoing shot and rise, each a window onto the incoming one in a gentle dome, the frame behind showing toward the rim, the scene mirrored in thin-film colours, two window glints; the frame dissolves behind them and they pop | 24 to 36 frames |
| 1 Shake | a handheld jolt through the cut, translation and roll, pushed in just enough that the edge never shows | 16 to 24 |
| 2 Sphere | the outgoing shot curls onto a ball that turns half a turn to bring the incoming one round from its far side, lit from the upper left over a dimmed, out-of-focus backdrop, then flattens | 30 to 40 |
| 3 Crash Zoom | a zoom crashes in on Center X, Y and back out, the shots dissolving through the fastest frames | 12 to 20 |
| 4 Cross Zoom | a zoom burst: the framing nearly still, the streaks' centre travelling along Angle while the shots cross | 16 to 24 |
| 5 Directional | a pan blur along Angle rises and falls while the shots cross, a short drift with it | 12 to 20 |
| 6 Spin | the camera rolls about Center X, Y, the incoming shot rolling in the same way to rest | 16 to 24 |
| 7 Vector | each shot smeared along its own contours, as a brush follows the forms | 24 to 36 |
| 8 Curl | the picture carried and smeared by a swirling, incompressible flow, as ink in water | 24 to 36 |
| 9 Kaleida | a kaleidoscope's mirrors close over the outgoing shot, its picture turns into the incoming one, the mirrors open | 24 to 36 |

Overlap with the other families, and what this one adds:

- Develop Push's Hyper Push and Hyper Pull zoom about the frame centre and cut on the middle. Crash Zoom is the
  dissolve: aimed at Center X, Y, the shots crossing over the fastest frames. Cross Zoom is a zoom burst, which Push
  does not have at all.
- Develop Push's Swish travels a frame's width and cuts. Directional stays put, blurs and dissolves.
- Develop Warp's Vortex twists about the centre by distance; Spin is a rigid camera roll with real motion blur. Warp's
  Smoke reveals through a noise mask; Curl moves the picture itself through a fluid flow.
- Develop Kaleido already gives Kaleida's look as a static effect; Kaleida here is the dissolve through it.
- Resolve 21 ships Camera Shake, Crash Zoom and Spin transitions; these add the dissolve, the shutter-true blur and the aim.

Every moving style (Shake, Crash Zoom, Cross Zoom, Directional, Spin, Kaleida) is a real camera's motion blur: the move
is read at the shutter's two ends and middle, and the pixel averages as many taps as keep them 1.5 px apart (up to 64),
each at its own instant inside the shutter, bilinear, in linear light, offset by a per-pixel hash so a long streak
reads as fine grain and never as a ladder. Shutter is the shutter angle (180 is a film camera's), Frames the length the
dissolve is laid, so the blur in each frame matches the move in that frame. Every style starts exactly on the outgoing
shot and ends exactly on the incoming one, and eases in and out (mean change under 0.005 at 0.02 and 0.98).

## Develop Kaleido Polar

| Mode | What it does |
|---|---|
| 0 Polar | mirrors in angle (Slices) and in distance from Center X, Y (Rings), so mirrored rings of slices repeat out from the centre; the picture turns behind the mirrors (Spin) and the rings flow (Flow) |
| 1 Fly's Eye Circles | a packed array of round lenslets, each a small dome holding the picture seen from its own place (View), darker toward its rim, a glint as bright as what it sees; the gaps show the picture darkened (Gap) |

Both take as many taps a pixel as the squeeze of the picture asks for (up to 36 in Polar's centre, 25 in a lens), so the
fine rings and the minified pictures never alias. Mix 0 returns the picture exactly. Develop Kaleido
(`effects/fx/Develop Kaleido.src.dctl`) is unchanged.
