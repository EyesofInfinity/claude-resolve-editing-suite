# Develop Diffusion

Diffusion filters and atmosphere in one transform DCTL. Each mode is built from the glass, the
fabric, the film or the air it names, in our own words and code. The light is scattered in linear (Rec.709 gamma 2.4).
The clipped highlights get back the brightness the camera could not hold (Highlights), so they bloom the way a real
filter blooms a light much brighter than white. Edit page OpenFX > ResolveFX Color > DCTL on a clip or adjustment
clip, or a DCTL plugin node. MIT License.

| Mode | What it is |
|---|---|
| 0 Black Mist | a black mist filter: a small share of all light scattered, the highlights' light in a steep power-law halo; shadows lift only a little |
| 1 Diffusion | a white mist or diffusion filter: more light scattered and wider, shadows go milky, the highlights glow broadly |
| 2 Fog | a fog filter: a wide veil of the picture's own light lifts the blacks, the highlights glow far, detail softens a little |
| 3 Double Fog | more veil and a tight halo, so definition is kept; Depth thickens it toward the top |
| 4 Frost | frosted glass: a gaussian scatter of moderate width, the scattered light pale and a little cool |
| 5 Soft Focus | a soft focus lens: spherical aberration lays an out-of-focus disc of each point under the sharp image (Softness its edge) |
| 6 Net | a net stocking: the weave diffracts each light into a soft cross along the threads (Angle), colours parting toward the tips (Colour); the rest softens a very little |
| 7 Silk | a silk stocking: a short scatter fills fine dark texture while edges keep their sharp core, a faint six-point sheen, a touch ivory |
| 8 Center Spot | clear glass at Position (Spot, Softness), a soft focus and glow around it |
| 9 Halo | a corona round each light, as thin cloud of droplets of one size throws round the moon: a ring red outside, blue inside, an aureole within |
| 10 Atmospheric Glow | forward scattering in hazy air: a long warm aureole round the lights, a pale haze of the scene's own light; Depth thickens it toward the top |
| 11 Film Glow | film halation and bloom: a tight red-orange fringe round each highlight (light back off the film base, Colour how red), a soft bloom over it; each dye layer saturates on its own |
| 12 Smoke and Fog | a slow drifting bank of smoke and fog, two layers at two depths billowing as they move, lit by the scene's own light (Density, Speed, Angle the drift, Depth how low it pools); moves by TIMELINE_FRAME_INDEX |

Thirteen modes. Modes 0 to 11 hold still, as a filter on a lens does. Amount 0 or Strength 0
gives the picture back exactly. Strength 50 is about a quarter grade, 100 about a two.

## How the wide blurs stay smooth

- Halos (`gatherD` in `diffusion.h`): stratified rings of taps, 1.18 apart in radius for the power-law halos, each
  ring turned a golden share of its tap gap past the last, the whole set turned and slid outward per pixel by a white
  hash. Gaussian and exponential kernels use log-spaced rings too. Kernels taper to nothing over the last fifth of
  their reach. On the wide power-law halos only (Black Mist, Diffusion, Fog, Double Fog, Atmospheric Glow), a
  highlight gathered by fewer than about three taps fades (the guard), so a far speck prints no grain.
- Veils (`veilD`): a gaussian read off a lattice of nodes fixed in the frame, each node the mean of five taps,
  weighted smoothly by distance. Neighbouring pixels read the same nodes, so the veil carries no grain at all.
- Net and Silk arms (`armsD`): taps exactly a pixel apart along each arm, each read across the arm at five points so
  the arm widens into a wedge of about 4 degrees as it goes.
- The shoulder (`outD`) rolls only the added light into white, from a knee at 0.8 or the pixel's own brightest
  channel, so the picture's own brights are never pressed down.
