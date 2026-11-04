# Develop Depth

Effects driven by depth: a lens's depth of field, focus pulled from one plane to another, air between the camera and the far scene, the scene's own lights glowing at a chosen depth, and a transition that peels a shot away from the camera outward. A DCTL sees one picture, so these are renderers like Time FX: the picture and its depth go in frame by frame, on the GPU with torch. MIT License.

The depth is DaVinci Resolve 21's own AI Depth Map (the Fusion DepthMap tool, Better mode, Deflicker on), rendered by `depth_pass.py` as a lossless 16-bit movie, near white. Each effect is built from what the real thing does: the aperture's shape spread over the points the lens does not focus, single scattering in air, a lens's glow round its lights.

Needs Python 3 with torch (CUDA when there is a GPU; the CPU works, slowly), numpy and OpenCV, ffmpeg on PATH, and DaVinci Resolve Studio 21 running for the depth pass. Set the environment variable `DEVELOP_PROJECT` to your project's name, and `depth_pass.py` refuses any other project.

## The effects

| Name | What it is |
|---|---|
| `defocus` | Depth of field. The blur radius at 1080 is `aperture_px` times the distance in depth from the focus plane; planes in front of focus spread `near_scale` times as much. The picture is cut into 23 planes by blur radius (neighbours a quarter apart, a pixel between two shared between them). Planes behind focus are blurred far to near, each normalised so it fills the parts of itself that nearer things cover; the backdrop starts as the far picture spread into the near planes' holes (push-pull), so a sharp subject keeps no dark rim and nothing behind a near object is black. Planes in front of focus spread over what is behind them. The point spread is the aperture: round, or `blades` straight blades rounded by `roundness`, turned by `rotation`, brighter toward the rim by `rim` (an over-corrected lens), an anamorphic oval by `squeeze`. Before the blur, only the part of the picture near clipping (above 0.6 linear) is lifted (`boost`), and pressed back after by the exact inverse, so a clipped light becomes a bright disc while white snow and sky stay what they are. |
| `zblur` | The same planes with a Gaussian spread and no lift: depth blur with no lens shape. |
| `rack` | `defocus` with its focus pulled from `--focus` to `--focus_to` over `--rack_dur` s from `--rack_at` s, eased. |
| `haze` | Air (Koschmieder single scattering): distance runs from `start` to the far plane, shaped by `curve`; transmission `exp(-3 density distance)` per channel, blue thinned faster (`blue`), so far planes go cool. The air's colour is the scene's own (the mean of its farthest 8%, half its saturation), so a night scene's air stays dark and a day scene's pale; `colour` and `brightness` set it by hand. The picture's lights glow through the air (`glow`, spread `glow_size` of the height). `linear` gives a straight fall from `start` to `end`. |
| `zglow` | The picture's own lights glowing where the depth says (`where` far, near or a band `at` a depth, `width` soft). A light is what passes a soft threshold; its glow is four widths, the wide ones weak, as a lens's falls off; `grow` widens the glow of far lights (seen through more air). |
| `depth_wipe` | A transition: the incoming shot shows first where the outgoing one is nearest (`far_first`: farthest), the border sweeping through depth with a soft edge (`soft`); the outgoing plane softens (`blur` px) just before it gives way, as a plane leaving focus. Exactly the outgoing shot at 0 and the incoming at 1, eased. |

`--focus` takes a depth (0.4), a point of the frame (`0.5,0.6`: the depth there, followed through the clip and smoothed so focus glides as a focus puller's does), or nothing for the middle of the frame. `--refine` (default 4 px) moves the AI map's edges onto the picture's edges with a guided filter before any effect. The depth is put on one scale for the whole clip (its nearest 0.5% to 1, its farthest 0.5% to 0); `--norm 0` turns that off.

## Running one

    python -I apply.py <clip.mov> <out.mp4> --fx <name> [--start s] [--dur s] [--depth pass.mov] [--in s] [--out s] [--<argument> value ...]
    python -I apply.py --list

`<clip.mov>` is a path to a video file. A number in its place reads that `idx` row of a footage index CSV (columns `idx`, `path`, `dur`); `ta_catalog()` in `apply.py` sets where that CSV is, and the environment variable `DEVELOP_MATERIAL_ROOT` moves its folder. Without `--depth` the pass is made by Resolve and kept in `tests/out/depth/pass/`. Examples:

    python -I apply.py <path.mov> path.mp4 --fx defocus --start 1 --dur 2 --aperture_px 30 --focus 0.5,0.75
    python -I apply.py <forest.mov> rack.mp4 --fx rack --start 1 --dur 3 --aperture_px 45 --focus 0.85 --focus_to 0.15 --rack_at 0.8
    python -I apply.py <lake.mov> lake.mp4 --fx haze --start 2 --dur 2 --density 0.8
    python -I apply.py <a.mov> wipe.mp4 --fx depth_wipe --start 1 --b <b.mov> --bstart 2 --wipe_dur 1.25

The output is 1080p H.264, Rec.709 tagged, at the clip's own rate, letterboxed as Resolve fits a clip (Time FX's writer); a letterboxed clip is processed inside its picture only, so the bars never bleed in.
