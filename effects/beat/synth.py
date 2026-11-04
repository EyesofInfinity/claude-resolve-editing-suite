"""Test music with a known beat grid, for the beat family's checks: kick, snare, hats, a bass line and chords
that change on the downbeat, a tempo that drifts, a pad-only intro, and noise. Every beat time and bar place is known,
so beat and downbeat accuracy can be measured exactly. Synthesised here; no sample or recording is read.

usage: python -I synth.py <out.wav> <out_truth.json> [--bpm 118] [--to 126] [--bars 24] [--intro 2] [--swing 0]
       [--seed 1] [--meter 4]
MIT License.
"""
import json
import sys

import numpy as np

SR = 44100

def env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)

def kick(rng):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t / 0.03)
    return 0.9 * np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.12)

def snare(rng):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * 190 * t) * env(n, 0.001, 0.05)
    noise = rng.standard_normal(n) * env(n, 0.001, 0.07)
    noise = np.diff(np.concatenate([[0], noise]))
    return 0.35 * tone + 0.5 * noise

def hat(rng):
    n = int(0.06 * SR)
    x = rng.standard_normal(n)
    x = np.diff(np.diff(np.concatenate([[0, 0], x])))
    return 0.08 * x * env(n, 0.0005, 0.015)

def tone(freq, n, a=0.01, d=0.6, harm=4):
    t = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * freq * k * t) / k for k in range(1, harm + 1))
    return s * env(n, a, d)

def make(bpm=118.0, to=126.0, bars=24, intro=2, swing=0.0, seed=1, meter=4):
    rng = np.random.default_rng(seed)
    nb = bars * meter
    tempos = np.linspace(bpm, to, nb)
    times = np.concatenate([[0.0], np.cumsum(60.0 / tempos[:-1])]) + 0.5
    dur = times[-1] + 60.0 / tempos[-1] + 2.0
    x = np.zeros(int(dur * SR) + SR)
    K, Sn = kick(rng), snare(rng)
    roots = [55.0, 43.65, 49.0, 41.2]
    chords = [(220.0, 261.6, 329.6), (174.6, 220.0, 261.6), (196.0, 246.9, 293.7), (164.8, 207.7, 246.9)]

    def put(sig, t, g=1.0):
        i = int(round(t * SR))
        e = min(len(x), i + len(sig))
        x[i:e] += g * sig[:e - i]
    for b, t in enumerate(times):
        bar, pos = divmod(b, meter)
        spb = 60.0 / tempos[b]
        if pos == 0:
            ch = chords[bar % 4]
            n = int(spb * meter * SR)
            for f in ch:
                put(tone(f, n, 0.08, spb * meter * 0.8, 3) * 0.05, t)
        if bar >= intro:
            if meter == 4:
                if pos in (0, 2):
                    put(K, t, 1.0 if pos == 0 else 0.85)
                if pos in (1, 3):
                    put(Sn, t)
            else:
                if pos == 0:
                    put(K, t)
                else:
                    put(Sn, t, 0.6)
            for h in range(2):
                off = h * spb / 2 + (swing * spb / 6 if h else 0)
                put(hat(rng), t + off, 1.0 if h == 0 else 0.7)
            if pos == 0 or pos == 2:
                put(tone(roots[bar % 4], int(spb * 1.8 * SR), 0.005, spb * 0.9, 3) * 0.35, t)
    x += 0.003 * rng.standard_normal(len(x))
    x /= np.abs(x).max() * 1.12
    truth = {"beats": [round(float(t), 5) for t in times], "bar": [int(b % meter) for b in range(nb)],
             "drums_from": float(times[intro * meter]) if intro < bars else float(dur), "meter": meter}
    return x.astype(np.float32), truth

def main():
    import soundfile as sf
    a = sys.argv[1:]
    arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    x, truth = make(float(arg("--bpm", 118)), float(arg("--to", 126)), int(arg("--bars", 24)), int(arg("--intro", 2)),
                    float(arg("--swing", 0)), int(arg("--seed", 1)), int(arg("--meter", 4)))
    sf.write(a[0], x, SR, subtype="PCM_16")
    json.dump(truth, open(a[1], "w", encoding="utf-8"))
    print(f"{len(x) / SR:.1f} s, {len(truth['beats'])} beats -> {a[0]}")

if __name__ == "__main__":
    main()
