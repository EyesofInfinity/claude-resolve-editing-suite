"""Python side of the CPU harness for Develop Grain Match. MIT License.
run(frames, params, first_frame) sends float frames through runframes.mjs and returns float frames."""
import json, os, shutil, subprocess, tempfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DCTL = os.path.join(HERE, "build", "Develop Grain Match.dctl")
RUN = os.path.join(HERE, "runframes.mjs")

def run(frames, params, first_frame=1, dctl=DCTL, threads=16):
    H, W, _ = frames[0].shape
    td = tempfile.mkdtemp(prefix="gm_")
    try:
        io = []
        for k, f in enumerate(frames):
            a, b = os.path.join(td, f"i{k}.rgb48"), os.path.join(td, f"o{k}.rgb48")
            np.clip(np.round(f.astype(np.float64) * 65535), 0, 65535).astype("<u2").tofile(a)
            io += [a, b]
        subprocess.run(["node", RUN, dctl, json.dumps(params), str(W), str(H), str(first_frame), *io,
                        "--threads", str(threads)], check=True, capture_output=True)
        return [np.fromfile(io[2 * k + 1], "<u2").reshape(H, W, 3).astype(np.float32) / 65535 for k in range(len(frames))]
    finally:
        shutil.rmtree(td, ignore_errors=True)
