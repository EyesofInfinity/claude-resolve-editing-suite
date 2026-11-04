// Develop stock: shared code of Develop Process and Develop Film Stock, on top of light.h (gamma, hash, noise)
// and glitch.h (clamped sampling). Rec.709 gamma 2.4 in and out; colour is mixed in linear, curves run on display
// values. Parametric curves only: no measured stock data, no LUT, nothing taken from any vendor. MIT License.

#include "../light/light.h"
#include "../glitch/glitch.h"

__DEVICE__ float3 lin3(float3 c) { return make_float3(toLin(c.x), toLin(c.y), toLin(c.z)); }
__DEVICE__ float3 disp3(float3 c) { return make_float3(toDisp(c.x), toDisp(c.y), toDisp(c.z)); }
__DEVICE__ float3 sat3(float3 c) { return make_float3(_saturatef(c.x), _saturatef(c.y), _saturatef(c.z)); }
__DEVICE__ float3 mix3(float3 a, float3 b, float t) { return make_float3(lerp1(a.x, b.x, t), lerp1(a.y, b.y, t), lerp1(a.z, b.z, t)); }

__DEVICE__ float sCurve(float v, float a, float p)
{
    if (_fabs(a) < 0.01f) return v;
    float u = _saturatef(v);
    if (a > 0.0f) {
        float lo = 1.0f / (1.0f + _expf(a * p)), hi = 1.0f / (1.0f + _expf(-a * (1.0f - p)));
        return (1.0f / (1.0f + _expf(-a * (u - p))) - lo) / (hi - lo);
    }
    float b = -a;
    float lo = 1.0f / (1.0f + _expf(b * p)), hi = 1.0f / (1.0f + _expf(-b * (1.0f - p)));
    float s = lo + u * (hi - lo);
    return _saturatef(p - _logf(1.0f / s - 1.0f) / b);
}

__DEVICE__ float3 satLin(float3 c, float s)
{
    float L = luma(c.x, c.y, c.z);
    return make_float3(_fmaxf(L + (c.x - L) * s, 0.0f), _fmaxf(L + (c.y - L) * s, 0.0f), _fmaxf(L + (c.z - L) * s, 0.0f));
}

__DEVICE__ float3 toneDisp(float3 v, float a, float p, float3 gam, float3 sh, float3 hi, float lift, float cap)
{
    float r = _powf(_saturatef(v.x), gam.x), g = _powf(_saturatef(v.y), gam.y), b = _powf(_saturatef(v.z), gam.z);
    r = sCurve(r, a, p); g = sCurve(g, a, p); b = sCurve(b, a, p);
    float L = luma(r, g, b), ws = (1.0f - L) * (1.0f - L), wh = L * L;
    r += sh.x * ws + hi.x * wh; g += sh.y * ws + hi.y * wh; b += sh.z * ws + hi.z * wh;
    return make_float3(lift + (cap - lift) * _saturatef(r), lift + (cap - lift) * _saturatef(g), lift + (cap - lift) * _saturatef(b));
}

__DEVICE__ float3 trims(float3 v, float con, float sat, float warm, float fade)
{
    float3 o = v;
    if (con != 0.0f) o = make_float3(sCurve(o.x, con * 0.05f, 0.46f), sCurve(o.y, con * 0.05f, 0.46f), sCurve(o.z, con * 0.05f, 0.46f));
    if (sat != 0.0f || warm != 0.0f) {
        float3 l = lin3(o);
        l = satLin(l, 1.0f + sat / 100.0f);
        float k = _exp2f(0.5f * warm / 100.0f);
        l = make_float3(l.x * k, l.y, l.z / k);
        o = sat3(disp3(l));
    }
    if (fade > 0.0f) {
        float f = fade / 100.0f, lo = 0.12f * f, hi = 1.0f - 0.10f * f;
        o = make_float3(lo + (hi - lo) * o.x, lo + (hi - lo) * o.y, lo + (hi - lo) * o.z);
    }
    return o;
}

__DEVICE__ float3 halation(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h, float rad, float amt, float tint)
{
    if (amt <= 0.0f) return make_float3(0.0f, 0.0f, 0.0f);
    float s = 0.0f;
    for (int i = 0; i < 16; i++) {
        float rr = rad * _sqrtf(((float)(i) + 0.5f) / 16.0f), an = 2.3999632f * (float)(i);
        int sx = x + (int)(_round(rr * _cosf(an))), sy = y + (int)(_round(rr * _sinf(an)));
        float L = toLin(lumaAt(tr, tg, tb, sx, sy, w, h));
        s += _fmaxf(L - 0.35f, 0.0f);
    }
    s = s / 16.0f * amt;
    return make_float3(s * 1.0f, s * lerp1(0.32f, 0.9f, tint), s * lerp1(0.10f, 0.85f, tint));
}

__DEVICE__ float3 grainDisp(float3 v, int x, int y, int h, float amt, float cell, uint seed)
{
    if (amt <= 0.0f) return v;
    float sz = _fmaxf(cell * (float)(h) / 1080.0f, 1.0f);
    int cx = (int)((float)(x) / sz), cy = (int)((float)(y) / sz);
    float n = (hash01((uint)(cx + 65536), (uint)(cy + 65536), seed) + hash01((uint)(cx + 65536), (uint)(cy + 65536), seed + 1u)) - 1.0f;
    float nc = hash01((uint)(cx + 65536), (uint)(cy + 65536), seed + 2u) - 0.5f;
    float L = luma(v.x, v.y, v.z), m = 4.0f * L * (1.0f - L) * 0.7f + 0.3f;
    float k = amt * 0.11f * m;
    return make_float3(v.x + k * (n + 0.25f * nc), v.y + k * n, v.z + k * (n - 0.25f * nc));
}
