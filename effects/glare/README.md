# Develop Glare and Glow Plus: glares, streaks, halos, glows, a flashed film, a free lens, flashbulbs

Two transform DCTLs, each built from what the real thing is: the optics, the film, the light. MIT License. Edit page OpenFX > ResolveFX Color > DCTL on a clip or adjustment clip, or a
DCTL plugin node on the Color page. Rec.709 gamma 2.4 in and out, light added in linear. Amount 0 returns the input exactly.

In Develop Glare only a real light throws: a lamp, a glint, a small sun,
the moon, standing above a darker surround (judged at three sizes by how dark a ring round it is, and devalued where other
bright specks crowd it), and its glare grows with its size as well as its brightness. A bright sky, a white wall or gaps of
sky in leaves throw nothing.

## Develop Glare

| Mode | What it is |
|---|---|
| 0 Glare | the glare an eye or a hazed lens sees round a light: fine needles of uneven length (Rays) radiating from it, brighter and larger lights reaching further, a faint rainbow ring round a large light, red outside (Colour) |
| 1 Streaks | a streak filter: a long line through every light along Angle, Directions 2 to 4 lines evenly turned; One Side 100 smears each light one way, as a long exposure does; Colour parts the colours toward the tips |
| 2 Chroma Bands | a diffraction grating filter: each light's spectrum either side along Angle, violet nearest and red furthest, a fainter second order beyond; Directions crosses the grating |
| 3 Ice Halos | ice crystals round the sun or moon: the 22 degree halo (Size), sharp and red on its inner edge, the faint 46 degree halo, sun dogs at the sun's height, the upper tangent arc, the parhelic circle and a light pillar (Arcs). Find Sun finds the brightest compact light in the frame (every pixel runs the same search); Find Sun 0 uses Position X, Y. The halo hangs in the sky: where the picture is much darker than the sky round the sun (hills, trees, the sea) it is hidden |

Taps run exactly a pixel apart along needles, streaks and bands, bilinear, the light test anchored at texels and blended by
their light (Develop Optics and Glow Dissolve's lessons), so a line is continuous at 1:1. Streaks reach past 48 px only
from lights broader than the wider spacing there, so a speck keeps a short continuous line.

## Develop Glow Plus

| Mode | What it is |
|---|---|
| 0 Glow | light over Threshold spreads into a glow, blue reaching further than red (Spread, as haze scatters), Falloff from a tight halo to a long tail, Key Hue and Key Width for chosen colours, Atmosphere breaking the far glow into slow wisps; it spills round the light and adds little on it. A real light (Develop Glare's compact test) glows in full and counts 2.5 times; a broad bright area such as a sky glows only by Broad (default 15) |
| 1 Distance | a glow measured from the edge of each bright shape, the same width round a thin line as round a big shape, as a neon tube in haze |
| 2 Aura | fine streamers standing out from the outline of bright shapes, as in a corona discharge photograph, flickering at Rate, colour swinging round Tint Hue by Spread |
| 3 Colorize | the glow's own brightness through a gradient, Edge Hue at its rim to Tint Hue and white at its core (the same light test and Broad as Glow) |
| 4 Edges | light hugging the outline of bright shapes (keyed by brightness, a DCTL sees no alpha): outside (Balance 0), inside (100), or both |
| 5 Flashing | a pre-flashed negative: a little even light lifts and tints the shadows and lowers their contrast (Balance 0); a flashed print dulls the highlights instead (Balance 100); Tint Hue is the flash |
| 6 Free Lens | a lens held off the body and tilted: a sharp band at Angle and Position, the blur growing either side (Size), light leaking in at the gap (Balance), the far side vignetted, drifting as the hand does (Rate) |
| 7 Flashbulbs | camera flashes over the frame, each one frame long with a faint afterglow on the next, at Rate, in a band at Position (Spread its height), each lighting what is near it (Balance) |
