# Develop Stage Light and Develop Laser

Two transform DCTLs: lamps that relight the picture, and beams, arcs and a muzzle flash added as light.
Lay either on a clip from Edit page > OpenFX > ResolveFX Color > DCTL, or as a DCTL plugin node. Rec.709 gamma 2.4 in and
out; light is added in linear and the picture is relit by multiplying, so black stays black outside a beam or flame.
Amount 0 returns the input exactly.

## Develop Stage Light

| Mode | What it does |
|---|---|
| 0 Spotlight | an elliptical pool (Size, Aspect, Angle, Position) with a soft penumbra (Softness); inside the picture gains Light stops, a little more at the centre as a lamp's field does, coloured by the gel (Gel warm or cold, Colour and Hue for a coloured gel); outside it falls to Ambient stops |
| 1 Reverse Spotlight | the same pool cut out of the light: the pool falls to Ambient, the rest takes Light and the gel (set Light 0 and Gel 0 to leave the rest untouched) |
| 2 Stage Light | Beams lamps on a rig at Position X and Rig Y (above the frame by default), Rig Width apart, aimed at Angle and fanned by Fan, each a cone Size wide. The haze is lit only inside each cone, brightest near the lamp and thinning about as 1 / distance, smoke and streaks drifting through it by frame; Depth hides the haze behind dark silhouettes (a trunk against a lighter ground); where a beam meets the floor (Landing) the picture is lit in a pool at Light plus half a stop and a little all along the cone; the rest falls to Ambient. Sweep and Speed swing the beams in a scissor; Hue Spread fans their colours |

## Develop Laser

| Mode | What it does |
|---|---|
| 0 Laser Beam | a straight beam Start to End: a white core, a narrow coloured glow, clumps of haze drifting along it that brighten the beam where they pass (Haze), shimmer along its length and a frame to frame flicker (Flicker), hot spots at the emitter and the strike, the struck surface lit by multiplying. Length under 100 makes it a bolt travelling Start to End Rate times a second |
| 1 Zap To | an arc Start to End on the same noise path as Develop Zap's bolt, forking (Branches), a new path Rate times a second; on a strike's first frame the leader reaches part way and lands on the next; white contacts at both ends; the arc lights the scene round it |
| 2 Zap From | Count arcs thrown out from Start over Spread degrees about Angle, out to Size, each thinning and dying toward its tip, a white electrode at Start |
| 3 Muzzle Flash | at Start along Angle: a forward flame and Points side jets round a white core, torn at the edges by noise, burning tongues through it, a few grains flung forward. It fires every Interval frames by TIMELINE_FRAME_INDEX and lives Life frames (default 3: full, about a third, about a ninth), larger, cooler and more orange each frame; its light falls on the scene round it as a point source's does. Interval 0 holds the first frame |

Time runs at 24 frames a second for Rate, Speed and the drift (as Develop Zap); Interval and Life count frames.
