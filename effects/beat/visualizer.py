"""Develop Visualizer: the music drawn as light, for music videos. Three
styles, each a fine line of light with a soft glow, never a bar meter:
  line   a spectrum line across the lower part of the frame, 30 Hz to 11 kHz on a musical (log) scale, flat in
         silence, a faint reflection under it and peak points that hang and fall
  ring   the spectrum around a circle (low notes at the bottom, high at the top, mirrored), the circle breathing
         with the bass, a thin still ring inside it
  wave   an oscilloscope: the waveform of the last 46 ms as one line, held still on a rising zero crossing of its
         bass so it does not crawl, a short afterglow behind it
The same analysis as the beat family: an STFT of the song, bands followed with a 25 ms attack and a 160 ms release.
Rendered as ProRes 4444 with alpha (light only, for a track above the picture: Normal or Add), or laid over a
clip with Screen for a preview. Drawn on the CPU with OpenCV (anti-aliased lines, Gaussian glow).

usage: python -I visualizer.py <music> <out.mov|out.mp4> [--style line|ring|wave] [--size 1920x1080] [--fps 24]
       [--start s] [--dur s] [--color 230,236,250] [--jobs 8] [--under clip.mp4 --under-start s]
An alpha .mov renders in --jobs pieces at once; --under lays the light over a clip with Screen (a preview, .mp4).
MIT License.
"""
import os
import subprocess
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "audio", "link"))
import music

SR = 44100
NB = 120

class Spectrum:
    """Band levels 0 to 1 per video frame, and the raw samples for the wave."""

    def __init__(self, path, fps, start=0.0, dur=0.0):
        self.x = music.load(path, start, dur, sr=SR).astype(np.float32)
        self.fps = fps
        self.n = int(len(self.x) / SR * fps)
        nfft = 4096
        win = np.hanning(nfft).astype(np.float32)
        freqs = np.fft.rfftfreq(nfft, 1 / SR)
        edges = np.geomspace(30, 11000, NB + 1)
        self.centres = np.sqrt(edges[:-1] * edges[1:])
        idx = [np.where((freqs >= edges[i]) & (freqs < edges[i + 1]))[0] for i in range(NB)]
        idx = [ix if len(ix) else np.array([int(np.argmin(np.abs(freqs - self.centres[i])))]) for i, ix in enumerate(idx)]
        M = np.zeros((len(freqs), NB), np.float32)
        for i, ix in enumerate(idx):
            M[ix, i] = 1.0 / len(ix)
        pad = np.pad(self.x, (nfft // 2, nfft // 2 + nfft))
        db = np.zeros((self.n, NB), np.float32)
        for k0 in range(0, self.n, 256):
            ks = np.arange(k0, min(self.n, k0 + 256))
            seg = np.stack([pad[int(k / fps * SR):int(k / fps * SR) + nfft] for k in ks])
            sp = np.abs(np.fft.rfft(seg * win, axis=1)) ** 2
            db[ks] = 10 * np.log10(sp @ M + 1e-12)
        db += 4.5 * np.log2(self.centres / 1000.0)[None, :]
        lo, hi = np.percentile(db, 30), np.percentile(db, 99.7)
        lev = np.clip((db - lo) / max(1e-6, hi - lo), 0, 1) ** 1.3
        lev = cv2.GaussianBlur(lev, (0, 0), sigmaX=1.2, sigmaY=0.01)
        a, r = np.exp(-1 / (0.025 * fps)), np.exp(-1 / (0.16 * fps))
        out, y = np.zeros_like(lev), np.zeros(NB, np.float32)
        for k in range(self.n):
            kk = np.where(lev[k] > y, a, r)
            y = kk * y + (1 - kk) * lev[k]
            out[k] = y
        self.lev = out
        bass = out[:, self.centres < 150].mean(1)
        self.bass = bass / (np.percentile(bass, 98) + 1e-6)
        self.agc = np.percentile(np.abs(self.x), 99.5) + 1e-6

    def wave(self, k, npts=640):
        """46 ms of the waveform at frame k, smoothed and held on a rising zero crossing of its low part."""
        c = int(k / self.fps * SR)
        span, search = 2048, 1024
        a = max(0, c - span // 2 - search)
        seg = self.x[a:a + span + 2 * search]
        if len(seg) < span + 2 * search:
            seg = np.pad(seg, (0, span + 2 * search - len(seg)))
        low = np.convolve(seg, np.hanning(301) / np.hanning(301).sum(), mode="same")
        mid = len(seg) // 2
        zc = np.where((low[:-1] < 0) & (low[1:] >= 0))[0]
        z = zc[np.argmin(np.abs(zc - mid))] if len(zc) else mid
        z = int(np.clip(z, span // 2, len(seg) - span // 2 - 1))
        w = seg[z - span // 2:z + span // 2]
        w = np.convolve(w, np.hanning(41) / np.hanning(41).sum(), mode="same")
        w = np.interp(np.linspace(0, span - 1, npts), np.arange(span), w)
        return np.clip(w / self.agc, -1.2, 1.2) * np.hanning(npts) ** 0.35

def _lines(h, w, polys, thick):
    m = np.zeros((h, w), np.uint8)
    S = 16
    for p in polys:
        q = np.round(np.asarray(p) * S).astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(m, [q], False, 255, thickness=thick, lineType=cv2.LINE_AA, shift=4)
    return m.astype(np.float32) / 255.0

def _dots(h, w, pts, rad):
    m = np.zeros((h, w), np.uint8)
    for x, y in pts:
        cv2.circle(m, (int(round(x * 16)), int(round(y * 16))), int(rad * 16), 255, -1, cv2.LINE_AA, shift=4)
    return m.astype(np.float32) / 255.0

def _glow(core, h):
    """Core line plus two Gaussian glows, in linear light (0 to about 2)."""
    size = (core.shape[1], core.shape[0])
    half = cv2.resize(core, (size[0] // 2, size[1] // 2), interpolation=cv2.INTER_AREA)
    s1 = cv2.resize(cv2.GaussianBlur(half, (0, 0), h * 0.002), size, interpolation=cv2.INTER_LINEAR)
    small = cv2.resize(half, (size[0] // 4, size[1] // 4), interpolation=cv2.INTER_AREA)
    s2 = cv2.resize(cv2.GaussianBlur(small, (0, 0), h * 0.006), size, interpolation=cv2.INTER_LINEAR)
    return core * 1.0 + s1 * 1.1 + s2 * 1.1

class Painter:
    def __init__(self, spec, style, w, h, color=None):
        self.s, self.style, self.w, self.h = spec, style, w, h
        c = np.array([int(v) for v in (color or "230,236,250").split(",")], np.float32) / 255.0
        self.col = c ** 2.4
        self.peak = np.zeros(NB, np.float32)
        self.trail = None
        grid = (np.linspace(0, 1, 4096, dtype=np.float32) ** 2) * 4.0
        self.lut = to_display(grid[:, None, None] * self.col[None, None, :])[:, 0, :].astype(np.float32)

    @staticmethod
    def index(L):
        return (np.sqrt(np.clip(L * 0.25, 0, 1)) * 4095 + 0.5).astype(np.int32)

    def display(self, L):
        """Display RGB (h, w, 3) from the light."""
        return self.lut[self.index(L)]

    def frame(self, k):
        """The light at frame k: one channel (h, w), linear, 0 to 4; display() colours it."""
        s, w, h = self.s, self.w, self.h
        lev = s.lev[min(k, s.n - 1)]
        if self.style == "line":
            xs = np.linspace(0.08 * w, 0.92 * w, 480)
            u = np.linspace(0, NB - 1, 480)
            v = np.interp(u, np.arange(NB), lev)
            edge = np.sin(np.linspace(0, np.pi, 480)) ** 0.5
            base = 0.78 * h
            ys = base - v * edge * 0.22 * h
            core = _lines(h, w, [np.stack([xs, ys], 1)], 1)
            self.peak = np.maximum(self.peak - 0.012, lev)
            pk = np.interp(u, np.arange(NB), self.peak)
            pts = [(x, base - p * e * 0.22 * h - 3) for x, p, e, c in zip(xs[::12], pk[::12], edge[::12], v[::12])
                   if p > 0.05 and p - c > 0.04]
            core = core + 0.6 * _dots(h, w, pts, max(1.0, h / 900))
            refl = _lines(h, w, [np.stack([xs, 2 * base - ys + 4], 1)], 1)
            refl *= np.clip(1 - (np.arange(h)[:, None] - base) / (0.12 * h), 0, 1) * (np.arange(h)[:, None] > base)
            light = _glow(core, h) + 0.18 * _glow(refl, h)
        elif self.style == "ring":
            cx, cy = 0.5 * w, 0.5 * h
            b = float(np.clip(s.bass[min(k, s.n - 1)], 0, 1.5))
            r0 = 0.2 * h * (1 + 0.035 * b)
            th = np.linspace(0, np.pi, 360)
            taper = np.clip(0.55 + np.arange(NB) / 40.0, 0, 1)
            v = np.interp(th / np.pi * (NB - 1), np.arange(NB),
                          cv2.GaussianBlur((lev * taper)[None, :], (0, 0), 2.5)[0])
            rr = r0 + v * 0.085 * h
            right = np.stack([cx + rr * np.sin(th), cy - rr * np.cos(th)], 1)
            left = np.stack([cx - rr * np.sin(th), cy - rr * np.cos(th)], 1)
            core = _lines(h, w, [right, left], 1)
            ti = np.linspace(0, 2 * np.pi, 720)
            inner = np.stack([cx + 0.93 * r0 * np.cos(ti), cy + 0.93 * r0 * np.sin(ti)], 1)
            core = core + 0.3 * _lines(h, w, [inner], 1)
            light = _glow(core, h)
        else:
            wv = s.wave(k)
            xs = np.linspace(0.1 * w, 0.9 * w, len(wv))
            ys = 0.5 * h - wv * 0.16 * h
            core = _lines(h, w, [np.stack([xs, ys], 1)], 1)
            light = _glow(core, h)
            if self.trail is not None:
                light = light + 0.3 * self.trail
            self.trail = light * 0.5
        return np.clip(light, 0, 4)

def to_display(lin):
    """Light to display values with a soft shoulder (hot light turns white, never a flat clipped colour)."""
    m = lin.max(2, keepdims=True)
    k = np.where(m > 0.8, (0.8 + 0.2 * np.tanh((m - 0.8) / 0.2)) / np.maximum(m, 1e-6), 1.0)
    v = lin * k
    v = v + (np.clip((m - 1.0) / 2.0, 0, 1) * 0.6) * (k * m - v)
    return np.clip(v, 0, 1) ** (1 / 2.4)

def _chunk(args):
    path, out, style, w, h, fps, start, dur, color, k0, k1 = args
    return render(path, out, style, w, h, fps, start, dur, color, True, None, 0.0, True, (k0, k1))

def render_parallel(path, out, style="line", w=1920, h=1080, fps=24.0, start=0.0, dur=0.0, color=None, jobs=8):
    """The alpha .mov in jobs pieces at once, joined without re-encoding (ProRes frames stand alone)."""
    import multiprocessing as mp
    import tempfile
    n = Spectrum(path, fps, start, dur).n
    step = int(np.ceil(n / jobs))
    tmp = tempfile.mkdtemp(prefix="vis_")
    parts = [(path, os.path.join(tmp, f"p{k:06d}.mov"), style, w, h, fps, start, dur, color, k, min(n, k + step))
             for k in range(0, n, step)]
    with mp.get_context("spawn").Pool(jobs) as pool:
        pool.map(_chunk, parts)
    lst = os.path.join(tmp, "list.txt")
    esc = lambda s: s.replace(os.sep, "/").replace("'", "'\\''")
    open(lst, "w").write("".join(f"file '{esc(p[1])}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                    out], check=True)
    for p in parts:
        os.remove(p[1])
    return n

def render(path, out, style="line", w=1920, h=1080, fps=24.0, start=0.0, dur=0.0, color=None, alpha=True,
           under=None, under_start=0.0, under_fill=True, span=None):
    spec = Spectrum(path, fps, start, dur)
    p = Painter(spec, style, w, h, color)
    k0, k1 = span if span else (0, spec.n)
    for k in range(max(0, k0 - 90), k0):
        p.frame(k)
    if out.lower().endswith(".mov") and alpha:
        enc = ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0"]
        ipix, ch = "rgba", 4
    else:
        enc = ["-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p"]
        ipix, ch = "rgb24", 3
    e = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", ipix, "-s",
                          f"{w}x{h}", "-r", str(fps), "-i", "-"] + enc + ["-colorspace", "bt709", "-color_primaries",
                          "bt709", "-color_trc", "bt709", out], stdin=subprocess.PIPE)
    dec = None
    if under:
        vf = (f"fps={fps},scale={w}:{h}:force_original_aspect_ratio={'increase' if under_fill else 'decrease'}"
              f":in_color_matrix=bt709,crop={w}:{h}")
        dec = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{under_start}", "-i", under, "-frames:v",
                                str(spec.n), "-vf", vf, "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                               stdout=subprocess.PIPE)
    a_t = p.lut.max(1, keepdims=True)
    rgba_t = (np.concatenate([np.where(a_t > 1e-4, p.lut / np.maximum(a_t, 1e-4), 0), a_t], 1) * 255 + 0.5).astype(np.uint8)
    rgb_t = (p.lut * 255 + 0.5).astype(np.uint8)
    for k in range(k0, k1):
        idx = p.index(p.frame(k))
        if dec is not None:
            raw = dec.stdout.read(w * h * 3)
            bg = np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(np.float32) / 255 if len(raw) == w * h * 3 \
                else np.zeros((h, w, 3), np.float32)
            img = 1 - (1 - bg) * (1 - p.lut[idx])
            e.stdin.write((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
        elif ch == 4:
            e.stdin.write(rgba_t[idx].tobytes())
        else:
            e.stdin.write(rgb_t[idx].tobytes())
    e.stdin.close()
    e.wait()
    if dec is not None:
        dec.stdout.close()
        dec.wait()
    return spec.n

def main():
    a = sys.argv[1:]
    arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    w, h = (int(v) for v in arg("--size", "1920x1080").split("x"))
    import time
    t0 = time.time()
    jobs = int(arg("--jobs", 8))
    if a[1].lower().endswith(".mov") and "--under" not in a and jobs > 1:
        n = render_parallel(a[0], a[1], arg("--style", "line"), w, h, float(arg("--fps", 24)), float(arg("--start", 0)),
                            float(arg("--dur", 0)), arg("--color", None), jobs)
    else:
        n = render(a[0], a[1], arg("--style", "line"), w, h, float(arg("--fps", 24)), float(arg("--start", 0)),
                   float(arg("--dur", 0)), arg("--color", None), True, arg("--under", None),
                   float(arg("--under-start", 0)))
    print(f"{n} frames, {(time.time() - t0) / max(1, n) * 1000:.0f} ms a frame -> {a[1]}")

if __name__ == "__main__":
    main()
