# Develop Particles

Real things floating in the shot's air: dust in light, embers and ash rising from a fire, sparks, snow, fireflies and soft light orbs. Two transform DCTLs from one shared engine (`particles.h`). MIT License. Free, for DaVinci Resolve on Windows: Edit page OpenFX > ResolveFX Color > DCTL, or a DCTL node on the Color page.

- **Develop Particles**: the plain DCTL. It needs nothing but the picture.
- **Develop Particles Depth**: the same, with a depth map in the node's alpha (Resolve 21's Depth Map, near white). Particles hide behind anything nearer than they are, and Focus is read on the map's own scale. Depth In 0 makes it Develop Particles exactly.
- **A camera match for a moving shot**: `camera.py` reads one shot, measures how its camera moves and writes a copy of both DCTLs with that move baked in, so the particles travel with the scene as the camera pans, trucks or walks. See "The camera match" below.

Six looks, built from what the real things are. Our own code.

## The styles

| Style | What it is | Built from |
|---|---|---|
| 0 Dust | Motes drifting in light, seen only where the air is lit, glinting as they turn | A mote scatters the light it floats in, mostly forward. The air counts as lit where the picture within 30 px is bright; clipped highlights within 90 px (looking toward a light) make the motes far brighter. Each mote has its own size and a tumbling glint. |
| 1 Embers | Embers rising from a fire below (Source X, Source Y, Spread its width), flickering, cooling as they climb and burning out; grey ash carried up with them | Each ember is a black body: born at 1200 to 1600 K, cooling with the height it has risen, its colour from Planck's law at 610, 550 and 465 nm, its brightness rising steeply with heat. Each layer rises along its own heading (up to 26 degrees off vertical), each column of cells at its own speed, each ember swinging on its own. One in eight is ash, lit like a grey thing. |
| 2 Sparks | Sparks thrown from Source along Direction within Spread: fast streaks under gravity and air drag, white-yellow at birth, orange to red as they cool, gone in under a second | Each spark is a projectile with linear drag, drawn as the curve the shutter swept (two segments, the older half hotter). Some are thrown together in bursts; with a floor they land and bounce once, slowed and cooler. A hot point at the source flickers and flares on each burst. |
| 3 Snow | Flakes falling in depth, lit by the light round them; near flakes large, soft and faint | A flake is a white thing: as bright as the light a white surface gets there (about six times the surroundings' mean, never brighter than the brightest thing near), composited so it covers what is behind. A dense far layer blurred past what its cells can hold becomes an even veil. |
| 4 Fireflies | Cold yellow-green lights that flash and go dark, low over the ground | A flash of about a third of a second every 1.8 to 5 s, some with a second flash; a lens glow round each. |
| 5 Orbs | Soft steady lights drifting, breathing slowly | A small hot core in a ball of light and a halo of lit air (most of its light in the halo), each halo its own width and strength. |

## The sliders

| Slider | What it does |
|---|---|
| Particles | How much of the effect. 0 gives the picture back exactly. |
| Style | 0 Dust, 1 Embers, 2 Sparks, 3 Snow, 4 Fireflies, 5 Orbs. |
| Density | How many particles. |
| Size | How big each particle is. |
| Speed | How fast they move. It also sets how often fireflies flash and how often sparks burst. |
| Wind | A sideways push: positive to the right, negative to the left. |
| Direction | Sparks: the throw, in degrees from straight up (positive to the right, 180 straight down). |
| Source X, Source Y | Sparks: where they come from. Embers: the middle of the fire and the line they start rising from. Percent of the width and height (Source Y 100 is the bottom edge; past 100 is below the frame). With a baked camera path these are read on the shot's first frame. |
| Spread | Sparks: the width of the throw. Embers: the width of the fire. |
| Depth | How far away the cloud of particles sits. 50 is each style's own; lower is farther, higher nearer. |
| Depth Spread | How deep the cloud is. 50 is the style's own; 0 puts every particle on one plane. |
| Focus | The distance in focus: 0 infinity, 100 the nearest thing in the shot, past 100 nearer the lens. |
| Blur | The lens: how much particles away from Focus spread into soft discs. 0 keeps every particle sharp. |
| Shutter | Shutter angle in degrees. 180 is a normal film shutter; 0 is no motion blur; 360 the longest streaks. |
| Frame Rate | Set it to the timeline's frame rate, so speeds and motion blur are true. A baked DCTL starts at the shot's own rate. |
| Colour | Dust and Snow: a warm or cool tint. Embers and Sparks: hotter or cooler. Fireflies and Orbs: their hue. |
| Scene Light | 100 lets the shot's own light decide: dust shows only in light, snow and ash are as bright as their surroundings, glowing particles are dimmer in a bright shot. 0 ignores the picture's light. |
| Camera Pan, Camera Tilt | Match a camera move by hand when no path is baked: the particles slide sideways or up and down, near ones more than far ones. Leave them at 0 with a baked path. |
| Seed | A different arrangement of the same look. |
| Scene Glow | Embers, sparks, fireflies and orbs light the picture round them. 50 is natural, 0 is none, 100 is twice natural. The light falls on what is there: a lit trunk or rock brightens, black sky and empty shadow stay dark. With the Depth version, a surface far behind a particle gets less of its light. |
| Source Glow | Sparks: the hot point they leave from (a grinder's bite, a log's split), flickering and flaring on each burst, lighting the scene round it. Set it to 0 when a real fire, grinder or strike is already in the shot. |
| Bursts | Sparks: the share thrown together in bursts, as when a log pops or a grinder bites. 0 is a steady stream; 100 is bursts only, with quiet between. |
| Floor Y | Sparks: the floor they land on and bounce off once, in percent of the height (100 the bottom edge). It must sit below Source Y. 140 and over: no floor, the sparks fall out of the frame. |
| Camera Match | With a camera path baked by `camera.py`: how much the particles move with the scene. 100 fully, 0 locked to the screen. It does nothing in a DCTL with no path baked. |
| Shot Start s | With a camera path baked: where the shot's analysed first frame sits on the timeline, in seconds from the timeline's first frame. |
| Depth In | Develop Particles Depth only: how much the depth map is believed. 0 is Develop Particles exactly. |

Speed, Shutter, Wind and Camera Pan set the cell size of each layer. Keyframing them reshuffles the particles; keyframe Density, Focus, Blur and Colour instead.

## How each particle sits in the shot

- **Depth.** Every particle has a disparity q (1 is the nearest thing in the shot as Develop Depth's pass scales it, 0 is infinity, up to 1.6 between that thing and the lens). Its screen size, spacing and speed scale with q, as perspective does; its light falls as q squared. Depth and Depth Spread set where the cloud is and how deep it is (50 is each style's own).
- **The lens.** A thin lens spreads a particle over a disc of radius Blur x |q - Focus|. A glowing particle out of focus is the lens's own disc: a rim a little brighter than the middle, faint onion rings, a mottled inside, a soft coloured fringe by the side of focus, and toward the frame's corners a cat's eye (a fast lens wide open clips its discs). The disc carries the light the sharp spot did, so a particle neither dims nor brightens as it goes out of focus. Small spots are a Gaussian no sharper than the plate (0.75 px at 1080).
- **The shutter.** A moving particle is the disc swept along its path for the shutter's time (Shutter angle, Frame Rate): the streak's ends fade over the disc's width, as a moving out-of-focus light does on film. With a baked camera path the camera's own move streaks the particles too.
- **Light.** Light is added in linear (Rec.709 gamma 2.4 in and out) and rolled off into white through the house shoulder (`light.h`). Glowing styles take the shot's exposure (Scene Light 100): they are dimmer in a bright shot, brighter at night, as a camera exposed for the scene would show them. Scene Glow adds the light they throw on the scene: irradiance from a point a little off the surface, reflected by what the picture shows is there.
- **Grain.** The plate's grain (the pixel's difference from its four neighbours) is carried onto what is added, new each frame.
- **Depth pass.** With Develop Particles Depth, a particle is drawn only where it is nearer than the depth map says the scene is, decided per pixel, so a soft near flake is cut by the sharp edge of a trunk behind which it falls.
- **No state.** Every particle is a pure function of its cell, the seed and the time (hash-seeded), so any frame renders on its own and scrubbing works. Particles 0 gives the picture back exactly. A pixel no particle reaches comes back exactly (at Scene Glow 0; with Scene Glow the light on the scene reaches further). A letterbox bar (a black row in the top or bottom 13% of the frame) is left black.

## The camera match

On a moving shot, particles locked to the screen give the effect away: the trunks slide past and the snow does not. `camera.py` measures the shot's camera and bakes it into a copy of both DCTLs for that shot.

    python -I effects/particles/camera.py <clip> <out folder> --start <s> --dur <s> --name <name>

It writes `Develop Particles - <name>.dctl`, `Develop Particles Depth - <name>.dctl` and `<name>.camera.json` (the path, how well it fits, what it cost). Install the two DCTLs as any other (they work on their own), put one on the shot, then:

1. Set **Shot Start s** to where the analysed first frame (the clip's time `--start`) sits on the timeline, in seconds from the timeline's first frame.
2. Set **Frame Rate** to the timeline's rate. The path is stored in seconds, so it plays on any rate.
3. Leave Camera Pan and Camera Tilt at 0. Use **Camera Match** to blend between locked (0) and matched (100).

How it measures. Each pair of frames gets dense optical flow (OpenCV DIS), checked forward against backward, kept where the picture has texture. Each frame gets a depth map from Depth Anything V2 Small on the GPU. A camera that turns and moves is fitted to the flow, robustly (fire, water and walking people are thrown out): a pan, tilt, zoom or roll moves everything alike; a truck, crane or dolly moves near things more than far ones. A depth curve fitted from the motion corrects the depth map's scale. The path is baked at three depths and the DCTL reads it per layer, so near particles slide more than far ones, as the scene's own points at their depth do. With a flat or featureless scene every layer moves with the picture.

What it needs: Python 3 with numpy, opencv-python and Pillow; ffmpeg and ffprobe on the PATH; for the depth part, PyTorch and Hugging Face transformers and the model's weights (below). `--no-depth` skips the depth part: every layer then moves with the picture's own motion, with no parallax.

Limits:
- One shot a bake. Before the analysed range the path holds its first frame, after it its last.
- The shot is analysed as Resolve fits it to a 16:9 frame. If the clip is scaled, moved, stabilised, retimed or speed-ramped on the timeline, the path no longer matches.
- The path table holds up to 14000 values (the 64 KB a GPU's constant memory holds). A shot over about 55 s at 25 fps is sampled every second or third frame.
- The depth from the network is relative, so parallax is matched in proportion, not in metres.

### The depth weights

`camera.py` loads Depth Anything V2 Small from the local Hugging Face cache only (`depth-anything/Depth-Anything-V2-Small-hf`, offline, it never downloads). The weights are not in this repo. Fetch them once before the first run, for example `hf download depth-anything/Depth-Anything-V2-Small-hf` (about 99 MB). Read the model card's licence before you use them: the Small model is published as Apache-2.0, and the Base, Large and Giant V2 models are CC-BY-NC-4.0 (non-commercial), so only Small is used here.

## The depth input (not proven live)

Develop Particles Depth reads the alpha (`p_TexA`, the transform form with alpha that Resolve's DCTL readme gives since 19.1). How Resolve 21 hands a node's alpha to a DCTL, and how to route the Depth Map into it, has not been tested in Resolve. If the alpha form needs a `DEFINE_DCTL_ALPHA_MODE_STRAIGHT` line, add it above the sliders. Offline, `render.py --depth <pass.mov>` feeds Develop Depth's pass (effects/depth/depth_pass.py) as the alpha, put on one scale for the clip as Develop Depth does.

## Known limits

- Dust: the lit air is guessed from the picture's brightness near each mote, so motes can show beside bright surfaces outside any beam. In bright daylight dust is faint to invisible at 1:1.
- Embers: each streak is straight within one frame and one brightness along its length. By day they are almost invisible and the ash is barely seen.
- Snow: flakes are round discs. Far snow under heavy defocus becomes a veil. On busy white branches the flakes disappear.
- Orbs have no real-world reference: they are a fantasy element.
- Grain on the added light is a rough match: an edge also raises it.
- A moving particle's swept disc carries 8 to 28% more light than a still one, so a particle brightens a little as it starts to move.
