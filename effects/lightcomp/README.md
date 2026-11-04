# Develop Light Comp

Generated light composited into the shot. Laid straight over a picture, the light that Stage Light, Laser, Glare,
Glow Plus and the light styles of Glow Dissolve draw can look like a sticker. This family blends and layers it. It
makes no new light: it takes the light those DCTLs already draw and places it in the plate as one real source seen
through the plate's own lens, film and air. A renderer like Time FX and Develop Depth (a DCTL sees one picture and no depth), run
on the GPU with torch. MIT License.

A sticker is light laid over the picture: in front of everything, sharper, cleaner, brighter and whiter than anything
the camera saw, lighting nothing. Each of those is answered:

| What the comp does | How |
|---|---|
| The light stands at a depth | `--at` is a depth (0 far, 1 near, the clip's own scale) or a point of the frame whose depth it takes, followed through the clip (`x,y`, or `x,y,shift`). `--ramp` adds depth toward the bottom of the frame, for a beam from a rig high and far landing on a floor nearer. What Resolve 21's depth pass puts nearer covers the light; holes of a few pixels in a cover are closed so a speck of wrong depth does not let the light blink through. |
| The depth is believed only where the picture has detail | The AI map invents depth over a featureless dark sky. Within a tenth of the frame's height of real detail the depth covers and receives light; over a featureless field it does neither. |
| The light is spread as the plate is at its depth | The plate's softness is measured by depth from its own edges (the re-blur ratio of Zhuo and Sim 2011, calibrated: sharp edges read 0.17 px, edges blurred by 1, 2 and 3 px read 0.98, 1.97, 2.96). Up to 1.5 px the light takes a Gaussian of that size; past it, the lens's aperture by Develop Depth's planes (`depthfx.defocus`, imported), its clipped cores opening into discs. `--defocus_px` sets it by hand. |
| The light lights the scene | Surfaces near the light in the frame and in depth are brightened by the light times their own colour (multiplied: black stays black, a dark trunk takes little, a white dog a lot). Four spreads, each wider one reaching further in depth, as light falls with distance. Faces of things in front of the light look away from it and take a tenth. `--spill`, `--reach`. |
| A rim on edges facing it | The near side of a real silhouette (a step in depth to what is behind it), on things at or in front of the light, brightest where the edge faces it. `--rim`. |
| The plate's tone | The light enters scaled between the plate's black floor and its white, and eases per channel into the plate's own clipped white (`--knee` of it), so no light is brighter or whiter than the plate's own highlights: under a cream-clipped sky a white core goes cream. |
| The plate's colour cast | The mean colour of the plate's lit middle tones, to the power `--cast` (0.35), tints the light. |
| The plate's grain | The plate's grain is measured by brightness (the residual of a 1 px blur in flat places), with its size (from its lag-one correlation) and colour correlation. Over what the light adds, new grain is laid at the strength the plate's grain has at the new brightness, minus what is already there, new each frame. Darkening by `--ambient` adds none. `--grain_amt`. |
| Air | The haze of the plate is read from the dark channel of its far scene against the air's own colour (He et al. 2009). In haze the light reaches the camera dimmed by the air between and the rest scattered round it wide. `--air` sets it by hand. |
| Off | `--gain 0` or amount 0 returns the plate exactly. |

Every mix is in linear light (Rec.709 gamma 2.4 display values in and out).

Lens lights (`kind lens`: a flare, a glare, a glow, orbs) happen in the lens, not the scene: they are not covered pixel
by pixel and light nothing, but they dim as their source is covered (the brightest place of the light, covered only by
what stands clearly nearer than `--at`), and take the plate's tone, cast, sensor softness and grain.

## The lights

The light layer is one of the installed DCTLs run through the CPU harness (`lightrun.mjs`, float output): over a black frame where the DCTL adds light and relights by multiplying, so
only the emitted light is left; as the DCTL over the plate minus the plate where the DCTL answers the plate's own
lights. Cached in `tests/out/lightcomp/layers`, about 25 MB a frame: delete it when you are done.

| Name | DCTL | Layer | Kind |
|---|---|---|---|
| `stage` | Develop Stage Light, Stage Light (beams on a rig through haze) | black | scene |
| `laser`, `zap_to`, `zap_from`, `flash` | Develop Laser, Laser Beam, Zap To, Zap From, Muzzle Flash | black | scene |
| `flare` | Develop Glow Dissolve, Lens Flare (Wash 0, progress by `--progress a,b`) | black | lens |
| `bulbs`, `zap` | Develop Glow Dissolve, Flashbulbs, Zap | black | scene |
| `glow_dis`, `orbs` | Develop Glow Dissolve, Glow, Orbs | diff | lens |
| `glare`, `streaks` | Develop Glare, Glare, Streaks | diff | lens |
| `glow` | Develop Glow Plus, Glow | diff | lens |

`--set slider=value` changes the DCTL's own sliders. Stage Light's Spotlight modes, Glow Plus's other modes and the
remaining Glow Dissolve styles are not listed; any DCTL can be named in `layers.layer` by path.

## Running one

    python -I apply.py <clip.mov> <out.mp4> --light <name> [--start s] [--frames n | --dur s]
        [--at 0.3 | --at x,y[,shift]] [--set slider=value ...] [--progress a,b] [--before b.mp4] [--sticker s.mp4]
        [--spill 1] [--rim 1] [--reach 1] [--occlude 0.03] [--ramp 0] [--defocus_px -1] [--cast 0.35]
        [--grain_amt 1] [--air -1] [--ambient 0] [--gain 1] [--knee 0.7] [--kind scene|lens] [--in s --out s]
    python -I apply.py --list

`<clip.mov>` is a path to a video file, or an `idx` number of a footage index CSV as in Develop Depth's `apply.py`.
Examples:

    python -I apply.py <night.mov> laser.mp4 --light laser --start 6 --frames 48 --at 0.3 --set lzHue=200 --gain 1.5
    python -I apply.py <forest.mov> beams.mp4 --light stage --start 1 --frames 48 --at 0.1 --ramp 0.25 --ambient -2 --gain 2.5
    python -I apply.py <night.mov> flare.mp4 --light flare --start 2 --frames 48 --at 0 --set gdCX=75.8 --set gdCY=34.7 --progress 0.44,0.56

The depth pass is found in `tests/out/depth/pass` for the clip and start, or given by `--depth`. A clip with no pass
needs one made by `effects/depth/depth_pass.py` (Resolve must be running).
The output is 1080p H.264, Rec.709 tagged, letterboxed as Resolve fits a clip, at the clip's own rate.
