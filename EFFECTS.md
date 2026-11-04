# The effects

65 effects, transitions and grade nodes, 43 Fusion tools and 6 audio plugins. Each one runs inside DaVinci Resolve Studio. Install
them with `Install.bat`. Many folders hold one file with several modes: the first slider picks the mode, and its tooltip lists them.

| Part | Folder |
|---|---|
| Effects (DCTL) | `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT\Develop` |
| Fusion tools (Fuse) | `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Fuses\Develop` |
| Audio plugins (VST3) | `C:\Program Files\Common Files\VST3\Develop` |

## Use an effect by hand

- **On the Color page:** add a node, drag **DCTL** from the Effects library (ResolveFX Color) onto it, and pick a file from the
  `Develop` folder in its list. Its sliders appear under the effect.
- **On the Edit page:** drag **DCTL** onto a clip or an adjustment clip and pick the file the same way.
- **Transitions:** the files marked *transition* below go on a cut. Drag the **DCTL** transition onto the cut and pick the file.
- **In Fusion:** the Fuses appear in the tool list under their names (Develop Burn, Develop Glitch and the rest).

Claude can place effects and looks by script: see [looks/README.md](looks/README.md). Transitions need the drag by hand.

## Blend the effect into the shot

Most light effects (leaks, glows, lasers, stage light, particles, lightning) look best layered into the shot, not laid on top of it
at full strength. On the Color page, use the node's Key Output gain or a Layer Mixer node with a composite mode (Screen, Add or
Soft Light) and lower the opacity until the light belongs to the scene. Each effect's **Amount** or **Mix** slider does the same
inside the effect.

## The grade: Develop 1 Light and Develop 2 Color

Photo-style grading sliders and film light, in two nodes in a row.

- **Develop 1 Light:** white balance, exposure, tone, detail, highlight recovery, mist, veil, sparkle, halation, deband.
- **Develop 2 Color:** split toning, colour contrast, the colour mixer and skin, density, vibrance, saturation, vignette,
  highlight shoulder, path to white, gamut compression, black floor, grain.

Put Develop 1 Light first and Develop 2 Color right after it. Highlight Rolloff and Deband sit on both nodes: set the same value on
each.

The `Nodes` folder holds single-purpose nodes for a node tree: Bloom, Orton, Print, Night (day for night), Grain, Vignette, Matte,
Acutance and the streaks.

## The effect folders

| Folder | Effects | Kind |
|---|---|---|
| Art | Halftone, crosshatch, etching, sketch, cartoon, posterize, mosaic and more print and ink looks | effect |
| Beat | Glow, punch-in, shake, flash, lift, breathe and split on the beat of a song; a music visualizer | effect, tool |
| Blurdis | Blur Dissolve (camera blur and warp dissolves); Kaleido Polar | transition, effect |
| Damage | Film damage, grunge and flicker | effect |
| Diffusion | Diffusion filters and atmosphere: 13 kinds of glass, fabric, film and air | effect |
| Filmdis | Film Dissolve (film roll, TV roll, a dissolve that holds the highlights); Glitch Dissolve | transition |
| Fx | Glint, Glow FX, Kaleido, Rays, Zap (lightning and electric arcs) | effect |
| Glare | Glare (streaks, stars, ice halos); Glow Plus | effect |
| Glitch | Glitch (a transition) and Pixel Sort | transition, effect |
| Glowdis | Glow Dissolve (light dissolves) | transition |
| Grainmatch | Grain Match: the grain of a reference clip on another clip | effect |
| Lens | Bokeh and Lens (defocus, fisheye, edge stretch, shake, vignette) | effect |
| Light | Burn and Leak (film burn and light leaks); Light Dissolve | effect, transition |
| Move | Push (swish pans, whips, flutter cuts) | transition |
| Optics | Pastel, pencil, rainbow, soft light, star and flag looks | effect |
| Paint | Auto paint, brush, cartoon paint, watercolour, spray | effect |
| Particles | Dust, embers, sparks, snow, fireflies, light orbs; camera match | effect |
| Presets | Filter (31 camera filters from real transmission curves) and Texture | effect |
| Psych | Psychedelic looks: blobs, stripes, solarize, pseudo colour, prism | effect |
| Retro | CRT and VHS | effect |
| Screens | Screen (night vision, X-ray, LED, digital damage) and Emboss | effect |
| Sky | Aurora, night sky, moon, rain, snow, caustics, fog | effect |
| Stage | Stage Light and Laser (beams, arcs, muzzle flash) | effect |
| Stock | Film Stock (two-strip, three-strip, infrared, cross process, bleach bypass) and Process | effect |
| Strips | Strip Move (card pushes and wipes) and Strip Look | transition, effect |
| Texplus | Texture Plus (moire, spots, tiles, loops and more) | effect |
| Tones | Deband (smooths banding in skies) and Tritone Dissolve | effect, transition |
| Warp | Warp (defocus, vortex, waves, puddle, prism dissolves) | transition |

## Which effect for which job

Start with these. They read most like a real lens, film stock or camera move.

| Job | Effect |
|---|---|
| A film look | Film Stock, Process, Filter, Diffusion, and the Print and Bloom nodes in the grade |
| Day for night | The Night node (`looks/Day for Night.json`) |
| Clean skies after compression | Deband |
| Match grain between clips | Grain Match |
| A soft defocus or lens move | Bokeh, Lens |
| A cut with energy | Push, Film Dissolve, Warp |
| A real broken-video look | Glitch, Pixel Sort, VHS, CRT, Datamosh |
| A time effect | Time FX |

Use these only when the user asks, and at low strength. Generated light can look pasted on: Glare, Glow Plus, Sky, Zap, Laser,
Stage Light, Glow Dissolve, Texture Plus. For generated light placed into a scene by its depth, see `effects/lightcomp/README.md`.

## Speed on a faster timeline

16 moving effects count time as if the timeline runs at 24 fps. At 30 fps they run 1.25 times as fast, and at 60 fps 2.5 times. Lower
their speed or rate slider to match: Glint, Zap, Rays, Kaleido, Kaleido Polar, Diffusion, Glow Plus, Bokeh, Lens, Leak, Texture, Texture
Plus, Psych, Sky, Laser and Stage Light. The Datamosh tool always writes a 24 fps clip.

## The audio plugins (Fairlight)

Six VST3 plugins. In Fairlight, open a track's effects and look under VST.

| Plugin | What it does |
|---|---|
| Develop Tape | Tape saturation, wow and flutter, hiss |
| Develop Lo-fi | Vinyl, cassette, radio, telephone, old TV, intercom, through a wall, bitcrush and more |
| Develop Transient | Transient shaper: more or less attack and sustain |
| Develop Room | Rooms built from acoustics: cathedral, cave, small room, night forest, plate, spring |
| Develop Wash | A wash of reverb, with freeze |
| Develop Shimmer | Shimmer reverb |

Their noise (hiss, crackle, hum) follows the audio: where the track is silent, the plugin is silent.

## Shot tools (optional, need Python)

Some effects need to look at a whole shot or a song first, so they run as small tools outside Resolve:

- **Beat:** analyses a song and writes its beats into a Beat effect file.
- **Grain Match:** measures the grain of a reference clip and of your clip, and writes the settings.
- **Particles camera match:** measures the camera move of a shot so the particles move with the scene. It uses the Depth Anything
  V2 Small model (Apache-2.0, about 99 MB), downloaded once from Hugging Face.
- **Depth and Light Comp:** depth effects and generated light placed into the scene by its depth.
- **Time FX and Datamosh:** effects made of time, rendered as clips for your timeline.

Each tool's folder has a README with its command. They need Python and `requirements-shot-tools.txt`.
