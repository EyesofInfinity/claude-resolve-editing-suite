"""The audio link: a soundtrack turned into per-frame envelopes that drive the video effects, so a glow swells
with the music, focus racks on a hit, trails pulse on the beat.

Features, one value per video frame at the given rate, each 0 to 1:
  rms     loudness (RMS in dB over the frame, over the clip's own 5th to 99th percentile), smoothed by an attack and
          a release
  low     energy under 150 Hz (kicks, booms), mid 150 Hz to 2.5 kHz, high above 2.5 kHz (hats, air), each
          normalised to its own 98th percentile over the clip and smoothed the same way
  onset   spectral flux (positive change of the log spectrum), peak-picked: 1 on a hit frame, decaying after it
  beat    1 on each beat frame, decaying; tempo in the header (the beat family's tracker, music.py)
  downbeat 1 on each downbeat (the first beat of a bar), decaying over at least 0.4 s
  kick    1 on each low hit (a kick or a bass note under 150 Hz), decaying
  centroid brightness (spectral centroid, log scale 100 Hz to 10 kHz)

usage: python -I analyse.py <audio or video> <out.json> [--fps 24] [--start s] [--dur s] [--attack 0.02] [--release 0.25]
The json holds {"fps", "tempo", "n", "features": {name: [values]}, "hits": [frame...], "beats": [frame...],
"downbeats": [frame...], "kicks": [frame...]}. MIT License.
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SR = 48000

def load(path, start=0.0, dur=0.0):
    """Any file ffmpeg reads, as mono float32 at 48 kHz."""
    tmp = os.path.join(tempfile.gettempdir(), f"link_{os.getpid()}.wav")
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{start}", "-i", path]
    if dur:
        cmd += ["-t", f"{dur}"]
    subprocess.run(cmd + ["-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_f32le", tmp], check=True)
    x, _ = sf.read(tmp, dtype="float32")
    os.remove(tmp)
    return x

def smooth(v, fps, attack, release):
    """A peak follower: rises with time constant attack, falls with release (seconds)."""
    a, r = np.exp(-1.0 / max(1e-3, attack * fps)), np.exp(-1.0 / max(1e-3, release * fps))
    out, y = np.empty_like(v), 0.0
    for i, s in enumerate(v):
        k = a if s > y else r
        y = k * y + (1 - k) * s
        out[i] = y
    return out

def decay(n, frames, fps, release):
    """1 on each frame given, falling exponentially with the release time between them."""
    v = np.zeros(n)
    for f in frames:
        if 0 <= f < n:
            v[f] = 1.0
    out, y, r = np.empty(n), 0.0, np.exp(-1.0 / max(1e-3, release * fps))
    for i in range(n):
        y = max(v[i], y * r)
        out[i] = y
    return out

def analyse(x, fps=24.0, attack=0.02, release=0.25):
    hop = SR / fps
    n = int(np.floor(len(x) / hop))
    win = 4096
    pad = np.pad(x, (win // 2, win // 2))
    hann = np.hanning(win).astype(np.float32)
    freqs = np.fft.rfftfreq(win, 1.0 / SR)
    rms, low, mid, high, cen, flux = (np.zeros(n) for _ in range(6))
    prev = None
    for i in range(n):
        c = int(i * hop + hop / 2)
        seg = pad[c:c + win]
        if len(seg) < win:
            seg = np.pad(seg, (0, win - len(seg)))
        frame = x[int(i * hop):int((i + 1) * hop)]
        rms[i] = 20 * np.log10(np.sqrt(np.mean(frame.astype(np.float64) ** 2)) + 1e-9)
        sp = np.abs(np.fft.rfft(seg * hann)) ** 2
        low[i] = sp[freqs < 150].sum()
        mid[i] = sp[(freqs >= 150) & (freqs < 2500)].sum()
        high[i] = sp[freqs >= 2500].sum()
        tot = sp.sum() + 1e-12
        cen[i] = (sp * freqs).sum() / tot
        ls = np.log1p(sp[freqs < 8000] * 1e3)
        flux[i] = 0.0 if prev is None else np.maximum(ls - prev, 0).sum()
        prev = ls

    def norm(v):
        v = np.sqrt(v)
        return np.clip(v / (np.percentile(v, 98) + 1e-12), 0, 1)

    lo_db, hi_db = np.percentile(rms, 5), np.percentile(rms, 99)
    f = {"rms": smooth(np.clip((rms - lo_db) / max(1.0, hi_db - lo_db), 0, 1), fps, attack, release),
         "low": smooth(norm(low), fps, attack, release),
         "mid": smooth(norm(mid), fps, attack, release),
         "high": smooth(norm(high), fps, attack, release),
         "centroid": np.clip((np.log10(np.maximum(cen, 100)) - 2) / 2, 0, 1)}
    w = max(3, int(fps))
    med = np.array([np.median(flux[max(0, i - w):i + w + 1]) for i in range(n)])
    spread = np.array([np.median(np.abs(flux[max(0, i - w):i + w + 1] - med[i])) for i in range(n)])
    thr = med + 1.5 * spread * 1.4826 + 1e-9
    hits, last = [], -10 ** 9
    for i in range(1, n - 1):
        if flux[i] > thr[i] and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1] and i - last >= 0.12 * fps:
            hits.append(i)
            last = i
    f["onset"] = decay(n, hits, fps, release)
    tempo, beats, downs, lows = 0.0, [], [], []
    try:
        import librosa
        import music
        mu = music.analyse(librosa.resample(x, orig_sr=SR, target_sr=music.SR))
        tempo = mu["tempo"]
        beats = sorted({int(round(s * fps)) for s in mu["beats"]})
        downs = sorted({int(round(s * fps)) for s, b in zip(mu["beats"], mu["bar"]) if b == 0})
        lows = sorted({int(round(s * fps)) for s in mu["kicks"]})
    except Exception as e:
        print("music analysis skipped:", e)
        try:
            import librosa
            t, b = librosa.beat.beat_track(y=x, sr=SR, hop_length=512, units="time")
            tempo = float(np.atleast_1d(t)[0])
            beats = sorted({int(round(s * fps)) for s in b})
        except Exception as e2:
            print("beat tracking skipped:", e2)
    f["beat"] = decay(n, beats, fps, release)
    f["downbeat"] = decay(n, downs, fps, max(release, 0.4))
    f["kick"] = decay(n, lows, fps, release)
    return {"fps": fps, "tempo": tempo, "n": n, "hits": hits, "beats": beats, "downbeats": downs, "kicks": lows,
            "features": {k: [round(float(v), 4) for v in vals] for k, vals in f.items()}}

def curve(link, feature, n=None, lo=0.0, hi=1.0, gamma=1.0, offset=0):
    """A feature as an effect amount: lo at silence to hi at full, shaped by gamma, shifted by offset frames
    (a negative offset lets the picture lead the sound, as editors often cut a frame early)."""
    v = np.asarray(link["features"][feature], dtype=np.float64)
    if offset:
        v = np.roll(v, offset)
        if offset > 0:
            v[:offset] = v[offset]
        else:
            v[offset:] = v[offset - 1]
    if n is not None:
        v = np.interp(np.arange(n), np.linspace(0, n - 1, len(v)) if len(v) > 1 else [0], v) if len(v) != n else v
    return lo + (hi - lo) * np.clip(v, 0, 1) ** gamma

def drive(path, spec, n):
    """An effect's envelope from a link json and a spec "feature[:lo:hi:gamma:offset]" (e.g. "onset:0.3:1:1:-1"),
    n frames long. The renderers' --link and --drive use it."""
    p = spec.split(":")
    lo, hi, gamma, offset = (float(p[1]) if len(p) > 1 else 0.0, float(p[2]) if len(p) > 2 else 1.0,
                             float(p[3]) if len(p) > 3 else 1.0, int(float(p[4])) if len(p) > 4 else 0)
    return curve(json.load(open(path, encoding="utf-8")), p[0], n, lo, hi, gamma, offset)

def main():
    a = sys.argv[1:]
    arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    x = load(a[0], float(arg("--start", 0)), float(arg("--dur", 0)))
    out = analyse(x, float(arg("--fps", 24)), float(arg("--attack", 0.02)), float(arg("--release", 0.25)))
    json.dump(out, open(a[1], "w", encoding="utf-8"))
    print(f"{out['n']} frames at {out['fps']} fps, tempo {out['tempo']:.1f}, {len(out['hits'])} hits, "
          f"{len(out['beats'])} beats -> {a[1]}")

if __name__ == "__main__":
    main()
