# Develop Datamosh

A true datamosh across a cut, rendered as a ProRes clip for the cut. The incoming shot's motion carries the outgoing shot's last picture until the incoming shot's own detail bleeds through. MIT License.

Needs Python 3 with numpy, opencv-python (5.0 tested) and PyAV (19 tested), and ffmpeg on PATH.

    python -I datamosh.py <A.mp4> <A last frame, s> <B.mp4> <B first frame, s> <out.mov> [options]

| Option | Meaning |
|---|---|
| `--engine codec` (default) | The classic method done for real: MPEG-4 Part 2, no B-frames, no scene cut detection, a keyframe forced at the cut and then deleted before decoding. `--q` sets the quantiser (4; higher is blockier). |
| `--engine flow` | A model you can steer: OpenCV DIS flow on the incoming shot, averaged per `--block` px, moves the held picture; `--bleed` (0.15) adds the incoming shot's own prediction residual as a decoder does; `--refresh` repaints that share of blocks each frame. |
| `--bloom k:m` | Both engines: the k-th incoming frame's motion sent m times (the bloom mosh). |
| `--dither` | 0 to 100, default 85: the moshed frames crushed through an 8 x 8 Bayer dither in 2 px cells at 1080, easing to 60% of that over the mosh. |
| `--frames`, `--pre` | Mosh frames (24) and frames of A kept before the cut (0). |
| `--preview out.mp4` | An H.264 copy to watch. |

Not a DCTL: a DCTL sees one frame (and a transition two), and a mosh needs every frame of the incoming shot up to the current one. A Fusion version (a Fuse reading neighbouring frames) would put it in Resolve's effects list; for now it ships as a renderer.
