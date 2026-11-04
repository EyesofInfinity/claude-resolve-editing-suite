// Develop optics: shared code of Develop Optics, on top of lens.h (bilinear sampling with mirrored edges, linear
// light, the spectrum). MIT License.

#include "../lens/lens.h"

__DEVICE__ float3 mix3o(float3 a, float3 b, float t) { return make_float3(lerp1(a.x, b.x, t), lerp1(a.y, b.y, t), lerp1(a.z, b.z, t)); }

__DEVICE__ float3 crossO(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int r, int w, int h)
{
    float3 a = rgbAt(tr, tg, tb, x, y, w, h), b = rgbAt(tr, tg, tb, x - r, y, w, h), c = rgbAt(tr, tg, tb, x + r, y, w, h);
    float3 d = rgbAt(tr, tg, tb, x, y - r, w, h), e = rgbAt(tr, tg, tb, x, y + r, w, h);
    return make_float3((a.x + b.x + c.x + d.x + e.x) / 5.0f, (a.y + b.y + c.y + d.y + e.y) / 5.0f, (a.z + b.z + c.z + d.z + e.z) / 5.0f);
}

__DEVICE__ float2 sobelO(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int r, int w, int h)
{
    float a = lumaAt(tr, tg, tb, x - r, y - r, w, h), b = lumaAt(tr, tg, tb, x, y - r, w, h), c = lumaAt(tr, tg, tb, x + r, y - r, w, h);
    float d = lumaAt(tr, tg, tb, x - r, y, w, h), f = lumaAt(tr, tg, tb, x + r, y, w, h);
    float g = lumaAt(tr, tg, tb, x - r, y + r, w, h), k = lumaAt(tr, tg, tb, x, y + r, w, h), m = lumaAt(tr, tg, tb, x + r, y + r, w, h);
    return make_float2(((c + 2.0f * f + m) - (a + 2.0f * d + g)) / 4.0f, ((g + 2.0f * k + m) - (a + 2.0f * b + c)) / 4.0f);
}

__DEVICE__ float wrapHalfO(float d) { return d - 3.1415927f * _floorf(d / 3.1415927f + 0.5f); }

__DEVICE__ float2 flowO(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int r, int s, float a0, float eps, int w, int h)
{
    float jxx = 0.0f, jyy = 0.0f, jxy = 0.0f;
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            float2 g = sobelO(tr, tg, tb, x + i * s, y + j * s, r, w, h);
            jxx += g.x * g.x; jyy += g.y * g.y; jxy += g.x * g.y;
        }
    }
    float c2 = jxx - jyy, s2 = 2.0f * jxy, en = jxx + jyy;
    float coh = _sqrtf(c2 * c2 + s2 * s2) / (en + 1e-6f);
    float wf = sstep(0.30f, 0.75f, coh) * sstep(0.5f * eps, 3.0f * eps, en);
    return make_float2(0.5f * _atan2f(-s2, -c2), wf);
}

__DEVICE__ float grooveO(float dx, float dy, float ang, float sc, float z, uint s)
{
    float qa = ang / 0.2617994f, q0 = _floorf(qa), t = qa - q0;
    float a0 = q0 * 0.2617994f, a1 = a0 + 0.2617994f;
    float c0 = _cosf(a0), s0 = _sinf(a0), c1 = _cosf(a1), s1 = _sinf(a1);
    float g0 = vnoise3((-dx * s0 + dy * c0) / (1.1f * sc) + 4096.0f, (dx * c0 + dy * s0) / (9.0f * sc) + 4096.0f, z, s);
    float g1 = vnoise3((-dx * s1 + dy * c1) / (1.1f * sc) + 4096.0f, (dx * c1 + dy * s1) / (9.0f * sc) + 4096.0f, z, s);
    return _saturatef(0.5f + (lerp1(g0, g1, t) - 0.5f) / _sqrtf(t * t + (1.0f - t) * (1.0f - t)));
}

__DEVICE__ float licO(float fx, float fy, float ca, float sa, float step, int n, float g, uint s)
{
    float acc = 0.0f;
    for (int k = -8; k <= 8; k++) {
        if (k < -n || k > n) continue;
        float px = fx + (float)(k) * step * ca, py = fy + (float)(k) * step * sa;
        acc += vnoise3(px / g + 4096.0f, py / g + 4096.0f, 0.5f, s);
    }
    float m = acc / (float)(2 * n + 1);
    return _saturatef(0.5f + (m - 0.5f) * 0.55f * _sqrtf((float)(2 * n + 1)));
}

__DEVICE__ float licTurnO(float fx, float fy, float ang, float step, int n, float g, uint s)
{
    float qa = ang / 0.2617994f, q0 = _floorf(qa), t = qa - q0;
    float a0 = q0 * 0.2617994f, a1 = a0 + 0.2617994f;
    float l0 = licO(fx, fy, _cosf(a0), _sinf(a0), step, n, g, s), l1 = licO(fx, fy, _cosf(a1), _sinf(a1), step, n, g, s);
    return _saturatef(0.5f + (lerp1(l0, l1, t) - 0.5f) / _sqrtf(t * t + (1.0f - t) * (1.0f - t)));
}

__DEVICE__ float toothO(float fx, float fy, float sc, uint s)
{
    float a = vnoise3(fx / (1.7f * sc) + 4096.0f, fy / (1.4f * sc) + 4096.0f, 0.25f, s);
    float b = vnoise3(fx / (4.5f * sc) + 4096.0f, fy / (6.0f * sc) + 4096.0f, 0.75f, s + 1u);
    return _saturatef(0.62f * a + 0.38f * b);
}

__DEVICE__ float3 discLinO(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float fx, float fy, float r, int n, float rot, int w, int h)
{
    float ar = 0.0f, ag = 0.0f, ab = 0.0f;
    for (int i = 0; i < 64; i++) {
        if (i >= n) break;
        float q = _sqrtf(((float)(i) + 0.5f) / (float)(n)), an = 2.3999632f * (float)(i) + rot;
        float3 c = linL(tr, tg, tb, fx + r * q * _cosf(an), fy + r * q * _sinf(an), w, h);
        ar += c.x; ag += c.y; ab += c.z;
    }
    return make_float3(ar / (float)(n), ag / (float)(n), ab / (float)(n));
}

__DEVICE__ float3 chalkO(float3 c, float col)
{
    float L = luma(c.x, c.y, c.z);
    float Lp = 0.08f + 0.86f * _powf(_saturatef(L), 0.80f);
    float k = _fminf(Lp / _fmaxf(L, 0.03f), 1.4f) * (0.85f + 0.4f * col);
    return make_float3(_saturatef(Lp + (c.x - L) * k), _saturatef(Lp + (c.y - L) * k), _saturatef(Lp + (c.z - L) * k));
}

__DEVICE__ float4 strokeLayerO(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float fx, float fy, float g, float a0,
                               float3 pc, float pr, float tooth, float sc, uint s, int w, int h)
{
    int ix = (int)(_floorf(fx / g)), iy = (int)(_floorf(fy / g));
    float p1 = -9.0f, e1 = 0.0f, z1 = 0.0f, x1 = 0.0f, y1 = 0.0f, n1 = 0.0f;
    float p2 = -9.0f, e2 = 0.0f, z2 = 0.0f, x2 = 0.0f, y2 = 0.0f, n2 = 0.0f;
    float p3 = -9.0f, e3 = 0.0f, z3 = 0.0f, x3 = 0.0f, y3 = 0.0f, n3 = 0.0f;
    float3 k1 = pc, k2 = pc, k3 = pc;
    int r = (int)(4.0f * sc + 0.5f);
    if (r < 1) r = 1;
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            int cx = ix + i, cy = iy + j;
            float px = ((float)(cx) + 0.5f + 0.5f * (rnd3(cx, cy, s) - 0.5f)) * g;
            float py = ((float)(cy) + 0.5f + 0.5f * (rnd3(cx, cy, s + 1u) - 0.5f)) * g;
            float2 gr = sobelO(tr, tg, tb, (int)(px), (int)(py), r, w, h);
            float ha = a0 + (fbm(px / (120.0f * sc), py / (120.0f * sc), 0.0f, 2, s + 2u) - 0.5f) * 1.2f + (rnd3(cx, cy, s + 3u) - 0.5f) * 0.35f;
            float ew = sstep(0.003f, 0.030f, gr.x * gr.x + gr.y * gr.y);
            float sa0 = ha + wrapHalfO(_atan2f(gr.y, gr.x) + 1.5707963f - ha) * ew;
            float ca = _cosf(sa0), sa = _sinf(sa0);
            float dx = fx - px, dy = fy - py;
            float u = dx * ca + dy * sa, v = -dx * sa + dy * ca;
            float e = (u * u) / (1.44f * g * g) + (v * v) / (0.25f * g * g);
            if (e >= 1.0f) continue;
            float3 c1 = bilL(tr, tg, tb, px - 0.6f * g * ca, py - 0.6f * g * sa, w, h);
            float3 c2c = bilL(tr, tg, tb, px, py, w, h);
            float3 c3 = bilL(tr, tg, tb, px + 0.6f * g * ca, py + 0.6f * g * sa, w, h);
            float3 c = make_float3((c1.x + 2.0f * c2c.x + c3.x) * 0.25f, (c1.y + 2.0f * c2c.y + c3.y) * 0.25f, (c1.z + 2.0f * c2c.z + c3.z) * 0.25f);
            float df = _fabs(c.x - pc.x) + _fabs(c.y - pc.y) + _fabs(c.z - pc.z);
            float dz = rnd3(cx, cy, s + 4u);
            float pri = dz - 3.0f * df - 0.6f * sstep(0.4f, 1.0f, e) + 0.35f * (tooth - 0.5f);
            if (pri > p1) {
                p3 = p2; e3 = e2; z3 = z2; x3 = x2; y3 = y2; n3 = n2; k3 = k2;
                p2 = p1; e2 = e1; z2 = z1; x2 = x1; y2 = y1; n2 = n1; k2 = k1;
                p1 = pri; e1 = e; z1 = dz; x1 = dx; y1 = dy; n1 = sa0; k1 = c;
            } else if (pri > p2) {
                p3 = p2; e3 = e2; z3 = z2; x3 = x2; y3 = y2; n3 = n2; k3 = k2;
                p2 = pri; e2 = e; z2 = dz; x2 = dx; y2 = dy; n2 = sa0; k2 = c;
            } else if (pri > p3) {
                p3 = pri; e3 = e; z3 = dz; x3 = dx; y3 = dy; n3 = sa0; k3 = c;
            }
        }
    }
    if (p1 < -8.0f) return make_float4(pc.x, pc.y, pc.z, 0.0f);
    float w2 = p2 < -8.0f ? 0.0f : _expf((p2 - p1) / 0.04f), w3 = p3 < -8.0f ? 0.0f : _expf((p3 - p1) / 0.04f);
    float q1 = pr * (1.0f - sstep(0.45f, 1.0f, e1));
    float v1 = sstep(1.0f - q1 - 0.12f, 1.0f - q1 + 0.12f, 0.55f * tooth + 0.45f * grooveO(x1, y1, n1, sc, z1 * 50.0f, s + 5u));
    float v2 = 0.0f, v3 = 0.0f;
    if (w2 > 0.002f) {
        float q2 = pr * (1.0f - sstep(0.45f, 1.0f, e2));
        v2 = sstep(1.0f - q2 - 0.12f, 1.0f - q2 + 0.12f, 0.55f * tooth + 0.45f * grooveO(x2, y2, n2, sc, z2 * 50.0f, s + 5u));
    }
    if (w3 > 0.002f) {
        float q3 = pr * (1.0f - sstep(0.45f, 1.0f, e3));
        v3 = sstep(1.0f - q3 - 0.12f, 1.0f - q3 + 0.12f, 0.55f * tooth + 0.45f * grooveO(x3, y3, n3, sc, z3 * 50.0f, s + 5u));
    }
    float ws = 1.0f + w2 + w3;
    return make_float4((k1.x + w2 * k2.x + w3 * k3.x) / ws, (k1.y + w2 * k2.y + w3 * k3.y) / ws, (k1.z + w2 * k2.z + w3 * k3.z) / ws,
                       (v1 + w2 * v2 + w3 * v3) / ws);
}

__DEVICE__ float lumaSO(float3 c) { return luma(_saturatef(c.x), _saturatef(c.y), _saturatef(c.z)); }

__DEVICE__ int greenOverO(__TEXTURE__ tg, float fx, float fy, float g, int w, int h)
{
    int x0 = (int)(_floorf(fx)), y0 = (int)(_floorf(fy));
    if (x0 < -1 || y0 < -1 || x0 >= w || y0 >= h) return 2;
    int xa = clampi(x0, 0, w - 1), xb = clampi(x0 + 1, 0, w - 1), ya = clampi(y0, 0, h - 1), yb = clampi(y0 + 1, 0, h - 1);
    if (_tex2D(tg, xa, ya) > g || _tex2D(tg, xb, ya) > g) return 1;
    return (_tex2D(tg, xa, yb) > g || _tex2D(tg, xb, yb) > g) ? 1 : 0;
}

__DEVICE__ float pointO(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float cx, float cy, float L, float rr, int w, int h)
{
    float lim = 0.65f * L;
    float ln = 0.0f, ro = 4.5f * rr;
    for (int i = 0; i < 6; i++) {
        float a = 1.0471976f * (float)(i) + 0.3f;
        ln = _fmaxf(ln, lumaSO(bilL(tr, tg, tb, cx + ro * _cosf(a), cy + ro * _sinf(a), w, h)));
        if (ln >= lim) return 0.0f;
    }
    float hi = 0.0f, lo = 9.0f;
    for (int i = 0; i < 6; i++) {
        float a = 1.0471976f * (float)(i) + 0.7f;
        float lq = lumaSO(bilL(tr, tg, tb, cx + rr * _cosf(a), cy + rr * _sinf(a), w, h));
        hi = _fmaxf(hi, lq); lo = _fminf(lo, lq);
    }
    float mixd = sstep(0.75f, 0.90f, hi / L) * (1.0f - sstep(0.55f, 0.75f, lo / L));
    return sstep(0.35f, 0.60f, 1.0f - ln / L) * (1.0f - mixd);
}

__DEVICE__ float3 starTapO(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float fx, float fy, float rr, float thr, int w, int h)
{
    float bx = _floorf(fx), by = _floorf(fy);
    float ax = fx - bx, ay = fy - by, band = _fmaxf(1.0f - thr, 0.02f);
    int x0 = (int)(bx), y0 = (int)(by), px = x0, py = y0;
    float er = 0.0f, eg = 0.0f, eb = 0.0f, best = -1.0f;
    for (int k = 0; k < 4; k++) {
        int kx = k & 1, ky = k >> 1;
        float wt = (kx == 1 ? ax : 1.0f - ax) * (ky == 1 ? ay : 1.0f - ay);
        int mx = mirL(x0 + kx, w), my = mirL(y0 + ky, h);
        float r = _saturatef(_tex2D(tr, mx, my)), g = _saturatef(_tex2D(tg, mx, my)), b = _saturatef(_tex2D(tb, mx, my));
        float L = luma(r, g, b);
        if (L > best) { best = L; px = x0 + kx; py = y0 + ky; }
        if (L > thr) {
            float e = wt * (L - thr) / band;
            er += toLin(r) * e; eg += toLin(g) * e; eb += toLin(b) * e;
        }
    }
    if (er + eg + eb <= 0.0f) return make_float3(0.0f, 0.0f, 0.0f);
    float pt = pointO(tr, tg, tb, (float)(px), (float)(py), best, rr, w, h);
    if (pt <= 0.0f) return make_float3(0.0f, 0.0f, 0.0f);
    float nf = 0.0f;
    for (int i = 0; i < 8; i++) {
        float a = 0.7853982f * (float)(i) + 0.2f;
        float lq = lumaSO(bilL(tr, tg, tb, (float)(px) + 9.0f * rr * _cosf(a), (float)(py) + 9.0f * rr * _sinf(a), w, h));
        nf += sstep(thr - 0.06f, thr + 0.02f, lq);
    }
    pt *= 1.0f - 0.9f * sstep(0.0f, 0.5f, nf / 8.0f);
    float k = pt * pt * _saturatef((best - thr) / band);
    return make_float3(er * k, eg * k, eb * k);
}

__DEVICE__ float boxSDO(float px, float py, float hx, float hy, float rr)
{
    float qx = _fabs(px) - hx + rr, qy = _fabs(py) - hy + rr;
    float ox = _fmaxf(qx, 0.0f), oy = _fmaxf(qy, 0.0f);
    return _sqrtf(ox * ox + oy * oy) + _fminf(_fmaxf(qx, qy), 0.0f) - rr;
}
