"""Quality gate, the detectors that work on stills: a graded frame against the same frame before the
effects, and for a frozen pattern two adjacent frames. Letterbox rows are left out. Thresholds are starting values, so a verdict is a flag for a look, never a ruling on one.

  clip and crush (4): the share of pixels newly clipped (any channel 0.995 or more) or crushed (all 0.005 or less)
  energy (7):         mean linear luminance, graded against before; flag above +3%
  halo (3):           overshoot beyond the 5 px min/max envelope of the before frame, within 5 px of its edges
                      (Canny); flag when the median is above 0.02
  frozen (2):         correlation between the effect fields (graded minus before, fine detail only) of two adjacent
                      frames, in screen space; above 0.4 on moving footage the effect is a pattern fixed to the
                      screen, which a live effect such as grain never is

usage: python -I gate.py <before.png> <graded.png> [<before next frame.png> <graded next frame.png>]
"""
import sys

import cv2
import numpy as np

W = np.array([0.2126, 0.7152, 0.0722])
LIMITS = {"clip_added": 0.005, "crush_added": 0.005, "energy": 0.03, "halo_median": 0.02, "frozen": 0.4}


def imread(path):
    """cv2.imread, but a path with non-ASCII letters works: cv2.imread returns None on those on Windows."""
    a = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_UNCHANGED)
    if a is None:
        sys.exit("cannot read " + path)
    return a


def load(path):
    a = imread(path)
    scale = 65535.0 if a.dtype == np.uint16 else 255.0
    return a[..., :3][..., ::-1].astype(np.float64) / scale


def picture_rows(before, graded=None):
    """Rows with picture in both frames, so a letterbox in either (a Matte look adds bars) is left out."""
    live = before.max(axis=(1, 2)) > 0.02
    if graded is not None:
        live &= graded.max(axis=(1, 2)) > 0.02
    rows = np.where(live)[0]
    return slice(rows.min(), rows.max() + 1) if len(rows) else slice(None)


def clip_crush(before, graded):
    clip = lambda a: (a.max(axis=2) >= 0.995).mean()
    crush = lambda a: (a.max(axis=2) <= 0.005).mean()
    return {"clip_added": float(clip(graded) - clip(before)), "crush_added": float(crush(graded) - crush(before))}


def energy(before, graded):
    lin = lambda a: (np.power(np.clip(a, 0, None), 2.4) @ W).mean()
    return {"energy": float(lin(graded) / max(lin(before), 1e-9) - 1.0)}


def halo(before, graded):
    yb, yg = before @ W, graded @ W
    edges = cv2.Canny((np.clip(yb, 0, 1) * 255).astype(np.uint8), 40, 120) > 0
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    zone = cv2.dilate(edges.astype(np.uint8), k) > 0
    hi = cv2.dilate(yb.astype(np.float32), k)
    lo = cv2.erode(yb.astype(np.float32), k)
    over = np.maximum(np.maximum(yg - hi, lo - yg), 0.0)[zone]
    if over.size == 0:
        return {"halo_median": 0.0, "halo_p95": 0.0, "edge_share": 0.0}
    return {"halo_median": float(np.median(over)), "halo_p95": float(np.percentile(over, 95)),
            "edge_share": float(zone.mean())}


def frozen(b0, g0, b1, g1):
    def field(b, g):
        d = (g - b) @ W
        return d - cv2.GaussianBlur(d, (0, 0), 3)
    f0, f1 = field(b0, g0).ravel(), field(b1, g1).ravel()
    f0, f1 = f0 - f0.mean(), f1 - f1.mean()
    den = np.sqrt((f0 * f0).sum() * (f1 * f1).sum())
    return {"frozen": float((f0 * f1).sum() / den) if den > 0 else 0.0}


def gate(before, graded, nxt=None):
    rows = picture_rows(before, graded)
    b, g = before[rows], graded[rows]
    out = {}
    out.update(clip_crush(b, g))
    out.update(energy(b, g))
    out.update(halo(b, g))
    if nxt is not None:
        out.update(frozen(b, g, nxt[0][rows], nxt[1][rows]))
    out["flags"] = [k for k, lim in LIMITS.items() if k in out and out[k] > lim]
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) not in (2, 4):
        sys.exit(__doc__)
    nxt = (load(a[2]), load(a[3])) if len(a) == 4 else None
    r = gate(load(a[0]), load(a[1]), nxt)
    print("  ".join(f"{k} {v:+.4f}" if isinstance(v, float) else f"{k} {v}" for k, v in r.items()))
