"""Beat accuracy measures, the usual ones from beat-tracking evaluation: F-measure of detected beats against
reference beats within a tolerance (70 ms), the mean signed and absolute error of the matched beats, and the share of
reference downbeats found as downbeats. MIT License.
"""
import numpy as np

def match(det, ref, tol=0.07):
    """Greedy one-to-one matching by nearest: returns pairs (i_det, i_ref)."""
    det, ref = np.asarray(det, float), np.asarray(ref, float)
    used, pairs = set(), []
    for j, r in enumerate(ref):
        if len(det) == 0:
            break
        i = int(np.argmin(np.abs(det - r)))
        if abs(det[i] - r) <= tol and i not in used:
            used.add(i)
            pairs.append((i, j))
    return pairs

def fmeasure(det, ref, tol=0.07):
    pairs = match(det, ref, tol)
    p = len(pairs) / max(1, len(det))
    r = len(pairs) / max(1, len(ref))
    f = 2 * p * r / max(1e-9, p + r)
    err = np.array([det[i] - ref[j] for i, j in pairs]) if pairs else np.zeros(0)
    return {"F": round(f, 4), "precision": round(p, 4), "recall": round(r, 4), "matched": len(pairs),
            "n_det": len(det), "n_ref": len(ref),
            "mean_err_ms": round(float(err.mean() * 1000), 2) if len(err) else None,
            "mean_abs_err_ms": round(float(np.abs(err).mean() * 1000), 2) if len(err) else None}

def downbeats(det_beats, det_bar, ref_beats, ref_bar, tol=0.07):
    """F-measure of the downbeats alone."""
    d = [t for t, b in zip(det_beats, det_bar) if b == 0]
    r = [t for t, b in zip(ref_beats, ref_bar) if b == 0]
    return fmeasure(d, r, tol)
