"""Develop Particles on real footage through the CPU harness: frames, stills and labelled moving clips.

The DCTL runs on the CPU by prun.mjs (the same code Resolve runs), the frames split between node workers. With
--depth the depth pass (Resolve 21's Depth Map, rendered by effects/depth/depth_pass.py, near white) is put on one
scale for the clip as Develop Depth does and handed to Develop Particles Depth as its alpha.

usage:
  python -I render.py <clip or catalog idx> <out.mp4|out.png> [--start s] [--frames n] [--w 1280]
      [--depth pass.mov] [--set slider=value ...] [--label text] [--workers 16] [--crf 28] [--keep dir]
      [--dctl baked.dctl]   (a DCTL camera.py baked a shot's camera path into; set ptShotStart to the start's
                             timeline time, which is --start here: the frames are numbered from --start)

An out ending in .png writes the first frame only, at full size. The labels name what the frame shows. MIT License.
"""
import csv, json, os, shutil, subprocess, sys, tempfile, time

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import develop_paths

def arg(a, name, default):
    return a[a.index(name) + 1] if name in a else default

def clip(s):
    """A clip path, or the path of that row of the footage index (tools/develop_paths.py)."""
    return develop_paths.clip_from_index(s) if s.isdigit() else os.path.abspath(s)

def fps_of(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "default=nw=1:nk=1", path], capture_output=True, text=True, check=True).stdout.split()
    a, b = (r[0].split("/") + ["1"])[:2] if r else ("24", "1")
    return float(a) / float(b)

def read(path, start, n, W, H):
    """n consecutive frames from start, fitted into W x H as Resolve fits a clip (letterboxed)."""
    vf = (f"scale={W}:{H}:in_color_matrix=bt709:in_range=tv:force_original_aspect_ratio=decrease,"
          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2")
    p = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{start:.4f}", "-i", path, "-frames:v", str(n),
                        "-vf", vf, "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True, check=True)
    f = np.frombuffer(p.stdout, np.uint8).reshape(-1, H, W, 3)
    if len(f) < n:
        sys.exit(f"{path}: {len(f)} frames read, {n} wanted")
    return f

def depth(path, n, W, H, box):
    """The depth pass: n frames, near 1, one scale for the clip (its nearest 0.5% 1, its farthest 0.5% 0, inside
    the picture's rows), resized to W x H."""
    p = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", path, "-frames:v", str(n), "-pix_fmt", "rgb48le",
                        "-f", "rawvideo", "-"], capture_output=True, check=True)
    d = np.frombuffer(p.stdout, np.uint16).reshape(-1, 1080, 1920, 3)[..., 0].astype(np.float32) / 65535.0
    if len(d) < n:
        sys.exit(f"{path}: {len(d)} depth frames, {n} wanted")
    y0, y1 = (int(box[0] * 1080 / H), int(box[1] * 1080 / H))
    v = d[:, y0:y1:4, ::4].ravel()
    lo, hi = np.percentile(v, 0.5), np.percentile(v, 99.5)
    d = np.clip((d - lo) / max(1e-4, hi - lo), 0, 1)
    return np.stack([cv2.resize(k, (W, H), interpolation=cv2.INTER_AREA) for k in d])

def content_box(frames):
    m = frames[::max(1, len(frames) // 8)].max(axis=(0, 2, 3))
    rows = np.nonzero(m > 3)[0]
    return (int(rows[0]), int(rows[-1]) + 1) if len(rows) else (0, frames.shape[1])

def run(frames, dctl, params, frame0, d=None, workers=16, keep=None):
    n, H, W = frames.shape[:3]
    work = keep or tempfile.mkdtemp(prefix="ptc_")
    os.makedirs(work, exist_ok=True)
    for i, f in enumerate(frames):
        f.tofile(os.path.join(work, f"a_{i:04d}.rgb"))
        if d is not None:
            np.round(d[i] * 65535).astype("<u2").tofile(os.path.join(work, f"d_{i:04d}.u16"))
    dfl = ["depth"] if d is not None else []
    base = ["node", os.path.join(HERE, "prun.mjs"), dctl, json.dumps(params), work, str(W), str(H), str(frame0)]
    if n >= workers:
        cuts = [round(j * n / workers) for j in range(workers + 1)]
        procs = [subprocess.Popen(base + [str(cuts[j]), str(cuts[j + 1])] + dfl)
                 for j in range(workers) if cuts[j + 1] > cuts[j]]
        bands = None
    else:
        per = max(1, workers // n)
        bands = [round(j * H / per) for j in range(per + 1)]
        procs = [subprocess.Popen(base + [str(i), str(i + 1)] + dfl + [f"rows={bands[j]}:{bands[j + 1]}"])
                 for i in range(n) for j in range(per)]
    for p in procs:
        if p.wait():
            sys.exit("a worker failed")
    if bands is None:
        out = np.stack([np.fromfile(os.path.join(work, f"o_{i:04d}.rgb"), np.uint8).reshape(H, W, 3) for i in range(n)])
    else:
        out = np.stack([np.concatenate([np.fromfile(os.path.join(work, f"o_{i:04d}_r{bands[j]}.rgb"), np.uint8)
                                        .reshape(bands[j + 1] - bands[j], W, 3) for j in range(len(bands) - 1)])
                        for i in range(n)])
    if not keep:
        shutil.rmtree(work, ignore_errors=True)
    return out

def label(img, text, size=None):
    """The label in the frame's top left, on a dark band, naming what the frame shows."""
    im = Image.fromarray(img)
    H = img.shape[0]
    font = ImageFont.truetype("arialbd.ttf", size or max(14, H // 34))
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = d.textbbox((0, 0), text, font=font)
    pad = H // 90 + 4
    d.rectangle((0, 0, x1 + 2 * pad, y1 + 2 * pad), fill=(0, 0, 0))
    d.text((pad, pad - y0 // 2), text, fill=(235, 235, 235), font=font)
    return np.asarray(im)

def write(frames, path, fps, crf):
    H, W = frames.shape[1:3]
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                          f"{W}x{H}", "-r", f"{fps:.6f}", "-i", "-", "-vf",
                          "scale=out_color_matrix=bt709:out_range=tv,setparams=color_primaries=bt709:color_trc=bt709:"
                          "colorspace=bt709:range=tv", "-c:v", "libx264", "-crf", str(crf), "-preset", "slow",
                          "-pix_fmt", "yuv420p", "-movflags", "+faststart", path], stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(np.ascontiguousarray(f).tobytes())
    p.stdin.close()
    if p.wait():
        sys.exit(f"ffmpeg failed writing {path}")

def main():
    a = sys.argv[1:]
    src, out = clip(a[0]), os.path.abspath(a[1])
    start, n = float(arg(a, "--start", "1")), int(arg(a, "--frames", "48"))
    W = int(arg(a, "--w", "1280"))
    H = W * 9 // 16
    still = out.lower().endswith(".png")
    if still:
        n = 1
    fps = fps_of(src)
    params = {"ptFps": round(fps, 3)}
    for s in [a[i + 1] for i, v in enumerate(a) if v == "--set"]:
        k, v = s.split("=")
        params[k] = float(v)
    dp = arg(a, "--depth", None)
    t0 = time.time()
    frames = read(src, start, n, W, H)
    d = depth(dp, n, W, H, content_box(frames)) if dp else None
    dctl = arg(a, "--dctl", None) or os.path.join(HERE, "build", "Develop Particles Depth.dctl" if dp else "Develop Particles.dctl")
    o = run(frames, dctl, params, int(round(start * fps)), d, int(arg(a, "--workers", "16")), arg(a, "--keep", None))
    lab = arg(a, "--label", None)
    if lab:
        o = np.stack([label(f, lab) for f in o])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if still:
        Image.fromarray(o[0]).save(out)
        Image.fromarray(frames[0]).save(out[:-4] + "_src.png")
    else:
        write(o, out, fps, int(arg(a, "--crf", "28")))
    print(f"{out}: {n} frames {W}x{H} in {time.time() - t0:.1f} s", flush=True)

if __name__ == "__main__":
    main()
