# Develop sky: atmosphere and sky

Atmosphere and sky: aurora, night sky, moon, dust, sparkles, caustics, fog, rain and snow. MIT License. A transform DCTL: Edit page OpenFX > ResolveFX Color > DCTL, or a DCTL plugin node; installed in `LUT\Develop\Sky`.

| Mode | What it does |
|---|---|
| 0 Aurora | curtains from a wavering ribbon at Height, rays rising, green below and violet above (Hue turns both) |
| 1 Night Sky | stars of many sizes and colours, the bright ones twinkling with a cross, a milky band with dust lanes |
| 2 Moon | a moon at X and Height with maria, craters, limb darkening, a phase by Density, a halo |
| 3 Rain | three depths of streaks leaning with Wind, lit by the picture; the scene a little darker and duller |
| 4 Snow | three depths of flakes falling and swaying |
| 5 Dust | motes drifting, seen only where the picture is bright |
| 6 Sparkles | brief star glints on bright points |
| 7 Caustics | a warped web of light, as under water |
| 8 Fog | low fog drifting toward Height, lit by the scene |

Sky Mask (modes 0 to 2): 100 keeps them to smooth sky (smooth at four scales) above Height, dark sky for Aurora and Night Sky, so trees stand in front; 0 lays them everywhere. A black silhouette reads as sky, so set Height to the sky line. Everything moves by frame; light is added in linear. Amount 0 gives the picture back exactly.

    python -I ../build.py .            # build
    node check.mjs                     # off is identity; repeats, moves; the mask; what each mode is for; 30 random slider sets
    python -I ../build.py . --install

