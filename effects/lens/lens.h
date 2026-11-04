// Develop lens: shared code of Develop Bokeh and Develop Lens, on top of light.h and glitch.h. Bilinear sampling
// with mirrored edges, linear light (Rec.709 gamma 2.4). MIT License.

#include "../light/light.h"
#include "../glitch/glitch.h"

__DEVICE__ int mirL(int i, int n)
{
    int q = 2 * n, m = i % q;
    if (m < 0) m += q;
    if (m >= n) m = q - 1 - m;
    return clampi(m, 0, n - 1);
}

__DEVICE__ float3 bilL(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float fx, float fy, int w, int h)
{
    float bx = _floorf(fx), by = _floorf(fy);
    float ax = fx - bx, ay = fy - by;
    int x0 = (int)(bx), y0 = (int)(by);
    int xa = mirL(x0, w), xb = mirL(x0 + 1, w), ya = mirL(y0, h), yb = mirL(y0 + 1, h);
    float3 c00 = make_float3(_tex2D(tr, xa, ya), _tex2D(tg, xa, ya), _tex2D(tb, xa, ya));
    if (ax == 0.0f && ay == 0.0f) return c00;
    float3 c10 = make_float3(_tex2D(tr, xb, ya), _tex2D(tg, xb, ya), _tex2D(tb, xb, ya));
    float3 c01 = make_float3(_tex2D(tr, xa, yb), _tex2D(tg, xa, yb), _tex2D(tb, xa, yb));
    float3 c11 = make_float3(_tex2D(tr, xb, yb), _tex2D(tg, xb, yb), _tex2D(tb, xb, yb));
    return make_float3(lerp1(lerp1(c00.x, c10.x, ax), lerp1(c01.x, c11.x, ax), ay),
                       lerp1(lerp1(c00.y, c10.y, ax), lerp1(c01.y, c11.y, ax), ay),
                       lerp1(lerp1(c00.z, c10.z, ax), lerp1(c01.z, c11.z, ax), ay));
}

__DEVICE__ float3 linL(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float fx, float fy, int w, int h)
{
    float3 c = bilL(tr, tg, tb, fx, fy, w, h);
    return make_float3(toLin(c.x), toLin(c.y), toLin(c.z));
}

__DEVICE__ float aperture(float a, float n, float rot, float rnd)
{
    if (n < 3.0f) return 1.0f;
    float seg = 6.2831853f / n;
    float t = a - rot;
    float m = t - seg * _floorf(t / seg) - 0.5f * seg;
    float poly = _cosf(0.5f * seg) / _cosf(m);
    return lerp1(poly, 1.0f, rnd);
}

__DEVICE__ float3 specL(float t)
{
    float a = 6.2831853f * t;
    float r = 0.5f + 0.5f * _cosf(a), g = 0.5f + 0.5f * _cosf(a - 2.0943951f), b = 0.5f + 0.5f * _cosf(a - 4.1887902f);
    return make_float3(r * r * r, g * g * g, b * b * b);
}
