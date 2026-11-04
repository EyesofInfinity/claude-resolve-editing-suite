# Develop stock: film processes and film stocks

Old colour processes, lab tricks and film stocks. Each is modelled from how the film worked, with parametric curves only: no measured stock data, no LUT, and no stock named after a maker's product. MIT License. Both are transform DCTLs: Edit page OpenFX > ResolveFX Color > DCTL on a clip or adjustment clip, or a DCTL plugin node on the Color page; installed in `LUT\Develop\Stock`.

| File | Kinds |
|---|---|
| `Develop Process.dctl` | Kind: 0 Two Strip, 1 Three Strip, 2 Infrared Colour, 3 Infrared Mono, 4 Cross Slide, 5 Cross Negative, 6 Bleach Bypass |
| `Develop Film Stock.dctl` | Stock: 0 Daylight Negative, 1 Tungsten Night, 2 Vivid Slide, 3 Portrait Negative, 4 Faded Print, 5 Home Movie, 6 Expired, 7 Silver Mono; Wear adds a projector's flicker, gate weave and dust |

    python -I ../build.py .            # build
    node check.mjs                     # off is identity, a frame repeats and grain moves the next, the grey ramp never falls,
                                       # 25 random slider sets in range, and what each kind is for (greys stay grey where
                                       # they should, infrared foliage red and sky blue, cross slide's blue shadows and
                                       # yellow highlights, the faded print's red mids, the gate's dark corners, Wear's weave)
    python -I ../build.py . --install

