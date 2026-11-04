"""Run any Develop Time FX effect on a clip and write a 1080p H.264 file.

usage: python -I apply.py <in.mp4> <out.mp4> --fx <name> [options] [--<param> <value> ...]
  --fx           feedback, feedback_bubble, feedback_distort, time_displace, trails, trails_diffuse, time_average,
                 random_edits, reverse_edits, get_frame, looper, posterize_time, jitter_basic, jitter, morph
  --start, --dur seconds into the clip and how long (default: the whole clip)
  --strength     the effect's env (default 1); --in and --out ease it in and out over that many seconds
  --link j.json the env rides the soundtrack: j.json from effects/audio/link/analyse.py at the output rate,
  --drive spec   feature[:lo:hi:gamma:offset], e.g. onset:0.2:1 (default rms)
  --fit          pad (default: letterboxed as Resolve fits a clip) or crop (filled)
  --fps          the output rate (default: the clip's own; frames are read consecutively either way)
  --crf          H.264 quality (default 14)
  morph only:    --b <second clip> --bstart <s>; the morph runs over --dur, with --pre seconds of the first clip
                 before it and --post seconds of the second after it
  --<param>      any argument of the function (see timefx.py), e.g. --zoom 1.03 --matte ramp --depth 20
                 --rise 0,-3 --seg 6,14 --sweep true. Tuples are comma lists.
  --list         print every effect's arguments and defaults
No audio is written. The file is Rec.709, tagged. Prints a JSON summary.
"""
import inspect, json, os, subprocess, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import timefx as tf

W, H = 1920, 1080
OWN = {"--fx", "--start", "--dur", "--strength", "--in", "--out", "--fit", "--fps", "--crf", "--b", "--bstart",
       "--link", "--drive",
       "--pre", "--post"}

def probe_fps(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "default=nw=1:nk=1", path], capture_output=True, text=True, check=True).stdout.split()
    r = r[0] if r else "24/1"
    a, b = r.split("/") if "/" in r else (r, "1")
    return float(a) / float(b)

def read(path, start, dur, fit, count=0):
    """Consecutive frames from start: for dur seconds, or count frames when given (the whole clip if neither)."""
    vf = (f"scale={W}:{H}:in_color_matrix=bt709:in_range=tv:force_original_aspect_ratio=increase,crop={W}:{H}"
          if fit == "crop" else
          f"scale={W}:{H}:in_color_matrix=bt709:in_range=tv:force_original_aspect_ratio=decrease,"
          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2")
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{start:.4f}", "-i", path]
    if count:
        cmd += ["-frames:v", str(count)]
    elif dur:
        cmd += ["-t", f"{dur:.4f}"]
    cmd += ["-vf", vf, "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    frames, size = [], W * H * 3
    while True:
        b = p.stdout.read(size)
        if len(b) < size:
            break
        frames.append(np.frombuffer(b, np.uint8).reshape(H, W, 3).copy())
    p.wait()
    if not frames:
        sys.exit(f"no frames read from {path}")
    return frames

def write(frames, path, fps, crf):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                          f"{W}x{H}", "-r", f"{fps:.6f}", "-i", "-", "-vf",
                          "scale=out_color_matrix=bt709:out_range=tv,setparams=color_primaries=bt709:color_trc=bt709:"
                          "colorspace=bt709:range=tv", "-colorspace", "bt709", "-color_primaries", "bt709",
                          "-color_trc", "bt709", "-color_range", "tv", "-c:v", "libx264", "-crf", str(crf),
                          "-pix_fmt", "yuv420p", "-movflags", "+faststart", path], stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(np.ascontiguousarray(f).tobytes())
    p.stdin.close()
    if p.wait():
        sys.exit(f"ffmpeg failed writing {path}")

def cast(text, default):
    t = text.strip()
    if isinstance(default, bool):
        return t.lower() in ("1", "true", "yes", "on")
    if isinstance(default, tuple):
        kind = type(default[0]) if default else float
        return tuple(kind(float(v)) if kind is int else kind(v) for v in t.split(","))
    if isinstance(default, int):
        return int(float(t))
    if isinstance(default, float):
        return float(t)
    if default is None:
        if "," in t:
            return tuple(float(v) for v in t.split(","))
        try:
            return float(t)
        except ValueError:
            return t
    return t

def main():
    a = sys.argv[1:]
    if "--list" in a:
        for name, fn in tf.FX.items():
            ps = [f"{k}={v.default!r}" for k, v in inspect.signature(fn).parameters.items()
                  if k not in ("frames", "A", "B")]
            print(f"{name}: " + ", ".join(ps))
        return
    if len(a) < 4 or "--fx" not in a:
        sys.exit(__doc__)
    src, out = a[0], a[1]
    opts = {}
    k = 2
    while k < len(a):
        if not a[k].startswith("--") or k + 1 >= len(a):
            sys.exit(f"cannot read the option at {a[k]!r}")
        opts[a[k]] = a[k + 1]
        k += 2
    name = opts["--fx"]
    if name not in tf.FX:
        sys.exit(f"--fx {name}: one of {', '.join(tf.FX)}")
    fn = tf.FX[name]
    sig = inspect.signature(fn).parameters
    fit = opts.get("--fit", "pad")
    start, dur = float(opts.get("--start", 0)), float(opts.get("--dur", 0))
    fps_in = probe_fps(src)
    fps = float(opts.get("--fps", fps_in))
    kw = {}
    for key, val in opts.items():
        if key in OWN:
            continue
        p = key[2:]
        if p not in sig:
            sys.exit(f"{name} has no argument {p!r}; it takes: {', '.join(k for k in sig if k not in ('frames', 'A', 'B'))}")
        kw[p] = cast(val, sig[p].default)
    t0 = time.time()
    if name == "morph":
        if "--b" not in opts:
            sys.exit("morph needs --b <second clip>")
        dur = dur or 1.25
        pre, post = float(opts.get("--pre", 0)), float(opts.get("--post", 0))
        n, npre, npost = (int(round(x * fps)) for x in (dur, min(pre, start), post))
        A = read(src, start - npre / fps_in, 0, fit, npre + n)
        B = read(opts["--b"], float(opts.get("--bstart", 0)), 0, fit, n + npost)
        n = min(len(A) - npre, len(B))
        frames = A[:npre] + fn(A[npre:npre + n], B[:n], **kw) + B[n:]
    else:
        frames = read(src, start, dur, fit)
        if len(frames) > 900:
            print(f"note: {len(frames)} frames held in memory ({len(frames) * W * H * 3 / 1e9:.1f} GB)", file=sys.stderr)
        n = len(frames)
        if "env" in sig and "env" not in kw:
            s = float(opts.get("--strength", 1.0))
            r, f = float(opts.get("--in", 0)) * fps_in, float(opts.get("--out", 0)) * fps_in
            kw["env"] = tf.ramp_env(n, int(round(r)), int(round(f)), s) if (r or f) else s
            if "--link" in opts:
                sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio", "link"))
                import analyse as al
                kw["env"] = np.asarray(kw["env"], dtype=np.float64) * al.drive(opts["--link"],
                                                                                opts.get("--drive", "rms"), n)
        frames = fn(frames, **kw)
    write(frames, out, fps, int(opts.get("--crf", 14)))
    shown = {k: (v if not isinstance(v, np.ndarray) else "per-frame") for k, v in kw.items()}
    print(json.dumps({"out": out, "fx": name, "frames": len(frames), "fps": round(fps, 3), "fit": fit,
                      "params": shown, "seconds": round(time.time() - t0, 1)}, default=str))

if __name__ == "__main__":
    main()
