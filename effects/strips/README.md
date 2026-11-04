# Develop strips: card, strip and swish moves, wipes with character, and the strip looks

Card, strip and swish moves, the wipes Resolve 21 does not ship, and strip looks. MIT License. Two DCTLs, built from what the real thing is (cards in perspective, strips of film, a prism, a wide lens, smoke, glass). Our own code.

## Develop Strip Move (Transition DCTL)

On the Edit page, Effects > Video Transitions > ResolveFX > DCTL on a cut, then pick `Develop Strip Move`.

| Style | What it does | Lay it |
|---|---|---|
| 0 Card Flip | a wall of square cards (Count across) turns over along Angle, each in perspective, lifting toward the lens (Amount), shaded by its turn with a sheen (Light), the incoming shot on its back | 24 to 36 frames |
| 1 Parallax Strips | strips along Angle, each a layer at its own depth: far ones shrink, dim and drift slowly, near ones race, each carrying the incoming shot in behind | 24 to 36 |
| 2 Strip Slide | strips slide alternately one way and the other, set off one after another (Stagger), each a ribbon with the incoming behind the outgoing, motion blurred | 18 to 30 |
| 3 Swish Prism | a whip pan whose blur splits into the spectrum: red leads, blue trails | 8 to 12 |
| 4 Swish Warp | a whip pan through a wide lens: the middle leads, the edges lag and bow, the picture stretches along the move at the cut | 8 to 12 |
| 5 Smoke Wipe | a bank of smoke rolls across along Angle; the picture softens and veils inside it | 24 to 36 |
| 6 Texture Wipe | the incoming shot burns through along a marbled texture (Amount: how far the texture leads a straight wipe), the edge lit by the shot's own light | 24 to 36 |
| 7 Cells Wipe | the frame breaks into cells that open from their centres, a rim of light on each opening, a dark seam between cells | 24 to 36 |
| 8 Bubble Wipe | glass bubbles swell and merge; inside each the incoming shot magnified through the glass, a window highlight on the crown, the outgoing caught on the rim | 24 to 36 |
| 9 Lens Wipe | a glass rod rolls across; the picture under it bent and magnified toward its middle, colours parting at its edges, a highlight down its side | 20 to 30 |
| 10 Stretch Wipe | strips of the incoming shot shoot in along Angle, stretched out long and settling as they land | 18 to 30 |

The six wipes picked are the ones with character that Resolve 21 lacks (it ships Box, Checker, Tile, Vee, Radial, Multi Circle, Luma Wipe, the Mosaic wipes, Shape Transition and its stingers). Every style starts exactly on the outgoing shot and ends exactly on the incoming one. Sampling is bilinear with mirrored edges; blurs take a tap every 4 px (8 to 48) from a start that differs pixel to pixel, so a long blur reads as fine grain, never as copies.

## Develop Strip Look (transform DCTL)

Edit page OpenFX > ResolveFX Color > DCTL, or a DCTL plugin node. Look 0 gives the picture back exactly.

| Mode | What it does |
|---|---|
| 0 Borders | a mat over the picture's edge: Size its width, Tone its paper, a bevel cut lit from the upper left (Level), a torn deckle edge (Roughness), feathered (Softness), its shadow on the picture (Light) |
| 1 Colour Choke | the printer's spread and choke: colour regions grow into their neighbours (Spread above 0, the light spreads) or shrink back (below 0), over a round reach of Size up to 6.5 px at 1080; Level lets each channel choke on its own |
| 2 Strip Slide | strips along Angle, each slid along its length (Level), smooth wave to random (Roughness), kept sliding by Speed and blurred by it (Softness), the cuts shaded (Light) |
| 3 Infinite Zoom | the frame holds a copy of itself (Size: how much smaller), without end, and the camera falls into it forever (Speed, Phase); every loop the same. Level a thin frame of Tone round each copy, Light its shadow. Each copy is box-filtered by how far it is shrunk, so it never shimmers |
| 4 Fluted Glass | reeded glass: each strip (Size wide, along Angle) a convex cylinder lens bending the picture behind it (Level), past about 20 turned over and repeated, a highlight on each ridge and a dark line at each join (Light), a little soft (Softness) |
