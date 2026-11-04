# Develop presets: textures and camera filters

Two families of ready looks: procedural textures and camera filters (numbered colour and black and white filters, gels, polarizer, graduated ND). Built from scratch, from the things themselves. MIT License. Two transform DCTLs: Edit page OpenFX > ResolveFX Color > DCTL, or a DCTL plugin node; to install in `LUT\Develop\Presets`.

## Develop Texture

Seven textures, each laid over or into the picture, each moving slowly by frame (Speed 0 holds it).

| Kind | What it is |
|---|---|
| 0 Cells | living cells under a microscope: thin bright walls (the exact distance to each cell's border), a darker nucleus and nucleolus, granules in the cytoplasm; the cells drift and jostle, the walls curve |
| 1 Flux | the streamlines of a slow turbulent flow running across the frame, thin as ink lines in moving water, bending as the flow drifts downstream |
| 2 Neurons | cultured neurons in fluorescence: round bodies joined by fine wavy neurites that thin away from them, a finer mesh of twigs, each cell glowing and fading on its own (calcium imaging), green by default |
| 3 Ridges | eroded ridges from above: ridged gradient noise, each octave gathered on the one above, the folds rounded, lit from the upper left |
| 4 Folded | paper folded many times and opened flat: 20 to 40 straight creases across the sheet, mountain or valley, flat facets between, each crease lit on one side and shaded on the other, the sheet bent slightly and pressed unevenly |
| 5 Plasma | the glow of a turbulent ionised gas with brighter filaments, violet to rose |
| 6 Weave | plain-woven canvas: round yarns over and under, each yarn its own thickness and shade with slubs and fibres along it, the yarns wandering a little |

Blend: 0 Overlay (display values, centred on the texture's median so the typical pixel keeps its level), 1 Multiply (display values, the texture as a print laid on the picture, its light parts clear), 2 Screen (the texture's lighter half added as light in linear, a double exposure), 3 Displace (the picture seen through glass pressed with the texture's relief, sampled bilinear, up to about 40 px at 1080 and full Strength). Hue 0 keeps each texture's own colour; above 0 it tints round the wheel, Colour sets the tint's saturation. Size, Detail (octaves, line count, folds, fibres), Speed, Seed. Line widths are set in pixels at 1080 rows, so the look holds at any resolution.

Eight more textures are in Develop Texture Plus (`effects/texplus/`).

## Develop Filter

Every filter is its transmission across the spectrum, laid on the light. `spectra.py` writes `spectra.h`: each linear Rec.709 pixel is read as a surface under CIE D65 (three smooth reflectance bands summing to one, so grey is a flat grey surface), seen through the filter at 65 wavelengths (390 to 710 nm) and integrated against the CIE 1931 observer back into linear Rec.709. A filter is therefore a 3 x 3 matrix the DCTL builds at run time from the transmission, so Strength can thicken it (T to the power Strength/100, 200 being two stacked). Exposure opens by the filter's factor as a camera operator's would (at most 2.6 stops, and never so far that white through the filter passes 2 in its strongest channel); past white a colour rolls off keeping its hue. Black and white is the same light on a panchromatic film (its own blue band, the sensitising dyes to about 655 nm, the green gap near 505 nm), then a gentle print curve. Sources: CIE D65 at 10 nm, the Wyman, Sloan and Shirley (2013) fit of the 1931 observer, the XYZ to Rec.709 matrix, all written from published numbers. The filter curves are modelled from their published figures (mired shift, 50% cut-on wavelength and edge, peak transmission, the gel's published colour); no measured vendor table was copied, and none was read.

| Filter | What it is |
|---|---|
| 0 to 7 | 85 (+112 mireds), 85B (+131), 80A (-131), 80B (-112), 81A (+18), 81EF (+52), 82A (-18), 82C (-45): each the ratio of two black bodies a mired shift apart, as these filters are specified |
| 8 to 17 | black and white: pan film alone, then the numbered filters 8 yellow, 11 yellow-green, 15 deep yellow, 21 orange, 23A light red, 25 red, 29 deep red, 47 blue, 58 green, each a long-pass edge or band at its published cut-on |
| 18 to 27 | gels: full CTO (+159), half CTO (+81), full CTB (-137), plus green, minus green, pale amber, deep violet (with its red leak), primary red, moon blue, steel blue |
| 28 | polarizer: Rayleigh skylight is polarized by 0.75 sin^2 / (1 + cos^2) of its angle from the sun; each pixel's direction comes from Lens Angle and Horizon, the sun's from Sun Azimuth and Sun Height, so the darkest band lies 90 degrees from the sun and a wide lens shows it unevenly. Each pixel's skylight share is found by least squares on white haze plus Rayleigh blue and cut by that degree (the sky's own light, a third of it as pure Rayleigh colour), so blue sky and distant haze deepen and white cloud passes; daylit sky only (a night sky's glow is left). Glare Cut takes back part of the neutral sheen where the neighbourhood is coloured (leaves, teal water), so they go deeper and more saturated. Turn rotates it: 0 strongest, 45 none, 90 the reverse |
| 29, 30 | graduated ND and reverse graduated ND: Grad Stops over a transition of Grad Softness at Grad Line, turned by Grad Angle; Grad Colour neutral, tobacco, blue or sunset (the colour spectral, the weight in stops); the reverse densest at the line |

Film: 0 the filter's own (8 to 17 in black and white, the rest colour), 1 colour, 2 black and white (so a polarizer or a grad can feed the pan film too).
