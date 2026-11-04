"""Run one Develop Character effect on a sound file and write a 48 kHz 24-bit WAV.

usage: python -I apply.py <in.wav> <out.wav> --fx <name> [--<param> <value> ...]
       python -I apply.py --list            every effect with its parameters and defaults
  --fx       tape, tape_stop, tape_start, vinyl, cassette, bitcrush, memory, radio, telephone, old_tv, intercom, wall,
             ghost, robot, ringmod, octaver, terminal, stutter, beat_repeat, tape_scrub, gate_pattern, doppler, riser,
             sub_drop, transient
  --<param>  any argument of the effect, e.g. --drive 9 --speed 7.5 --at 1.2,3.4 --pattern x.x.xx.x
             numbers parse as numbers, true/false as booleans, comma lists stay text where the effect takes times
Input at any rate is resampled to 48 kHz first. The output is aligned sample for sample with the input and has its
length. Prints a JSON summary: true peak and loudness before and after, seconds of compute.
"""
import json
import os
import sys
import time

import numpy as np
import soundfile as sf
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import character as CH
import common as C

SR = 48000

def parse_value(s, default):
    if isinstance(default, bool):
        return s.lower() in ("1", "true", "yes", "on")
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    if low == "none":
        return None
    if "," in s:
        return s
    try:
        v = float(s)
        if isinstance(default, int) and not isinstance(default, bool) and v.is_integer():
            return int(v)
        return v
    except ValueError:
        return s

def load(path):
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    if sr != SR:
        from math import gcd
        g = gcd(SR, int(sr))
        x = signal.resample_poly(x, SR // g, int(sr) // g, axis=0).astype(np.float32)
    return x, SR

def main(argv):
    if "--list" in argv:
        for name in CH.FX:
            print(name + ": " + ", ".join(f"{k}={v!r}" for k, v in CH.params(name).items()))
        return 0
    if len(argv) < 4 or "--fx" not in argv:
        print(__doc__)
        return 2
    src, dst = argv[0], argv[1]
    rest = argv[2:]
    kw, name = {}, None
    i = 0
    while i < len(rest):
        k = rest[i]
        if not k.startswith("--") or i + 1 >= len(rest):
            print(f"bad argument {k}")
            return 2
        v = rest[i + 1]
        if k == "--fx":
            name = v
        else:
            kw[k[2:]] = v
        i += 2
    if name not in CH.FX:
        print(f"unknown effect {name}")
        return 2
    defaults = CH.params(name)
    for k in list(kw):
        if k not in defaults:
            print(f"{name} has no parameter {k}; it takes: {', '.join(defaults)}")
            return 2
        kw[k] = parse_value(kw[k], defaults[k])
    x, sr = load(src)
    t0 = time.time()
    y = CH.run(name, x, sr, **kw)
    dt = time.time() - t0
    y = C.as2d(y).astype(np.float32)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    sf.write(dst, y, sr, subtype="PCM_24")
    summary = {
        "fx": name, "params": kw, "in": src, "out": dst, "seconds": round(x.shape[0] / sr, 3),
        "compute_s": round(dt, 3), "tp_in_dbtp": round(C.true_peak_db(x), 2), "tp_out_dbtp": round(C.true_peak_db(y), 2),
        "lufs_in": round(C.lufs(x, sr), 2), "lufs_out": round(C.lufs(y, sr), 2),
    }
    print(json.dumps(summary))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
