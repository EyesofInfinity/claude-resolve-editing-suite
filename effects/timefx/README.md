# Develop Time FX

Effects made of time: feedback loops, time displacement by a matte, trails, time averaging, edits in time, jitter and a morph between two clips. A DCTL sees one frame, so these are Python renderers over runs of frames, as the time glitches (`effects/time/timeglitch.py`) and the datamosh (`effects/mosh/datamosh.py`) are. Each look is built from the real thing: a camera pointed at its own monitor, a glass ball, a slit-scan camera, a long exposure, smoke. MIT License.

Needs Python 3 with numpy and OpenCV (5.0 tested), Pillow for the review renders, and ffmpeg on PATH.

## The effects

Every function takes a list of HxWx3 uint8 Rec.709 frames and returns a new list. `env` (one number or one value per frame) scales the effect, so it can rise and fall over a window; at 0 the input frame comes back exactly. Light-like mixes are done in linear light (gamma 2.4).

| Function | What it is |
|---|---|
| `feedback` | The output fed back each frame, zoomed and turned about a centre, softened, and screened over the live picture. Each trip round the loop sinks the dim parts (gamma 1.35) and pushes the colour (chroma 1.06), as a camera pointed at its monitor does, so old echoes fall to colour and black rather than a grey veil. Hue can turn each pass. |
| `feedback_bubble` | The loop seen through a glass ball: the live picture refracted by the ball (magnified at its middle, pressed toward its rim, the rim darkened), the output fed back through the ball and shrunk each pass, so the ball holds smaller balls receding into it. Mixed, so nothing lifts. |
| `feedback_distort` | The loop pushed each pass through a smooth noise field that drifts, so older echoes curl further, like a picture through rising heat. |
| `time_displace` | Each pixel taken from a frame offset in time by a matte: the picture's own luma, a ramp (slit-scan), a radial, any array or a function. Fractional offsets mix the two neighbouring frames in linear light, so a smooth matte gives a smooth picture with no steps. |
| `trails` | Echoes of earlier frames by lighten, screen or average, each darker by decay; a key (`key`, `pop`, `thin`) keeps only the lights. `sweep` draws each point light along its whole path between frames by optical flow (DIS), so a firefly leaves one continuous streak as on a long exposure, not a row of beads. Offset, hue and blur per echo. |
| `trails_diffuse` | Trails that drift, swirl and blur as they fade, like smoke rising off the bright parts. The defaults suit a fire's glow; `sweep` with a faster drift suits small lights. |
| `time_average` | A window of frames mixed in linear light: mean (water to silk) or max (everything bright that passed stays lit); with a light key and max, light painting with each light swept along its path. The window grows by fractions, never a step. |
| `random_edits` | The clip cut into short pieces, each replaced (with the chance env) by a piece from elsewhere in the clip. |
| `reverse_edits` | The clip cut into short pieces, each played backwards in place (with the chance env). |
| `get_frame` | A frame from another moment (a fixed frame, or a fractional offset) mixed over the live picture by env. |
| `looper` | A section looped for the clip's length, its last frames crossfaded toward the frames before its start so the jump back continues the motion; or played forward and back. |
| `posterize_time` | The clip held to one new frame every step frames (fractional steps alternate holds); `shutter` makes each held frame the mean of the frames it stands for, which reads as low-rate film with motion blur rather than a stutter. |
| `jitter_basic` | Each frame swapped for one up to amount frames away. |
| `jitter` | Held, fractional time jitter (interpolated in linear light), with a gate-weave shake of the frame scaled just enough to keep the edges covered. |
| `morph` | Two runs of frames (both moving) morphed: optical flow both ways (DIS or Farneback), held to 12% of the height and smoothed, each clip pushed toward the other and the two crossfaded on an eased progress. The first frame is A's own and the last is B's own. |

`light_mask(frame, key, pop, thin, alone)` says what counts as a light: `key` by brightness; `pop` for small points brighter than the ring 3 to 7 px round them (fireflies: 0.45; a sky gap among twigs shares its ring with more sky and does not count); `thin` for points and thin streaks under 7 px across (sparks, not the flame they fly from); `alone` for points brighter than the brightest pixel of that ring (fireflies: 0.3; a glint where a dark trunk meets the sky has sky as bright beside it and fails).

With `sweep`, `trails`, `trails_diffuse` and `time_average` also take a motion key: `move` (px at 1080) with `persist` (frames, default 3). Each light is tracked as a blob. The camera's local motion (the median DIS flow in a window about 160 px wide) says where the scene under the light goes next frame, and the nearest light there is the same light. A light is kept when its drift from the scene over `persist` frames is above `move` (faded in over 1.5 px), when it is found in every one of those frames, and when its drift changes smoothly (a glint on an edge sits with the scene and then jumps to the next glint along the edge). A kept light stays kept for 3 more frames while it is still tracked, so a firefly that fails a test for one frame leaves no gap. Each kept light is swept along its own tracked motion. The firefly runs use `pop 0.45, alone 0.3, move 2, persist 3`.

The two jitters are time jitter: the full one with held fractional offsets and a frame shake. Resolve already does Trails, Motion Trails, Smear, Stop Motion, Frame Average and Seamless Loop; the ones here that overlap them add what they lack: light-keyed and swept trails, the linear-light mean with a window that grows smoothly, the shutter on the posterize, the crossfaded loop seam.

## Running one on a clip

    python -I apply.py <in.mp4> <out.mp4> --fx <name> [--start s] [--dur s] [--strength 1] [--in s] [--out s] [--<argument> value ...]
    python -I apply.py --list

`--in` and `--out` ease the effect in and out over that many seconds. Any argument of the function can be given (`--zoom 1.03`, `--matte ramp`, `--rise 0,-3`, `--sweep true`). Morph: `--b <second clip> --bstart s`, with `--pre` and `--post` seconds of clean picture around it. The file is 1080p H.264, Rec.709 tagged, at the clip's own rate, letterboxed as Resolve fits a clip (`--fit crop` to fill); no audio. Examples:

    python -I apply.py fireflies.mp4 trails.mp4 --fx trails --sweep true --pop 0.45 --alone 0.3 --move 2 --decay 0.85 --in 0.3
    python -I apply.py waves.mp4 slit.mp4 --fx time_displace --matte ramp --depth 24
    python -I apply.py fire.mp4 smoke.mp4 --fx trails_diffuse --dur 3
    python -I apply.py falls.mp4 morph.mp4 --fx morph --start 3 --dur 1.25 --b falls2.mp4 --bstart 3 --pre 1 --post 1
