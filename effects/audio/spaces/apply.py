"""Develop Spaces command line.

    python -I effects/audio/spaces/apply.py in.wav out.wav --fx shimmer --mix 0.4 --decay 8 --fifth 0.3

Reads any file soundfile reads, resamples to 48 kHz when needed, runs the effect, writes 48 kHz 24 bit
WAV. --fx is one of shimmer, wash, room, preverb, stretch, freeze; every other --name value pair is passed
to the effect as a keyword (numbers become floats, true/false/none become booleans and None).
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
import soundfile as sf

from spaces import FX
from common import resample, true_peak_db, lufs
import preverb as _pv

SR = 48000

def _value(s):
    t = s.strip().lower()
    if t in ("true", "yes", "on"):
        return True
    if t in ("false", "no", "off"):
        return False
    if t in ("none", "null", "auto"):
        return None
    try:
        v = float(s)
        return int(v) if t.lstrip("-").isdigit() else v
    except ValueError:
        return s

def parse(argv):
    ap = argparse.ArgumentParser(description="Develop Spaces")
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--fx", required=True, choices=sorted(FX))
    ap.add_argument("--quiet", action="store_true")
    args, rest = ap.parse_known_args(argv)
    params = {}
    i = 0
    while i < len(rest):
        k = rest[i]
        if not k.startswith("--") or i + 1 >= len(rest):
            ap.error("parameters come as --name value pairs, got %r" % k)
        params[k[2:].replace("-", "_")] = _value(rest[i + 1])
        i += 2
    return args, params

def run(inp, out, fx, params, quiet=False):
    x, sr = sf.read(inp, dtype="float32", always_2d=True)
    if sr != SR:
        x = resample(x.astype(np.float64), sr, SR).astype(np.float32)
    t = time.time()
    y = FX[fx](x, SR, **params)
    el = time.time() - t
    sf.write(out, np.asarray(y, dtype=np.float32), SR, subtype="PCM_24")
    info = dict(fx=fx, seconds_in=x.shape[0] / SR, seconds_out=y.shape[0] / SR, cpu_s=el,
                true_peak_dbtp=true_peak_db(y), lufs_in=lufs(x, SR), lufs_out=lufs(y, SR))
    if fx == "preverb":
        info["lead_s"] = _pv.last_lead
    if not quiet:
        msg = ", ".join(f"{k} {v:.3f}" if isinstance(v, float) else f"{k} {v}" for k, v in info.items())
        print(msg)
        if info.get("lead_s"):
            print(f"place {out} {info['lead_s']:.3f} s earlier than {inp} on the timeline")
    return info

def main(argv=None):
    args, params = parse(sys.argv[1:] if argv is None else argv)
    run(args.inp, args.out, args.fx, params, args.quiet)

if __name__ == "__main__":
    main()
