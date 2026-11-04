# Develop psych: psychedelic and colour-cycling looks

Psychedelic and colour-cycling looks. MIT License. A transform DCTL: Edit page OpenFX > ResolveFX Color > DCTL on a clip or adjustment clip, or a DCTL plugin node; installed in `LUT\Develop\Psych`.

| Mode | What it does |
|---|---|
| 0 Blobs | drifting clouds of cycling colour laid on the picture's light (hard light), its shapes kept |
| 1 Stripes | bands of cycling colour along Angle, swaying with slow noise |
| 2 Zebra | the tones cut into Bands stripes crawling down the tones; Colour 0 black and white, 100 a hue a stripe |
| 3 Solarize | tones above Level fold back down, each channel at its own drifting level |
| 4 Pseudo Colour | brightness mapped onto the spectrum, cycling |
| 5 Band Pass | the middle of the picture's detail on grey (a difference of two blurs) |
| 6 Prism | the picture split into its spectrum from the centre out |
| 7 Dog Vision | two-colour sight, red and green merged, a little soft |
| 8 Colour Shadow | three echoes of the picture's light along Angle, each a cycling hue, screened behind it |

Speed cycles the colour by frame; Speed 0 holds it still. Amount 0 gives the picture back exactly.

    python -I ../build.py .            # build
    node check.mjs                     # off is identity; every mode repeats, holds at Speed 0, cycles or holds as it should;
                                       # what each mode is for; 30 random slider sets in range
    python -I ../build.py . --install

