// Develop glare: shared code of Develop Glare and Develop Glow Plus, on top of lens.h (bilinear reads with
// mirrored edges, light.h's linear light and hash, glitch.h's clamped reads). Rec.709 gamma 2.4 in and out; light is
// added in linear. MIT License.

#include "../lens/lens.h"

__DEVICE__ float3 hueGl(float h)
{
    float k = _fmod(h / 60.0f + 600.0f, 6.0f);
    return make_float3(toLin(_saturatef(_fabs(k - 3.0f) - 1.0f)), toLin(_saturatef(2.0f - _fabs(k - 2.0f))), toLin(_saturatef(2.0f - _fabs(k - 4.0f))));
}

__DEVICE__ float3 waveGl(float t)
{
    if (t < -0.05f || t > 1.05f) return make_float3(0.0f, 0.0f, 0.0f);
    float e = sstep(-0.05f, 0.06f, t) * (1.0f - sstep(0.9f, 1.05f, t));
    float r = _expf(-((t - 0.78f) / 0.14f) * ((t - 0.78f) / 0.14f)) + 0.35f * _expf(-((t - 0.02f) / 0.07f) * ((t - 0.02f) / 0.07f));
    float g = _expf(-((t - 0.50f) / 0.13f) * ((t - 0.50f) / 0.13f));
    float b = _expf(-((t - 0.20f) / 0.12f) * ((t - 0.20f) / 0.12f));
    return make_float3(1.15f * r * e, 1.0f * g * e, 1.25f * b * e);
}

__DEVICE__ float lumaTexGl(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y)
{
    return luma(_saturatef(_tex2D(tr, x, y)), _saturatef(_tex2D(tg, x, y)), _saturatef(_tex2D(tb, x, y)));
}

__DEVICE__ int greenAnyGl(__TEXTURE__ tg, float fx, float fy, float g, int w, int h)
{
    int x0 = (int)(_floorf(fx)), y0 = (int)(_floorf(fy));
    if (x0 < -1 || y0 < -1 || x0 >= w || y0 >= h) return 2;
    int xa = clampi(x0, 0, w - 1), xb = clampi(x0 + 1, 0, w - 1), ya = clampi(y0, 0, h - 1), yb = clampi(y0 + 1, 0, h - 1);
    if (_tex2D(tg, xa, ya) > g || _tex2D(tg, xb, ya) > g) return 1;
    return (_tex2D(tg, xa, yb) > g || _tex2D(tg, xb, yb) > g) ? 1 : 0;
}

__DEVICE__ float ringDarkGl(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, float rad, float a0, float lim, int w, int h)
{
    float ring = 0.0f;
    for (int i = 0; i < 8; i++) {
        float a = 0.7853982f * (float)(i) + a0;
        int sx = mirL(x + (int)(_round(rad * _cosf(a))), w), sy = mirL(y + (int)(_round(rad * _sinf(a))), h);
        float q = lumaTexGl(tr, tg, tb, sx, sy);
        float bq = sstep(0.45f * lim, 0.9f * lim, q);
        ring += bq;
        if (ring >= 3.5f) return 0.0f;
    }
    return sstep(0.5f, 0.95f, 1.0f - ring / 8.0f);
}

__DEVICE__ float2 compactGl(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, float L, float ro, int w, int h)
{
    float iL = 1.0f / _fmaxf(L, 1e-4f);
    float br = 0.1f;
    for (int s = 0; s < 3; s++) {
        int ri = (int)((s == 0 ? 0.5f : (s == 1 ? 2.0f : 6.0f)) * ro + 0.5f);
        float bs = lumaTexGl(tr, tg, tb, mirL(x + ri, w), y) + lumaTexGl(tr, tg, tb, mirL(x - ri, w), y)
                 + lumaTexGl(tr, tg, tb, x, mirL(y + ri, h)) + lumaTexGl(tr, tg, tb, x, mirL(y - ri, h));
        br += 0.3f * sstep(0.35f, 0.8f, bs * 0.25f * iL);
    }
    float pt = ringDarkGl(tr, tg, tb, x, y, ro, 0.3f, L, w, h), fr = 10.0f * ro;
    if (pt < 1.0f) {
        float p2 = ringDarkGl(tr, tg, tb, x, y, 5.0f * ro, 0.8f, L, w, h);
        if (p2 > pt) { pt = p2; fr = 14.0f * ro; }
    }
    if (pt < 1.0f) {
        float p3 = ringDarkGl(tr, tg, tb, x, y, 14.0f * ro, 0.5f, L, w, h);
        if (p3 > pt) { pt = p3; fr = 30.0f * ro; }
    }
    if (pt <= 0.0f) return make_float2(0.0f, br);
    float nf = 0.0f;
    for (int i = 0; i < 8; i++) {
        float a = 0.7853982f * (float)(i) + 0.2f;
        int sx = mirL(x + (int)(_round(fr * _cosf(a))), w), sy = mirL(y + (int)(_round(fr * _sinf(a))), h);
        nf += sstep(0.55f * L, 0.8f * L, lumaTexGl(tr, tg, tb, sx, sy));
    }
    pt *= 1.0f - 0.9f * sstep(0.0f, 0.4f, nf / 8.0f);
    return make_float2(pt, br);
}

__DEVICE__ float4 lightTapGl(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float fx, float fy, float thr, float ro, float base, float hot, int w, int h)
{
    float bx = _floorf(fx), by = _floorf(fy);
    float ax = fx - bx, ay = fy - by, band = _fmaxf(1.0f - thr, 0.02f);
    int x0 = (int)(bx), y0 = (int)(by);
    float er = 0.0f, eg = 0.0f, eb = 0.0f, ps = 0.0f, bs = 0.0f, qs = 0.0f;
    for (int k = 0; k < 4; k++) {
        int kx = k & 1, ky = k >> 1;
        float wt = (kx == 1 ? ax : 1.0f - ax) * (ky == 1 ? ay : 1.0f - ay);
        if (wt <= 0.0f) continue;
        int mx = mirL(x0 + kx, w), my = mirL(y0 + ky, h);
        float r = _saturatef(_tex2D(tr, mx, my)), g = _saturatef(_tex2D(tg, mx, my)), b = _saturatef(_tex2D(tb, mx, my));
        float L = luma(r, g, b);
        if (L <= thr) continue;
        float ex = sstep(0.0f, 0.4f, (L - thr) / band), e = wt * ex;
        er += toLin(r) * e; eg += toLin(g) * e; eb += toLin(b) * e;
        float2 cb = compactGl(tr, tg, tb, mx, my, L, ro, w, h);
        float q = wt * ex * ex;
        ps += q * cb.x; bs += q * cb.y; qs += q;
    }
    if (qs <= 0.0f) return make_float4(0.0f, 0.0f, 0.0f, 0.0f);
    float pt = ps / qs, k = base + hot * pt * pt;
    if (k <= 0.0f) return make_float4(0.0f, 0.0f, 0.0f, 0.0f);
    return make_float4(er * k, eg * k, eb * k, bs / qs);
}

__DEVICE__ float keyGl(float3 c, float thr, float kh, float kw)
{
    float r = _saturatef(c.x), g = _saturatef(c.y), b = _saturatef(c.z);
    float k = sstep(thr, thr + 0.25f * (1.0f - thr) + 0.02f, luma(r, g, b));
    if (k <= 0.0f || kw >= 180.0f) return k;
    float mx = _fmaxf(r, _fmaxf(g, b)), mn = _fminf(r, _fminf(g, b)), d = mx - mn;
    if (d < 1e-4f) return 0.0f;
    float hh;
    if (mx == r) hh = 60.0f * _fmod((g - b) / d + 6.0f, 6.0f);
    else if (mx == g) hh = 60.0f * ((b - r) / d + 2.0f);
    else hh = 60.0f * ((r - g) / d + 4.0f);
    float dh = _fabs(_fmod(hh - kh + 540.0f, 360.0f) - 180.0f);
    return k * (1.0f - sstep(kw, kw + 20.0f, dh)) * sstep(0.04f, 0.15f, d / _fmaxf(mx, 1e-4f));
}
