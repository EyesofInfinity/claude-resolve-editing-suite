# Develop Glow Dissolve

Light dissolves in one Transition DCTL. Lay it on a cut from Edit page > OpenFX > Transition > ResolveFX
Color > DCTL and pick `Develop\Light\Develop Glow Dissolve.dctl`.

| Style | What it does |
|---|---|
| 0 Glow | the shot's highlights bloom wider and lower as the light rises (Tint colours the light) |
| 1 Rays | the highlights throw rays from Center X, Y, longest at the peak |
| 2 Edge Rays | the same from the picture's edges |
| 3 Glint | small bright points open into stars of 4, 6 or 8 points, turning; Rainbow toward the tips |
| 4 Flashbulbs | bulbs pop over the frame, crowding around the cut |
| 5 Zap | lightning strikes across the frame, a new strike every few frames |
| 6 Orbs | six-bladed bokeh orbs open on the bright parts and drift up |
| 7 Lens Flare | a flare crosses along Angle: core, anamorphic streak, ghosts, halo |
| 8 Light Wipe | a band of light wipes across at Angle, the incoming shot behind it |

The shots throw their own light in Glow, Rays, Edge Rays, Glint and Orbs: the outgoing shot until the cut, the incoming
after it. Light rises as sin squared of the progress, held near zero over the first and last eighth, so it leaves and
lands on each shot exactly. Light is added in linear; Wash brightens the whole frame by exposure at the peak (black
stays black); Blend widens the hand-over from a clean cut.
