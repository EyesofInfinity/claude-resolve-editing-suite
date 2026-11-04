"""The spectral tables of Develop Filter: writes spectra.h beside this file.

A filter acts on light, wavelength by wavelength. To lay a filter's transmission T(lambda) on a Rec.709 picture, each
linear pixel is read as a surface under daylight: its reflectance is built from three smooth bands (blue below 490 nm,
green, red above 590 nm, summing to one, so a grey pixel is a flat grey surface), lit by CIE D65, seen through the
filter and integrated against the CIE 1931 observer back into linear Rec.709. Since that is linear in the pixel, the
filter is a 3 x 3 matrix M = sum over lambda of T(lambda) G(lambda); the DCTL builds M from T at run time (so Strength
can thicken the filter, T to the power of Strength, as two filters stacked are), and G is written here.

For black and white, the same light falls on a panchromatic film instead of the observer: one row, the film's
exposure from the pixel, sum of T(lambda) F(lambda).

Sources, written from published numbers, nothing downloaded: CIE D65 at 10 nm (interpolated to 5 nm); the CIE 1931
2 degree observer by the multi-lobe Gaussian fit of Wyman, Sloan and Shirley (2013); the XYZ to linear Rec.709 matrix;
a generic panchromatic film sensitivity (the silver halide's own blue band, the sensitising dyes' band to about
655 nm, the shallow green gap between them near 505 nm). Also the colour of Rayleigh skylight (D65 times lambda^-4)
for the polarizer.

usage: python -I spectra.py      (writes spectra.h; prints the checks)
"""
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
L0, STEP, N = 390.0, 5.0, 65
lam = L0 + STEP * np.arange(N)

D65_10 = [49.98, 54.65, 82.75, 91.49, 93.43, 86.68, 104.86, 117.01, 117.81, 114.86, 115.92, 108.81, 109.35, 107.80,
          104.79, 107.69, 104.41, 104.05, 100.00, 96.33, 95.79, 88.69, 90.01, 89.60, 87.70, 83.29, 83.70, 80.03, 80.21,
          82.28, 78.28, 69.72, 71.61, 74.35, 61.60, 69.89, 75.09, 63.59, 46.42, 66.81, 63.38]
E = np.interp(lam, 380 + 10 * np.arange(len(D65_10)), D65_10)

def g(x, mu, s1, s2):
    s = np.where(x < mu, s1, s2)
    return np.exp(-0.5 * ((x - mu) / s) ** 2)

xb = 1.056 * g(lam, 599.8, 37.9, 31.0) + 0.362 * g(lam, 442.0, 16.0, 26.7) - 0.065 * g(lam, 501.1, 20.4, 26.2)
yb = 0.821 * g(lam, 568.8, 46.9, 40.5) + 0.286 * g(lam, 530.9, 16.3, 31.1)
zb = 1.217 * g(lam, 437.0, 11.8, 36.0) + 0.681 * g(lam, 459.0, 26.0, 13.8)
XYZ2RGB = np.array([[3.2404542, -1.5371385, -0.4985314], [-0.9692660, 1.8760108, 0.0415560],
                    [0.0556434, -0.2040259, 1.0572252]])
cam = XYZ2RGB @ np.stack([xb, yb, zb])

sig = lambda v: 1.0 / (1.0 + np.exp(-v))
Bb = 1.0 - sig((lam - 490.0) / 8.0)
Br = sig((lam - 590.0) / 8.0)
Bg = 1.0 - Bb - Br
B = np.stack([Br, Bg, Bb])

K = (cam * E) @ B.T
Dn = 1.0 / K.sum(axis=1)
K = Dn[:, None] * K
Ki = np.linalg.inv(K)
G = np.einsum("il,jl,jk->lik", Dn[:, None] * cam * E, B, Ki)
pan = 0.6 * (1.0 - sig((lam - 505.0) / 10.0)) + 0.9 * sig((lam - 512.0) / 9.0) * (1.0 - sig((lam - 655.0) / 10.0))
F = np.einsum("l,jl,jk->lk", pan * E, B, Ki)
F /= F.sum()
ray = (cam * E * (lam / 550.0) ** -4).sum(axis=1) * Dn
ray /= ray.max()

assert np.allclose(G.sum(axis=0), np.eye(3), atol=1e-9)
white = (cam * E).sum(axis=1)
xyz = np.stack([xb, yb, zb]) @ E
print("D65 white xy", xyz[0] / xyz.sum(), xyz[1] / xyz.sum(), "(0.3127, 0.3290)")
print("white balance gains", Dn / Dn.mean())
print("pan film weights r g b", F.sum(axis=0), "(the eye: 0.2126 0.7152 0.0722)")
print("Rayleigh sky colour", ray)

rows = []
for l in range(N):
    rows.append(", ".join(f"{v:.7g}f" for v in list(G[l].ravel()) + list(F[l])))
out = os.path.join(HERE, "spectra.h")
with open(out, "w", encoding="utf-8", newline="\n") as f:
    f.write("// Develop Filter's spectral tables, written by spectra.py; see there for what they are. One row per\n")
    f.write(f"// wavelength from {L0:.0f} nm in {STEP:.0f} nm steps ({N} rows): the 3 x 3 matrix G row by row, then the\n")
    f.write("// panchromatic film's three weights. MIT License.\n\n")
    f.write(f"__CONSTANT__ float FSPEC[{N * 12}] = {{\n")
    f.write(",\n".join("    " + r for r in rows))
    f.write("};\n")
    f.write(f"__CONSTANT__ float FRAYL[3] = {{{ray[0]:.6f}f, {ray[1]:.6f}f, {ray[2]:.6f}f}};\n")
print(out)
