# Develop Tritone Dissolve and Develop Deband (the tones family)

Two DCTLs. Rec.709 gamma 2.4 display values in and out. Build with `python -I ../build.py .` from
this folder (or `python -I effects/build.py effects/tones` from the root); both include `../light/light.h`.

## Develop Tritone Dissolve (Transition DCTL)

A dissolve through a printed tritone. Lay it on a cut from Edit page > OpenFX > Transition > ResolveFX Color > DCTL.

A tritone prints a picture's tones with three inks: the darkest ink is the floor, the paper's tint the ceiling, a
middle ink carries the mid tones. Each shot's own luminance is its tone (the display tone of its linear luminance). The
outgoing shot falls into a print of itself, the print's tone crosses from the outgoing shot's to the incoming shot's
(one plate printed from both, a double exposure in ink), and the incoming shot rises out of its own print. The print
keeps each tone's brightness between floor and ceiling: tone 0 prints at the Shadow colour, tone 1 at the Highlight
colour, the Mid colour sits at the tone of its own brightness. The inks mix as display values and the mix is set to the
tone's brightness, so the print re-colours the picture and keeps its light. Starts exactly on the outgoing shot, ends
exactly on the incoming, quintic fades flat at both ends.

Defaults are a classic print tritone: a warm near-black floor #1F1711, a sepia mid #A88A65 and a cream ceiling #F5EBD3
(HSV 28/45/12, 33/40/66 and 42/14/96; each within a code of the hex).

Sliders (`tt`): Shadow Hue, Sat, Level; Mid Hue, Sat, Level; Highlight Hue, Sat, Level (HSV, degrees and percent);
Tone (how fully the picture goes into the print at the peak, 0 is a plain dissolve); Hold (how long the print holds,
percent of the dissolve, 0 to 60); Tone Lead (positive brings the incoming shot in through its shadows first, negative
through its highlights); Pulse and Pulses (the print breathes once to three times, its mid tones lifting and settling,
at most 3 a second for any dissolve over a second).

## Develop Deband (transform DCTL)

Smooths the contour bands of an 8-bit gradient and dithers it so the delivered file holds the gradient. Lay it on a
node after the grade.

Night skies, mist and lifted indigo blacks arrive from 8-bit sources as runs of one code with one-code steps, and a
grade that stretches the shadows makes each step larger. It finds the flat places (the 3 x 3 neighbourhood within
Threshold), and there replaces the pixel with the mean of eight rings of four samples out to Radius. Each ring is two
opposite pairs, so a straight gradient averages back to itself; a ring is dropped when a pair's mean lies past
Threshold from the pixel (an edge or a line between them) or a point lies past about two Thresholds (texture, or soft
shading the reach would flatten). The rings turn and change radius per pixel and per frame. Then a dither of about
half a code spread at Dither 1 (hashed white noise less its four neighbours' mean, so it leans blue; new each frame;
mostly one grain on all channels with a third as much per channel) goes onto the flat places. Pure black and pure white
take no dither, so bars and cards stay clean. Amount 0 returns the input exactly.

Sliders (`db`): Amount (100), Threshold (3 codes of 8 bit; raise it after a grade that stretches the shadows more than
about 3 times), Radius (64 px at 1080), Dither (1 code), Grain Size (1 px at any resolution; up to 6, what it adds above 1 in px at 1080), View (1 shows where it smooths).
Cost: 8 neighbours plus 32 ring taps, 40 RGB reads a pixel, and 20 hashes for the dither.
