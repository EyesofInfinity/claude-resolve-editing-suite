"""Develop Datamosh: a true datamosh across a cut, rendered as a clip for the cut. The incoming shot's MOTION carries the outgoing shot's last picture: its pixels are
dragged along the incoming shot's movement until the incoming shot's own detail bleeds through.

Two engines:
  codec  the classic method, done for real: both shots encoded as one MPEG-4 Part 2 stream (no B-frames, no scene
         cut detection, a keyframe at the cut), the cut's keyframe deleted, the stream decoded. Every P-frame of the
         incoming shot then predicts from the outgoing shot's picture. --bloom k:m sends the k-th incoming P-frame
         m times (one motion repeated, the "bloom" mosh). --q sets the quantiser (higher is blockier).
  flow   a controllable model of the same: optical flow measured between the incoming shot's frames (OpenCV DIS),
         averaged per macroblock, moves the held picture each frame, and the incoming shot's own prediction residual
         is added (as the decoder adds it) scaled by --bleed; --refresh repaints that share of blocks from the
         incoming shot each frame; --bloom k:m repeats one frame's motion.
Both: --dither 0..100 crushes the moshed frames to few levels through a Bayer pattern of 2 px cells at 1080, strongest at the cut and easing out over the mosh.

Frames are read consecutively from each file (as Resolve conforms a clip to the timeline rate) with the Rec.709
matrix; the clip is written as ProRes 422 HQ, Rec.709 converted and tagged, 24 fps.

usage: python -I datamosh.py <A video> <A last frame, seconds> <B video> <B first frame, seconds> <out.mov>
       [--engine codec|flow] [--frames 24] [--pre 0] [--q 4] [--bloom k:m] [--block 16] [--bleed 0.15]
       [--refresh 0.0] [--dither 85] [--seed 0] [--preview out.mp4]
The clip holds --pre frames of A before the cut, then the mosh frames (--frames). Prints a JSON summary.
"""
import json, os, subprocess, sys, tempfile
import numpy as np

W, H, FPS = 1920, 1080, 24

def read_frames(path, t0, n):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{t0:.4f}", "-i", path, "-frames:v", str(n),
                          "-vf", f"scale={W}:{H}:in_color_matrix=bt709:in_range=tv:force_original_aspect_ratio=decrease,"
                                 f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2",
                          "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
    if len(f) < n:
        sys.exit(f"{path}: wanted {n} frames from {t0}, got {len(f)}")
    return [x.copy() for x in f]

def bayer(n):
    m = np.array([[0]])
    while m.shape[0] < n:
        m = np.block([[4 * m, 4 * m + 2], [4 * m + 3, 4 * m + 1]])
    return (m + 0.5) / (n * n)

def dither(img, amount, cell):
    """Crush to few levels per channel through an ordered dither; amount 0 returns img, 1 is 3 levels."""
    if amount <= 0:
        return img
    levels = 32.0 * (1 - amount) + 3.0 * amount
    th = bayer(8)
    th = np.kron(th, np.ones((cell, cell)))
    th = np.tile(th, (H // th.shape[0] + 1, W // th.shape[1] + 1))[:H, :W, None]
    x = img.astype(np.float32) / 255.0 * (levels - 1)
    q = np.floor(x + th) / (levels - 1)
    return np.clip(q * 255.0 + 0.5, 0, 255).astype(np.uint8)

def codec_mosh(A, B, q, bloom):
    import av
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "mosh.avi")
    out = av.open(path, "w")
    st = out.add_stream("mpeg4", rate=FPS)
    st.width, st.height, st.pix_fmt = W, H, "yuv420p"
    st.codec_context.options = {"g": "100000", "bf": "0", "sc_threshold": "1000000000", "qmin": str(q), "qmax": str(q)}
    frames = A + B
    cut = len(A)
    for i, f in enumerate(frames):
        vf = av.VideoFrame.from_ndarray(f, format="rgb24").reformat(format="yuv420p")
        vf.pts = i
        vf.pict_type = av.video.frame.PictureType.I if i in (0, cut) else av.video.frame.PictureType.NONE
        for p in st.encode(vf):
            out.mux(p)
    for p in st.encode():
        out.mux(p)
    out.close()
    src = av.open(path)
    vs = src.streams.video[0]
    pkts = [p for p in src.demux(vs) if p.size]
    kinds = ["I" if p.is_keyframe else "P" for p in pkts]
    if kinds[cut] != "I" or "I" in kinds[cut + 1:]:
        sys.exit(f"the stream's frame kinds around the cut are not as forced: {''.join(kinds)}")
    dec = av.CodecContext.create("mpeg4", "r")
    if vs.codec_context.extradata:
        dec.extradata = vs.codec_context.extradata
    order = list(range(cut)) + list(range(cut + 1, len(pkts)))
    if bloom:
        k, m = bloom
        at = order.index(cut + k)
        order = order[:at] + [cut + k] * m + order[at + 1:]
    got = []
    for idx in order:
        for fr in dec.decode(pkts[idx]):
            got.append(fr.to_ndarray(format="rgb24"))
    for fr in dec.decode(None):
        got.append(fr.to_ndarray(format="rgb24"))
    src.close()
    return got[cut:], "".join(kinds)

def flow_mosh(A, B, block, bleed, refresh, bloom, seed):
    import cv2
    rng = np.random.default_rng(seed)
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
    held = A[-1].astype(np.float32)
    gray = [cv2.cvtColor(b, cv2.COLOR_RGB2GRAY) for b in B]
    flows = [None]
    for i in range(1, len(B)):
        fb = dis.calc(gray[i], gray[i - 1], None)
        bh, bw = H // block, W // block
        q = fb[:bh * block, :bw * block].reshape(bh, block, bw, block, 2).mean(axis=(1, 3))
        q = np.repeat(np.repeat(q, block, 0), block, 1)
        full = np.zeros_like(fb)
        full[:q.shape[0], :q.shape[1]] = q
        full[q.shape[0]:, :] = fb[q.shape[0]:, :]
        full[:, q.shape[1]:] = fb[:, q.shape[1]:]
        flows.append(full)
    seq = list(range(1, len(B)))
    if bloom:
        k, m = bloom
        seq = seq[:k - 1] + [k] * m + seq[k:]
    out = []
    for i in seq:
        mx, my = gx + flows[i][..., 0], gy + flows[i][..., 1]
        held = cv2.remap(held, mx, my, cv2.INTER_NEAREST, borderMode=cv2.BORDER_REPLICATE)
        pred = cv2.remap(B[i - 1].astype(np.float32), mx, my, cv2.INTER_NEAREST, borderMode=cv2.BORDER_REPLICATE)
        held = held + bleed * (B[i].astype(np.float32) - pred)
        if refresh > 0:
            bh, bw = H // block + 1, W // block + 1
            mask = np.repeat(np.repeat(rng.random((bh, bw)) < refresh, block, 0), block, 1)[:H, :W]
            held[mask] = B[i].astype(np.float32)[mask]
        held = np.clip(held, 0, 255)
        out.append(held.astype(np.uint8))
    return out

def write(frames, path, preview):
    rec709 = ["-vf", "scale=out_color_matrix=bt709:out_range=tv,setparams=color_primaries=bt709:color_trc=bt709:"
              "colorspace=bt709:range=tv", "-colorspace", "bt709", "-color_primaries", "bt709",
              "-color_trc", "bt709", "-color_range", "tv"]
    targets = [(path, ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"])]
    if preview:
        targets.append((preview, ["-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p"]))
    for out, codec in targets:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                              f"{W}x{H}", "-r", str(FPS), "-i", "-", *rec709, *codec, out], stdin=subprocess.PIPE)
        for f in frames:
            p.stdin.write(np.ascontiguousarray(f).tobytes())
        p.stdin.close()
        if p.wait():
            sys.exit(f"ffmpeg failed writing {out}")

def main():
    a = sys.argv[1:]
    fa, ta, fb, tb, out = a[0], float(a[1]), a[2], float(a[3]), a[4]
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    engine, n, pre = opt("--engine", "codec"), int(opt("--frames", 24)), int(opt("--pre", 0))
    bloom = tuple(int(x) for x in opt("--bloom", "").split(":")) if "--bloom" in a else None
    dith = float(opt("--dither", 85)) / 100.0
    cell = max(1, round(2 * H / 1080))
    lead = max(pre + 1, 4)
    A = read_frames(fa, max(0.0, ta - (lead - 1) / FPS), lead)
    B = read_frames(fb, tb, n + 1)
    if engine == "codec":
        mosh, kinds = codec_mosh(A, B, int(opt("--q", 4)), bloom)
        mosh = mosh[:n]
    else:
        mosh = flow_mosh(A, B, int(opt("--block", 16)), float(opt("--bleed", 0.15)), float(opt("--refresh", 0.0)),
                         bloom, int(opt("--seed", 0)))[:n]
        kinds = None
    graded = []
    for i, f in enumerate(mosh):
        k = dith * (1.0 - 0.4 * i / max(1, len(mosh) - 1))
        graded.append(dither(f, k, cell))
    frames = A[len(A) - pre:] + graded if pre else graded
    write(frames, out, opt("--preview", None))
    print(json.dumps({"out": out, "engine": engine, "frames": len(frames), "pre": pre, "mosh": len(graded),
                      "stream": kinds, "dither": dith, "bloom": bloom}))

if __name__ == "__main__":
    main()
