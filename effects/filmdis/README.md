# Develop Glitch Dissolve and Develop Film Dissolve

Two Transition DCTLs. Lay either on a cut from Edit page > OpenFX > Transition > ResolveFX Color >
DCTL and pick the file. Both start exactly on the outgoing shot and end exactly on the incoming, and ease off both
(mean change under 0.005 at progress 0.02 and 0.98). Rec.709 gamma 2.4 in and out.

## Develop Glitch Dissolve

Every style is gritty and dithered. Every glitched pixel gets grain riding its brightness and its colour crushed
through an 8 x 8 Bayer dither (Develop Glitch's levels: 32 at Dither 0, 3 at Dither 100, about 7 at the default 85),
mixed in as far as the pixel is glitched. Glitch 0 is the clean shape of each style.

| Style | What it does |
|---|---|
| 0 Pixel Sort | runs of the bright parts sort themselves toward Angle (nearest of right, down, left, up); the band opens down to Threshold and the runs grow to Size at the cut. The mixed picture is sorted, so the hand-over sorts as one picture |
| 1 Diffuse | the picture breaks into sand: each grain thrown out from its place (most stay near), the shots trading grains through a Bayer and hash threshold |
| 2 Diffuse Wipe | the same on a front crossing at Angle, Softness wide |
| 3 Pixelate Wipe | a front at Angle breaks the picture into blocks, biggest on the front; block sides are base times 2 to 64 in nested grids, each chosen by its centre, so a block never splits; each block goes over whole |
| 4 RGB Displacement | each shot's red, green and blue pushed apart along three directions by the other shot's blurred brightness, widest at the cut |

Sliders: Style, Glitch, Size, Threshold, Angle, Softness, Blend, Grit, Dither, Seed.

## Develop Film Dissolve

| Style | What it does |
|---|---|
| 0 Film Dissolve | the optical printer's dissolve: the two shots add as exposure on the dupe and the print's curve (shoulder and toe) makes the picture, so a highlight given half its light stays near white and the blacks stay down; Highlight Hold sets the curve (0 is a dissolve in linear light). Grain rises through it, as an optical's dupe generation shows. The fades are an S in progress (p^3 / (p^3 + (1 - p)^3)) so a dark pixel is not lifted early through the gamma |
| 1 Film Roll | the loop is lost and the strip slips through the gate: frames roll by with the black frame line between them, streaked by the strip's speed over a half-open shutter (light averaged in linear), weaving and flickering, until the incoming frame settles. Frames sets how many frame lines roll by; Direction up or down |
| 2 TV Roll | the set loses sync at a channel change: the picture rolls with its blanking bar, gathering speed; the horizontal hold goes, the lines skewing and wrapping through the horizontal blanking into diagonal bands, the top of the field bent over, each line jittering; colour drops out (the colour killer), snow comes up and the picture's contrast falls under it, the raster lines show; then the incoming station rolls in and locks. Built from the set's sync; Develop Glitch's Channel Change is a separate, digital take |

Sliders: Style, Highlight Hold, Frames, Direction, Frame Line, Motion Blur, Weave, Flicker, Grain, Sync Tear, Snow, Seed.
