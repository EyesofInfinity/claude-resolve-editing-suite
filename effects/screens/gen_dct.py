"""Write jpeg.h: the 8 x 8 DCT code of Develop Screen's JPEG Damage, written out in full because a DCTL here
holds no local arrays (the CPU harness reads none either), so each block's 64 samples and 64 coefficients are named.

The code is baseline JPEG (ITU T.81): samples level-shifted by 128, the orthonormal 8 x 8 DCT-II, the standard
luminance and chrominance quantisation tables of Annex K scaled as the IJG encoder scales them for a quality, and the
decoder's inverse DCT evaluated at one pixel of the block. Rounding to the quantiser's step is a soft staircase
(softRound): flat over most of each step and steep only at its edge, so a float picture and an 8-bit still of it land
on the same coefficients.

usage: python -I gen_dct.py      (writes jpeg.h beside it)
"""
import math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))

QY = [16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56,
      14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
      49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99]
QC = [17, 18, 24, 47, 99, 99, 99, 99, 18, 21, 26, 66, 99, 99, 99, 99, 24, 26, 56, 99, 99, 99, 99, 99,
      47, 66, 99, 99, 99, 99, 99, 99] + [99] * 32

def basis(n, k):
    c = math.sqrt(0.5) if k == 0 else 1.0
    return 0.5 * c * math.cos((2 * n + 1) * k * math.pi / 16.0)

def lit(v):
    s = f"{v:.8f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    return s + "f"

def table(name, vals):
    rows = [", ".join(lit(v) for v in vals[i:i + 8]) for i in range(0, 64, 8)]
    return f"__CONSTANT__ float {name}[64] = {{\n    " + ",\n    ".join(rows) + "};\n"

def dct(prefix, src):
    """lines computing <prefix>F<v><u> from samples src(y, x) (names), rows first then columns"""
    L = []
    for y in range(8):
        for u in range(8):
            terms = " + ".join(f"{src(y, x)} * {lit(basis(x, u))}" for x in range(8))
            L.append(f"    float {prefix}t{y}{u} = {terms};")
    for v in range(8):
        for u in range(8):
            terms = " + ".join(f"{prefix}t{y}{u} * {lit(basis(y, v))}" for y in range(8))
            L.append(f"    float {prefix}F{v}{u} = {terms};")
    return L

def quant(prefix, tab, qs, garb, seed):
    return [f"    {prefix}F{v}{u} = qz({prefix}F{v}{u}, {tab}[{v * 8 + u}] * {qs}, {garb}, {seed}, {v * 8 + u});"
            for v in range(8) for u in range(8)]

def inverse(prefix):
    L = []
    for v in range(8):
        terms = " + ".join(f"{prefix}F{v}{u} * DCTB[px * 8 + {u}]" for u in range(8))
        L.append(f"    float {prefix}r{v} = {terms};")
    L.append(f"    float {prefix}out = " + " + ".join(f"{prefix}r{v} * DCTB[py * 8 + {v}]" for v in range(8)) + ";")
    return L

def main():
    o = []
    o.append("// Develop Screen's JPEG code, written by gen_dct.py: do not edit by hand, run python -I gen_dct.py.")
    o.append("// Baseline JPEG (ITU T.81): level shift by 128, the orthonormal 8 x 8 DCT, the Annex K tables scaled for a")
    o.append("// quality, and the decoder's inverse DCT at one pixel. Samples are BT.601 YCbCr from display values, as JFIF")
    o.append("// takes them. A pixel computes its own block (64 luma samples, 64 chroma samples of 2 x 2 cells each). MIT License.")
    o.append("")
    o.append("// DCTB[n * 8 + k]: the orthonormal basis, 0.5 c(k) cos((2n + 1) k pi / 16), c(0) = 1 / sqrt 2")
    o.append(table("DCTB", [basis(n, k) for n in range(8) for k in range(8)]))
    o.append("// the Annex K luminance and chrominance tables, row v then column u")
    o.append(table("QY", QY))
    o.append(table("QC", QC))
    o.append("""// a soft staircase: v rounded to the nearest whole number, flat over most of the step and steep at its edge
// (the steepness k), continuous everywhere, so a sample that moves a hair moves its coefficient a hair
__DEVICE__ float softRound(float v, float k)
{
    float n = _floorf(v + 0.5f), t = v - n;
    return n + 0.5f * _copysignf(_powf(_fabs(2.0f * t), k), t);
}

// one coefficient through the quantiser of step q; garb above 0 adds the random values a decoder reads after a bit
// error in the entropy-coded data (largest in the low frequencies)
__DEVICE__ float qz(float F, float q, float garb, uint gs, int k)
{
    float qq = _fmaxf(q, 1.0f);
    float v = qq * softRound(F / qq, KSTEEP);
    if (garb > 0.0f) {
        int u = k & 7, vv = k >> 3;
        v += garb * (hash01((uint)(k) + 1u, gs, 71u) - 0.5f) * 840.0f / (1.0f + (float)(u + vv));
    }
    return v;
}

// BT.601 luma of a display sample, 0 to 255, level-shifted
__DEVICE__ float jY(float3 c)
{
    return 255.0f * (0.299f * _saturatef(c.x) + 0.587f * _saturatef(c.y) + 0.114f * _saturatef(c.z)) - 128.0f;
}

// one chroma sample: the mean of four cells of bs pixels (2 x 2 subsampling, as 4:2:0), Cb and Cr centred on 0
__DEVICE__ float2 jC(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float fx, float fy, float bs, int w, int h)
{
    float3 a = bilL(tr, tg, tb, fx, fy, w, h), b = bilL(tr, tg, tb, fx + bs, fy, w, h);
    float3 c = bilL(tr, tg, tb, fx, fy + bs, w, h), d = bilL(tr, tg, tb, fx + bs, fy + bs, w, h);
    float r = 0.25f * (_saturatef(a.x) + _saturatef(b.x) + _saturatef(c.x) + _saturatef(d.x));
    float g = 0.25f * (_saturatef(a.y) + _saturatef(b.y) + _saturatef(c.y) + _saturatef(d.y));
    float bl = 0.25f * (_saturatef(a.z) + _saturatef(b.z) + _saturatef(c.z) + _saturatef(d.z));
    return make_float2(255.0f * (-0.168736f * r - 0.331264f * g + 0.5f * bl), 255.0f * (0.5f * r - 0.418688f * g - 0.081312f * bl));
}
""")
    o.append("// the luma block whose top left pixel is (ox, oy), each sample the mean of a cell of bs x bs pixels (a picture")
    o.append("// shrunk by bs before coding), decoded at sample (px, py); 0 to 255")
    o.append("__DEVICE__ float jpegY(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float ox, float oy, float bs, int w, int h, int px, int py, float qs, float garb, uint gs)")
    o.append("{")
    o.append("    float hb = 0.5f * (bs - 1.0f);")
    for y in range(8):
        for x in range(8):
            o.append(f"    float p{y}{x} = jY(bilL(tr, tg, tb, ox + {x}.0f * bs + hb, oy + {y}.0f * bs + hb, w, h));")
    o += dct("", lambda y, x: f"p{y}{x}")
    o += quant("", "QY", "qs", "garb", "gs")
    o += inverse("")
    o.append("    return out + 128.0f;")
    o.append("}")
    o.append("")
    o.append("// the chroma blocks of the MCU whose top left pixel is (ox, oy): 8 x 8 samples over 16 x 16 cells of bs pixels,")
    o.append("// decoded at sample (px, py) and shown at that sample's whole 2 x 2 cells; Cb and Cr centred on 0")
    o.append("__DEVICE__ float2 jpegC(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float ox, float oy, float bs, int w, int h, int px, int py, float qs, float garb, uint gs)")
    o.append("{")
    o.append("    float hb = 0.5f * (bs - 1.0f);")
    for y in range(8):
        for x in range(8):
            o.append(f"    float2 s{y}{x} = jC(tr, tg, tb, ox + {2 * x}.0f * bs + hb, oy + {2 * y}.0f * bs + hb, bs, w, h);")
    o += dct("b", lambda y, x: f"s{y}{x}.x")
    o += dct("r", lambda y, x: f"s{y}{x}.y")
    o += quant("b", "QC", "qs", "garb", "gs")
    o += quant("r", "QC", "qs", "garb", "gs + 7u")
    o += inverse("b")
    o += inverse("r")
    o.append("    return make_float2(bout, rout);")
    o.append("}")
    t = "\n".join(o) + "\n"
    k = sys.argv[sys.argv.index("--k") + 1] if "--k" in sys.argv else "64"
    t = t.replace("KSTEEP", lit(float(k)))
    open(os.path.join(HERE, "jpeg.h"), "w", encoding="utf-8", newline="\n").write(t)
    print(os.path.join(HERE, "jpeg.h"))

if __name__ == "__main__":
    main()
