"""Shot judge, first rule (highlight-percentile thresholds): the Bloom threshold for one frame.

Keep the look's threshold, but raise it until at most <budget> of the picture is above it, so bright daylight
and high-key shots do not bloom over most of the frame. Night and forest shots, where fewer pixels are bright,
keep the look's value exactly.

usage: python -I judge.py <frame> [base threshold in display % (45)] [budget share (0.30)]
The frame is a still exported from Resolve (TIFF or PNG, 8 or 16 bit) or a CPU-harness raw (.rgb48: 10-bit
codes x 64, 16-bit little-endian RGB, 1920 x 1080). Black letterbox rows are ignored.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load(path):
    if path.lower().endswith(".rgb48"):
        return np.fromfile(path, dtype="<u2").reshape(1080, 1920, 3).astype(np.float64) / 64 / 1023
    from gate import imread
    a = imread(path)
    scale = 65535.0 if a.dtype == np.uint16 else 255.0
    return a[..., :3][..., ::-1].astype(np.float64) / scale


def auto_threshold(path, base=45.0, budget=0.30):
    a = load(path)
    rows = np.where(a.max(axis=(1, 2)) > 0.02)[0]
    a = a[rows.min():rows.max() + 1] if len(rows) else a
    # the same brightness Bloom Bright compares with its threshold: luma of linear light, back in display terms
    lin = np.power(np.clip(a, 0.0, None), 2.4)
    y = np.power(lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722, 1 / 2.4).ravel()
    q = float(np.percentile(y, 100.0 * (1.0 - budget)))
    return max(base, round(q * 100.0, 1)), float((y >= base / 100.0).mean())


def night_stops(path, base, key=0.157, pull=0.5, lo=0.5, hi=3.5):
    """Night key (for a look with Night): the still is the shot through the look and Night at the look's own Night
    Exposure `base`. Its median moves one stop per stop of Night Exposure (on eight forest frames,
    1.00 to 1.04), so the stops that pull the median `pull` of the way to the night key (display luma `key`, 40/255,
    near the middle, 0.16, of the bible's 0.10 to 0.22) are base + pull * log2(median / key), in linear light, kept
    in lo..hi."""
    a = load(path)
    rows = np.where(a.max(axis=(1, 2)) > 0.02)[0]
    a = a[rows.min():rows.max() + 1] if len(rows) else a
    lin = np.power(np.clip(a, 0.0, None), 2.4)
    med = float(np.median(lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722))
    stops = base + pull * np.log2(max(med, 1e-6) / key ** 2.4)
    return float(np.clip(round(stops, 2), lo, hi)), med ** (1 / 2.4)


def stats(path):
    """What a frame holds: display-luma percentiles, the share
    clipped (any channel at 0.995 or more) and crushed (every channel at 0.005 or less), and the colour cast in
    linear RGB, normalised to luma 1: grey-world over low-chroma midtones averaged with shades-of-grey (p = 6)."""
    a = load(path)
    rows = np.where(a.max(axis=(1, 2)) > 0.02)[0]
    a = a[rows.min():rows.max() + 1] if len(rows) else a
    lin = np.power(np.clip(a, 0.0, None), 2.4).reshape(-1, 3)
    w = np.array([0.2126, 0.7152, 0.0722])
    yd = np.power(lin @ w, 1 / 2.4)
    mx, mn = lin.max(axis=1), lin.min(axis=1)
    mid = (yd > 0.15) & (yd < 0.85) & ((mx - mn) / (mx + 1e-6) < 0.3)
    gw = lin[mid].mean(axis=0) if mid.sum() > 0.01 * len(yd) else lin.mean(axis=0)
    sog = np.power(np.power(lin, 6).mean(axis=0), 1 / 6)
    cast = 0.5 * (gw / (gw @ w) + sog / (sog @ w))
    flat = a.reshape(-1, 3)
    return {"p1": float(np.percentile(yd, 1)), "p50": float(np.percentile(yd, 50)),
            "p995": float(np.percentile(yd, 99.5)), "clip": float((flat.max(axis=1) >= 0.995).mean()),
            "crush": float((flat.max(axis=1) <= 0.005).mean()), "cast": [float(c) for c in cast],
            "midtone_share": float(mid.mean())}


def exposure_stops(st, target_mid=0.32, limit=1.0):
    """Rule two (off unless a look asks): stops that bring the median display luma to the look's target."""
    stops = np.log2((target_mid ** 2.4) / max(st["p50"], 1e-4) ** 2.4)
    return float(np.clip(stops, -limit, limit))


def white_balance(st, keep=0.15):
    """Rule three (off unless a look asks): the Temp and Tint that leave `keep` of the measured cast."""
    from wb import solve_cast
    return solve_cast(st["cast"], keep)


if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[2] == "--report":
    target = float(sys.argv[3]) if len(sys.argv) > 3 else 0.32
    st = stats(sys.argv[1])
    temp, tint, _ = white_balance(st)
    print(f"p1 {st['p1']:.3f}  p50 {st['p50']:.3f}  p99.5 {st['p995']:.3f}  clip {st['clip'] * 100:.2f}%  "
          f"crush {st['crush'] * 100:.2f}%  cast {[round(c, 3) for c in st['cast']]}  "
          f"(midtones {st['midtone_share'] * 100:.0f}%)")
    print(f"rule two: exposure {exposure_stops(st, target):+.2f} stops to a median of {target}; "
          f"rule three: Temp {temp:+.0f}, Tint {tint:+.0f} to keep 15% of the cast")
    sys.exit()

if __name__ == "__main__":
    base = float(sys.argv[2]) if len(sys.argv) > 2 else 45.0
    budget = float(sys.argv[3]) if len(sys.argv) > 3 else 0.30
    thr, share = auto_threshold(sys.argv[1], base, budget)
    print(f"{thr:.1f}  (share of picture at or above {base:.0f}: {share * 100:.1f}%)")
