# Develop damage: film damage, grunge and burning edges

Film damage, grunge and flicker. MIT License. A transform DCTL: Edit page OpenFX > ResolveFX Color > DCTL, or a DCTL plugin node; installed in `LUT\Develop\Damage`. `damage.h` holds the code of each mode.

| Mode | What it does |
|---|---|
| 0 Film Damage | a worn print in a projector: four lanes of long scratches that live for runs of frames, wander and break as the film moves (most through the base, near white, some green; some dark), one-frame hairline scratches, dirt and lint specks dark and light with ragged edges, a curling hair, a rare emulsion blotch, density breathing frame to frame |
| 1 Grunge | a grime stamp: grime pooled in porous blotches and toward the edges, grit in clusters, mottling, a milky scuffed film along one direction |
| 2 Stains | dried spills: rings darkest at the tide line, fading inward and stopping sharp outside, a second ring in some, mottled inside |
| 3 Scratches | a scratched surface: fine scratches mostly one way catching the light, a few dark gouges, hairline wear |
| 4 Light Flicker | an unsteady light: the exposure wanders, jumps at high Speed, sputters now and then, unevenly across the frame, warming as it dims |
| 5 Edge Burn | bright shapes (a title) roughened at the edges, then burned away by Burn: the shape gives way to the ground behind it, scorches brown just inside the front, and the front glows |

Film Damage, Light Flicker and Edge Burn's front move by TIMELINE_FRAME_INDEX; Grunge, Stains and Scratches hold still (Seed gives another). Amount 0 gives the picture back exactly. Edge Burn is for a light title over a dark ground or on the title clip itself: everything brighter than Key burns, so on a daylight picture the sky burns too. Keyframe Burn from 0 to about 90.

    python -I ../build.py .            # build
    node check.mjs                     # off is identity; repeats; stamps hold, the rest move; long scratches and specks;
                                       # flicker wanders and warms as it dims; stains darken warm; lit scratches;
                                       # grunge at the edges; Edge Burn: untouched under Key, Burn 0 roughens, 100 leaves
                                       # the ground, the front glows orange; range
    python -I ../build.py . --install

Sliders exist only inside the main function in Resolve: helpers take every value as an argument, and no comment above the main function names it.
