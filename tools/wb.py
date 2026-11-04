"""Develop's white balance as numpy, the same arithmetic as Develop.dctl: Temp and Tint pick the white the
footage is taken to have been shot under (Planckian locus, Krystek 1985; Temp in mireds, Tint in Duv), and von Kries
scaling in CAT16 cone space takes it to 6504 K; luminance is renormalised. Used by the shot judge to find the Temp
and Tint that remove a measured colour cast.
"""
import numpy as np

M16 = np.array([[0.401288, 0.650173, -0.051461],
                [-0.250268, 1.204414, 0.045854],
                [-0.002079, 0.048952, 0.953127]])
XYZ_RGB = np.array([[0.4124564, 0.3575761, 0.1804375],
                    [0.2126729, 0.7151522, 0.0721750],
                    [0.0193339, 0.1191920, 0.9503041]])
A = np.linalg.inv(XYZ_RGB) @ np.linalg.inv(M16)
B = M16 @ XYZ_RGB
LUMA = np.array([0.2126, 0.7152, 0.0722])
REF_MIRED = 1e6 / 6504.0
TEMP_SPAN, TINT_SPAN = 55.2348, 0.016952        # mireds and Duv at +-100, as in the DCTL


def _uv(T):
    u = (0.860117757 + 1.54118254e-4 * T + 1.28641212e-7 * T * T) / (1 + 8.42420235e-4 * T + 7.08145163e-7 * T * T)
    v = (0.317398726 + 4.22806245e-5 * T + 4.20481691e-8 * T * T) / (1 - 2.89741816e-5 * T + 1.61456053e-7 * T * T)
    return u, v


def _white(mired, duv):
    T = 1e6 / mired
    u, v = _uv(T)
    u1, v1 = _uv(T * 1.01)
    du, dv = u1 - u, v1 - v
    n = np.hypot(du, dv)
    nu, nv = -dv / n, du / n
    flip = nv < 0
    nu, nv = np.where(flip, -nu, nu), np.where(flip, -nv, nv)
    u, v = u + duv * nu, v + duv * nv
    d = 2 * u - 8 * v + 4
    x, y = 3 * u / d, 2 * v / d
    return np.stack([x / y, np.ones_like(x), (1 - x - y) / y], axis=-1)


def matrices(temp, tint):
    """3 x 3 white-balance matrices (linear Rec.709) for arrays of Temp and Tint, shape (..., 3, 3)."""
    temp, tint = np.broadcast_arrays(np.asarray(temp, float), np.asarray(tint, float))
    ws = _white(REF_MIRED - TEMP_SPAN * temp / 100.0, TINT_SPAN * tint / 100.0)
    wd = _white(np.full_like(temp, REF_MIRED), np.zeros_like(tint))
    k = (wd @ M16.T) / (ws @ M16.T)
    M = np.einsum("ik,...k,kj->...ij", A, k, B)
    y = np.einsum("i,...ij,j->...", LUMA, M, np.ones(3))
    return M / y[..., None, None]


def solve_cast(cast, keep=0.15, step=1.0):
    """Temp and Tint that leave `keep` of a linear RGB cast (in log chromaticity), by search on a grid."""
    c = np.asarray(cast, float)
    c = c / (LUMA @ c)
    grid = np.arange(-100.0, 100.0 + step / 2, step)
    T, N = np.meshgrid(grid, grid, indexing="ij")
    out = matrices(T, N) @ c
    out = out / np.einsum("i,...i->...", LUMA, out)[..., None]
    want = np.exp(keep * np.log(c))
    want = want / (LUMA @ want)
    err = np.sum((np.log(out) - np.log(want)) ** 2, axis=-1)
    i, j = np.unravel_index(np.argmin(err), err.shape)
    return float(T[i, j]), float(N[i, j]), float(err[i, j])
