# Develop screens: damaged pictures, retro screens and emboss

Damaged pictures and retro screens beside Develop VHS and Develop CRT, and two emboss styles. Built from what the real things are. Our own code. MIT License. Both are transform DCTLs: Edit page OpenFX > ResolveFX Color > DCTL, or a DCTL plugin node; to be installed in `LUT\Develop\Screens`.

## Develop Screen (moves by TIMELINE_FRAME_INDEX)

| Mode | What it is |
|---|---|
| 0 JPEG Damage | baseline JPEG (ITU T.81): 8 x 8 luma DCT blocks quantised by the Annex K tables at a quality (Strength), chroma at half resolution both ways in 16 x 16 MCUs, Size the sample size (a picture shrunk before coding); bit errors (Rate) run from one MCU to the next restart marker or the frame's end: the MCUs shift along the row, every DC value carries a cast, the first few decode noise in their AC coefficients |
| 1 Digital Damage | a video stream after packet loss: from one macroblock on, a run of macroblocks lost in groups and concealed by smearing down the last good row, by a wrong motion vector that drags further each frame, or with zeroed chroma (green); it spreads frame to frame until the next keyframe clears it |
| 2 TV Damage | an analog set on a failing signal: horizontally streaked snow, sinking contrast, a softened picture, a multipath ghost (Size its delay) with a weaker negative one, hue drift and the colour killer, colour confetti; the vertical hold rolling whole frames through the blanking bar with its data dashes, the horizontal hold shearing the lines into diagonal bands, flagging at the top, hum bars. Develop VHS covers the tape |
| 3 Night Vision | an image intensifier: red and near-infrared weighted photocathode, gain (Strength) into a saturating plate, a soft tube, fixed-size halos round bright sources (Size), scintillation densest in the dark (Rate), the fibre honeycomb and fixed blemishes, a green P43 phosphor (Colour over 50 toward white P45); Shape 0 full frame, 1 one eyepiece, 2 two |
| 4 X-Ray | a radiograph: the picture as density on film, inverted (Shape 0) or bright as dense on black (Shape 1), the film curve (Strength), unsharp-mask edge lift (Size), scatter glow from the densest parts, quantum mottle (Rate, 0 still), a blue base (Colour) |
| 5 LED Sign | round emitters in a grid (Size the pitch) with black gaps, each the mean of its cell at few levels dithered across the emitters (Dither), domed with a faint lens glint, a glow that ends inside the neighbouring cells (Strength), rolling scan bands (Rate), dead emitters; Shape 0 full colour, 1 red, green and blue lamp clusters, 2 amber |
| 6 Misalignment | a three-gun set out of convergence: red and blue beside green, a static offset growing toward the corners, each gun's focus different (Size), purity patches (Colour), a hum wobble (Rate) |
| 7 Video Glitch | a digital link failing: sparkles always, and in drops (Rate) bands of lines repeating the last good line, slipping sideways with a dark wrap seam, decoded in the wrong colour space, or torn field from field (Size the band height, Colour the colour-space share) |

Every mode but the LED sign ends in the house finish (`glitch.h` gritFinish: grain riding the picture and the Bayer dither); the sign dithers its own emitters instead. Amount 0 gives the picture back exactly.

## Develop Emboss (still)

| Style | What it is |
|---|---|
| 0 Shiny | the picture's brightness as a height field (Size smooths it, Detail adds the fine relief, Invert presses it in), a glossy surface in the picture's colours (Colour toward a grey metal), lit from Light Angle and Light Height: diffuse light falling off on the slopes turned away, a white Blinn highlight from a smoother normal (Shine). A flat area keeps the picture |
| 1 Glass | the picture seen through clear glass pressed with the relief: each slope bends the view (Depth), red least and blue most; Fresnel reflection of a dim room on the steep slopes, a faint green tint, the highlight on top |
