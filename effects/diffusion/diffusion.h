// Develop diffusion: shared code of Develop Diffusion, on top of lens.h (mirrored edges, linear light, the
// hash and value noise). Every wide gather here reads stratified rings of taps: each ring is turned by its own angle
// and the whole set of rings is turned and slid outward per pixel, so what a finite set of taps leaves behind is a
// fine grain and never a ring, a ladder or a ghost copy. MIT License.

#include "../lens/lens.h"

__DEVICE__ float ignD(float x, float y)
{
    float f = 0.06711056f * x + 0.00583715f * y;
    f = f - _floorf(f);
    f = 52.9829189f * f;
    return f - _floorf(f);
}

__DEVICE__ float4 tapD(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float fx, float fy, float pre, int w, int h)
{
    float bx = _floorf(fx), by = _floorf(fy);
    float ax = fx - bx, ay = fy - by;
    int x0 = (int)(bx), y0 = (int)(by);
    int xa = mirL(x0, w), xb = mirL(x0 + 1, w), ya = mirL(y0, h), yb = mirL(y0 + 1, h);
    float g00 = _saturatef(_tex2D(tg, xa, ya)), g10 = _saturatef(_tex2D(tg, xb, ya));
    float g01 = _saturatef(_tex2D(tg, xa, yb)), g11 = _saturatef(_tex2D(tg, xb, yb));
    float r00 = _saturatef(_tex2D(tr, xa, ya)), r10 = _saturatef(_tex2D(tr, xb, ya));
    float r01 = _saturatef(_tex2D(tr, xa, yb)), r11 = _saturatef(_tex2D(tr, xb, yb));
    if (pre >= 0.0f) {
        float mx = _fmaxf(_fmaxf(_fmaxf(g00, g10), _fmaxf(g01, g11)), _fmaxf(_fmaxf(r00, r10), _fmaxf(r01, r11)));
        if (mx < pre) return make_float4(0.0f, 0.0f, 0.0f, 0.0f);
    }
    float b00 = _saturatef(_tex2D(tb, xa, ya)), b10 = _saturatef(_tex2D(tb, xb, ya));
    float b01 = _saturatef(_tex2D(tb, xa, yb)), b11 = _saturatef(_tex2D(tb, xb, yb));
    float r = lerp1(lerp1(r00, r10, ax), lerp1(r01, r11, ax), ay);
    float g = lerp1(lerp1(g00, g10, ax), lerp1(g01, g11, ax), ay);
    float b = lerp1(lerp1(b00, b10, ax), lerp1(b01, b11, ax), ay);
    return make_float4(r, g, b, 1.0f);
}

__DEVICE__ float3 veilD(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float fx, float fy, float sg, float sA, float sH,
                        float thr, float pk, int w, int h)
{
    float g = sg / 1.4f, lo = thr - 0.04f, rw = 2.6f * sg;
    int nx = (int)((float)(w) / g) + 1, ny = (int)((float)(h) / g) + 1;
    int i0 = clampi((int)(_floorf((fx - rw) / g)), 0, nx - 1), i1 = clampi((int)(_floorf((fx + rw) / g)) + 1, 0, nx - 1);
    int j0 = clampi((int)(_floorf((fy - rw) / g)), 0, ny - 1), j1 = clampi((int)(_floorf((fy + rw) / g)) + 1, 0, ny - 1);
    float ar = 0.0f, ag = 0.0f, ab = 0.0f, ws = 0.0f, c2 = 0.5f / (sg * sg), q = 0.3f * g;
    for (int j = 0; j < 24; j++) {
        if (j0 + j > j1) break;
        for (int i = 0; i < 24; i++) {
            if (i0 + i > i1) break;
            float qx = ((float)(i0 + i) + 0.5f) * g, qy = ((float)(j0 + j) + 0.5f) * g;
            float dx = qx - fx, dy = qy - fy, d2 = dx * dx + dy * dy;
            if (d2 >= rw * rw) continue;
            float wt = _expf(-d2 * c2) * (1.0f - sstep(2.0f * sg, rw, _sqrtf(d2)));
            float nr = 0.0f, ng = 0.0f, nb = 0.0f;
            for (int k = 0; k < 5; k++) {
                float ox = k == 0 ? 0.0f : ((k & 1) == 1 ? -q : q), oy = k == 0 ? 0.0f : (k < 3 ? -q : q);
                float4 t = tapD(tr, tg, tb, qx + ox, qy + oy, -1.0f, w, h);
                float lr = toLin(t.x), lg = toLin(t.y), lb = toLin(t.z);
                float e = sstep(lo, 1.0f, luma(t.x, t.y, t.z));
                float f = sA + sH * e * pk;
                nr += lr * f; ng += lg * f; nb += lb * f;
            }
            ar += wt * nr; ag += wt * ng; ab += wt * nb; ws += wt * 5.0f;
        }
    }
    return make_float3(ar / _fmaxf(ws, 1e-20f), ag / _fmaxf(ws, 1e-20f), ab / _fmaxf(ws, 1e-20f));
}

__DEVICE__ float kernD(int kind, float r, float p1, float p2)
{
    if (kind == 0) return _powf(r * r + p1 * p1, -0.5f * p2);
    if (kind == 1) return _expf(-0.5f * r * r / (p1 * p1));
    if (kind == 2) return 1.0f - sstep(p1 * (1.0f - p2), p1, r);
    if (kind == 3) {
        float q = (r - p1) / p2, a = r / (0.45f * p1);
        return _expf(-0.5f * q * q) + 0.30f * _expf(-0.5f * a * a);
    }
    return _expf(-r / p1);
}

__DEVICE__ float3 gatherD(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float fx, float fy, int kind, float p1, float p2,
                          int place, float rA, float rB, int nR, int nT, float sA, float sH, float thr, float pk, float disp,
                          float rot, float jit, int aEvery, int guard, int w, int h)
{
    float ar = 0.0f, ag = 0.0f, ab = 0.0f, war = 0.0f, wag = 0.0f, wab = 0.0f;
    float hr = 0.0f, hg = 0.0f, hb = 0.0f, whr = 0.0f, whg = 0.0f, whb = 0.0f, hs = 0.0f, hq = 0.0f;
    float lq = _logf(rB / rA), dA = 6.2831853f / (float)(nT), cd = _cosf(dA), sd = _sinf(dA);
    float lo = thr - 0.04f;
    float pre = _fmaxf((lo - 0.0722f) / 0.9278f, 0.0f);
    float er = 1.0f / (1.0f + disp), eb = 1.0f / _fmaxf(1.0f - disp, 0.2f);
    for (int m = 0; m < 48; m++) {
        if (m >= nR) break;
        float u = ((float)(m) + jit) / (float)(nR);
        float r = place == 0 ? rA * _expf(lq * u) : _sqrtf(rA * rA + (rB * rB - rA * rA) * u);
        float aw = (place == 0 ? r * r : 1.0f) * (1.0f - sstep(0.8f * rB, rB, r));
        float kg = kernD(kind, r, p1, p2) * aw, kr = kg, kb = kg;
        if (disp != 0.0f) { kr = kernD(kind, r * er, p1, p2) * aw; kb = kernD(kind, r * eb, p1, p2) * aw; }
        float gq = 0.618034f * (float)(m);
        float a0 = rot + dA * (gq - _floorf(gq));
        float c = _cosf(a0), s = _sinf(a0);
        for (int i = 0; i < 32; i++) {
            if (i >= nT) break;
            int doA = (sA > 0.0f && (i + m) % aEvery == 0) ? 1 : 0;
            float4 t = tapD(tr, tg, tb, fx + r * c, fy + r * s, doA == 1 ? -1.0f : pre, w, h);
            whr += kr; whg += kg; whb += kb;
            if (doA == 1) { war += kr; wag += kg; wab += kb; }
            if (t.w > 0.0f) {
                float lr = toLin(t.x), lg = toLin(t.y), lb = toLin(t.z);
                if (doA == 1) { ar += kr * lr; ag += kg * lg; ab += kb * lb; }
                float e = sstep(lo, 1.0f, luma(t.x, t.y, t.z));
                if (e > 0.0f) {
                    e *= pk;
                    hr += kr * lr * e; hg += kg * lg * e; hb += kb * lb * e;
                    float v = kg * luma(lr, lg, lb) * e;
                    hs += v; hq += v * v;
                }
            }
            float c2 = c * cd - s * sd;
            s = s * cd + c * sd; c = c2;
        }
    }
    float gd = 1.0f;
    if (guard == 1) gd = sstep(1.6f, 4.0f, hs * hs / _fmaxf(hq, 1e-20f));
    float oa = sA / _fmaxf(wag, 1e-20f), oh = sH * gd / _fmaxf(whg, 1e-20f);
    float rr = (war > 0.0f ? sA * ar / war : 0.0f) + (whr > 0.0f ? sH * gd * hr / whr : 0.0f);
    float bb = (wab > 0.0f ? sA * ab / wab : 0.0f) + (whb > 0.0f ? sH * gd * hb / whb : 0.0f);
    return make_float3(rr, ag * oa + hg * oh, bb);
}

__DEVICE__ float3 armsD(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float fx, float fy, float ang, int nAx, float len,
                        float lam, float sA, float sH, float thr, float pk, float disp, float jit, int w, int h)
{
    float ar = 0.0f, ag = 0.0f, ab = 0.0f, hr = 0.0f, hg = 0.0f, hb = 0.0f, wr = 0.0f, wg = 0.0f, wb = 0.0f;
    float lo = thr - 0.04f;
    float pre = sA > 0.0f ? -1.0f : _fmaxf((lo - 0.0722f) / 0.9278f, 0.0f);
    int nL = (int)(len);
    float lr0 = lam * (1.0f + disp), lb0 = lam * _fmaxf(1.0f - disp, 0.2f);
    for (int a = 0; a < 6; a++) {
        if (a >= 2 * nAx) break;
        float an = ang + 3.1415927f * (float)(a) / (float)(nAx);
        float ca = _cosf(an), sa = _sinf(an);
        for (int j = 0; j < 128; j++) {
            if (j >= nL) break;
            float d = (float)(j) + 0.5f + jit;
            float kg = _expf(-d / lam), kr = _expf(-d / lr0), kb = _expf(-d / lb0);
            float o = 0.3f + 0.035f * d;
            for (int q = 0; q < 5; q++) {
                float of = (float)(q - 2) * o, wq = (float)(3 - (q > 2 ? q - 2 : 2 - q)) / 9.0f;
                float4 t = tapD(tr, tg, tb, fx + d * ca - of * sa, fy + d * sa + of * ca, pre, w, h);
                if (t.w > 0.0f) {
                    float lr = toLin(t.x), lg = toLin(t.y), lb = toLin(t.z);
                    float e = sstep(lo, 1.0f, luma(t.x, t.y, t.z)) * pk;
                    ar += wq * kr * lr; ag += wq * kg * lg; ab += wq * kb * lb;
                    hr += wq * kr * lr * e; hg += wq * kg * lg * e; hb += wq * kb * lb * e;
                }
            }
            wr += kr; wg += kg; wb += kb;
        }
    }
    return make_float3((sA * ar + sH * hr) / _fmaxf(wr, 1e-20f), (sA * ag + sH * hg) / _fmaxf(wg, 1e-20f), (sA * ab + sH * hb) / _fmaxf(wb, 1e-20f));
}

__DEVICE__ float3 tintD(float3 g, float t, float sat)
{
    float y = luma(g.x, g.y, g.z);
    float r = lerp1(y, g.x, sat) * (1.0f + 0.22f * t), gg = lerp1(y, g.y, sat) * (1.0f + 0.02f * t), b = lerp1(y, g.z, sat) * (1.0f - 0.30f * t);
    float k = y / _fmaxf(luma(r, gg, b), 1e-12f);
    return make_float3(r * k, gg * k, b * k);
}

__DEVICE__ float smokeD(float u, float v, float t, float s, float dx, float dy, float dens, uint seed)
{
    float x = u / s - dx * t, y = v / s - dy * t;
    float wx = 0.0f, wy = 0.0f, f = 0.0f, a = 0.5f, tot = 0.0f, fr = 1.0f;
    for (int i = 0; i < 3; i++) {
        wx += a * vnoise3(x * 0.55f * fr + 4099.1f, y * 0.55f * fr + 4096.0f + 9.3f * (float)(i), t * 0.045f * fr + 4096.0f, seed + (uint)(i));
        wy += a * vnoise3(x * 0.55f * fr + 4096.0f, y * 0.55f * fr + 4103.7f + 5.1f * (float)(i), t * 0.045f * fr + 4096.0f, seed + 9u + (uint)(i));
        tot += a; a *= 0.5f; fr *= 2.03f;
    }
    wx = wx / tot - 0.5f; wy = wy / tot - 0.5f;
    a = 0.5f; tot = 0.0f; fr = 1.0f;
    for (int i = 0; i < 5; i++) {
        f += a * vnoise3((x + 1.6f * wx) * fr + 4096.0f + 37.1f * (float)(i), (y + 1.6f * wy) * fr + 4096.0f + 11.7f * (float)(i), t * 0.07f * fr + 4096.0f, seed + 17u + (uint)(i));
        tot += a; a *= 0.5f; fr *= 2.03f;
    }
    f /= tot;
    return sstep(0.56f - 0.30f * dens, 0.80f - 0.20f * dens, f);
}

__DEVICE__ float3 outD(float r, float g, float b, float lm, float k)
{
    float m = _fmaxf(r, _fmaxf(g, b));
    float kn = _fminf(_fmaxf(0.8f, lm), 0.999f);
    float rr = r, gg = g, bb = b;
    if (m > kn) {
        float nm = kn + (1.0f - kn) * _tanhf((m - kn) / (1.0f - kn));
        float s = nm / m, wh = 0.6f * sstep(1.0f, 3.0f, m), w = _saturatef(k * 4.0f);
        rr = lerp1(r, lerp1(r * s, nm, wh), w); gg = lerp1(g, lerp1(g * s, nm, wh), w); bb = lerp1(b, lerp1(b * s, nm, wh), w);
    }
    return make_float3(_saturatef(toDisp(rr)), _saturatef(toDisp(gg)), _saturatef(toDisp(bb)));
}

__DEVICE__ float3 filmOutD(float r, float g, float b)
{
    float rr = r <= 0.8f ? r : 0.8f + 0.2f * _tanhf((r - 0.8f) / 0.2f);
    float gg = g <= 0.8f ? g : 0.8f + 0.2f * _tanhf((g - 0.8f) / 0.2f);
    float bb = b <= 0.8f ? b : 0.8f + 0.2f * _tanhf((b - 0.8f) / 0.2f);
    return make_float3(_saturatef(toDisp(rr)), _saturatef(toDisp(gg)), _saturatef(toDisp(bb)));
}
