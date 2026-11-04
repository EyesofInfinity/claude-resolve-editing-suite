// Develop damage: the code of Develop Damage, on top of stock.h (gamma, mixing), light.h (hash, noise) and
// glitch.h (clamped sampling). Every helper works in units of a 1080-row frame (X, Y and the frame width Wn), so a
// pattern keeps its size at any resolution. Pictures go in and out in linear light. MIT License.

#include "../stock/stock.h"

__DEVICE__ float2 segDist(float px, float py, float ax, float ay, float dx, float dy, float L)
{
    float t = _clampf((px - ax) * dx + (py - ay) * dy, 0.0f, L);
    float ex = px - ax - dx * t, ey = py - ay - dy * t;
    return make_float2(_sqrtf(ex * ex + ey * ey), t / _fmaxf(L, 1e-4f));
}

__DEVICE__ float3 filmDamage(float3 l, float X, float Y, float Wn, int f, float str, float size, float spd, float age, uint sd)
{
    float3 o = l;
    for (int i = 0; i < 4; i++) {
        float run = (30.0f + 70.0f * hash01((uint)(i), 0u, sd)) * (1.5f - spd);
        int s = (int)(_floorf(((float)(f) + run * hash01((uint)(i), 1u, sd)) / run));
        if (hash01((uint)(i), (uint)(s + 4096), sd + 11u) > 0.25f + 0.45f * str) continue;
        if (hash01((uint)(i), (uint)(f), sd + 16u) < 0.07f) continue;
        float xb = (0.06f + 0.88f * hash01((uint)(i), (uint)(s + 4096), sd + 12u)) * Wn;
        float xs = xb + (fbm((float)(f) * 0.03f * (0.4f + spd), 3.7f * (float)(i), 0.0f, 2, sd + 13u) - 0.5f) * 40.0f * size
                 + (hash01((uint)(i), (uint)(f), sd + 14u) - 0.5f) * 1.2f;
        float w = (0.5f + 1.4f * hash01((uint)(i), (uint)(s + 4096), sd + 15u)) * size;
        float dx = X - xs;
        if (_fabs(dx) > 4.0f * w) continue;
        float core = _expf(-dx * dx / (w * w));
        float br = sstep(0.32f, 0.58f, fbm(Y / 260.0f, 0.9f * (float)(f) + 17.0f * (float)(i), 0.0f, 3, sd + 18u));
        float k = core * br * (0.65f + 0.35f * hash01((uint)(i), (uint)(f), sd + 19u));
        if (hash01((uint)(i), (uint)(s + 4096), sd + 17u) < 0.65f) {
            float gr = hash01((uint)(i), (uint)(s + 4096), sd + 20u) < 0.5f ? 1.0f : 0.0f;
            float3 sc = make_float3(0.85f - 0.25f * gr, 0.88f, 0.8f - 0.1f * gr);
            o = make_float3(lerp1(o.x, sc.x, k), lerp1(o.y, sc.y, k), lerp1(o.z, sc.z, k));
        } else {
            o = make_float3(o.x * (1.0f - 0.85f * k), o.y * (1.0f - 0.85f * k), o.z * (1.0f - 0.85f * k));
        }
    }
    {
        int c = (int)(_floorf(X / 24.0f));
        if (hash01((uint)(c + 65536), (uint)(f), sd + 30u) < 0.035f * str) {
            float xc = ((float)(c) + 0.2f + 0.6f * hash01((uint)(c + 65536), (uint)(f), sd + 31u)) * 24.0f;
            float y0 = hash01((uint)(c + 65536), (uint)(f), sd + 32u) * 1080.0f, ln = 120.0f + 600.0f * hash01((uint)(c + 65536), (uint)(f), sd + 33u);
            float dx = (X - xc) / (0.45f * size);
            float k = _expf(-dx * dx) * sstep(y0, y0 + 30.0f, Y) * sstep(y0 + ln, y0 + ln - 30.0f, Y) * 0.35f;
            o = make_float3(lerp1(o.x, 0.8f, k), lerp1(o.y, 0.8f, k), lerp1(o.z, 0.76f, k));
        }
    }
    {
        float C = 40.0f;
        int cx = (int)(_floorf(X / C)), cy = (int)(_floorf(Y / C));
        uint z = (uint)(f) * 977u + sd;
        if (hash01((uint)(cx + 65536), (uint)(cy + 65536), z + 40u) < 0.004f + 0.02f * str) {
            float h3 = hash01((uint)(cx + 65536), (uint)(cy + 65536), z + 41u);
            float r = (0.8f + 5.5f * h3 * h3 * h3) * size;
            float px = ((float)(cx) + 0.5f) * C + (hash01((uint)(cx + 65536), (uint)(cy + 65536), z + 42u) - 0.5f) * (C - 2.0f * r - 2.0f);
            float py = ((float)(cy) + 0.5f) * C + (hash01((uint)(cx + 65536), (uint)(cy + 65536), z + 43u) - 0.5f) * (C - 2.0f * r - 2.0f);
            float d = _sqrtf((X - px) * (X - px) + (Y - py) * (Y - py));
            float edge = d - r * (0.7f + 0.6f * vnoise3(X * 0.7f + 4096.0f, Y * 0.7f + 4096.0f, (float)(f), sd + 44u));
            float m = sstep(0.7f, -0.7f, edge);
            if (hash01((uint)(cx + 65536), (uint)(cy + 65536), z + 45u) < 0.7f) o = make_float3(o.x * (1.0f - 0.92f * m), o.y * (1.0f - 0.92f * m), o.z * (1.0f - 0.92f * m));
            else o = make_float3(lerp1(o.x, 0.82f, m), lerp1(o.y, 0.8f, m), lerp1(o.z, 0.74f, m));
        }
    }
    if (hash01((uint)(f), 50u, sd) < 0.1f + 0.25f * str) {
        float hx = hash01((uint)(f), 51u, sd) * Wn, hy = hash01((uint)(f), 52u, sd) * 1080.0f;
        float L = (60.0f + 200.0f * hash01((uint)(f), 53u, sd)) * size;
        if (_fabs(X - hx) < L + 4.0f && _fabs(Y - hy) < L + 4.0f) {
            float an = 6.2831853f * hash01((uint)(f), 54u, sd), curl = 0.25f + 0.6f * hash01((uint)(f), 55u, sd);
            float ph = 6.2831853f * hash01((uint)(f), 56u, sd), seg = L / 10.0f, best = 1e9f, ax = hx, ay = hy;
            for (int k = 0; k < 10; k++) {
                float a = an + curl * _sinf(0.8f * (float)(k) + ph);
                float dx = _cosf(a), dy = _sinf(a);
                float2 q = segDist(X, Y, ax, ay, dx, dy, seg);
                best = _fminf(best, q.x);
                ax += dx * seg; ay += dy * seg;
            }
            float w = 0.7f * size, m = _expf(-best * best / (w * w)) * 0.9f;
            o = make_float3(o.x * (1.0f - m), o.y * (1.0f - m), o.z * (1.0f - m));
        }
    }
    if (hash01((uint)(f), 60u, sd) < 0.12f * str) {
        float bx = hash01((uint)(f), 61u, sd) * Wn, by = hash01((uint)(f), 62u, sd) * 1080.0f;
        float R = (40.0f + 110.0f * hash01((uint)(f), 63u, sd)) * size;
        float d = _sqrtf((X - bx) * (X - bx) + (Y - by) * (Y - by));
        if (d < 1.6f * R) {
            float edge = d / R - 0.7f * fbm(X / 40.0f, Y / 40.0f, (float)(f), 3, sd + 64u);
            float m = sstep(0.75f, 0.35f, edge) * 0.35f * (0.6f + 0.8f * fbm(X / 12.0f, Y / 12.0f, (float)(f), 2, sd + 65u));
            o = make_float3(o.x * (1.0f + 0.8f * m) + 0.012f * m, o.y * (1.0f + 0.9f * m) + 0.014f * m, o.z * (1.0f + 0.3f * m) + 0.004f * m);
        }
    }
    float g = 1.0f + str * 0.07f * ((hash01((uint)(f), 70u, sd) + hash01((uint)(f + 1), 70u, sd)) * 0.5f - 0.5f)
            + str * 0.04f * (hash01((uint)(f), 71u, sd) - 0.5f) * (X / Wn - 0.5f) * 2.0f;
    float3 w = make_float3(1.0f + 0.05f * age, 1.0f, 1.0f - 0.1f * age);
    return make_float3(o.x * g * w.x + 0.0004f * age, o.y * g * w.y + 0.0003f * age, o.z * g * w.z + 0.0002f * age);
}

__DEVICE__ float3 grunge(float3 l, float X, float Y, float Wn, float str, float size, float age, uint sd)
{
    float u = X / (420.0f * size), v = Y / (420.0f * size);
    float big = fbm(u, v, 0.0f, 5, sd);
    float pool = sstep(0.5f, 0.85f, big) * 0.6f + sstep(0.6f, 0.8f, fbm(u * 2.5f, v * 2.5f, 1.7f, 4, sd + 5u)) * 0.5f;
    float mott = _fmaxf(fbm(u * 4.0f, v * 4.0f, 3.1f, 4, sd + 1u) - 0.5f, 0.0f) * 2.0f;
    float n = vnoise3(X / (2.2f * size) + 4096.0f, Y / (2.2f * size) + 4096.0f, 7.0f, sd + 2u);
    float grit = sstep(0.8f, 0.95f, n) * sstep(0.42f, 0.7f, fbm(u * 2.0f, v * 2.0f, 9.0f, 3, sd + 3u));
    float ex = (X / Wn - 0.5f) * 2.0f, ey = (Y / 1080.0f - 0.5f) * 2.0f;
    float edge = sstep(0.8f, 1.35f, _sqrtf(ex * ex * 0.75f + ey * ey) * 0.9f + 0.5f * (big - 0.5f));
    float pore = 0.45f + 1.1f * fbm(u * 10.0f, v * 10.0f, 13.0f, 3, sd + 6u);
    float dark = _saturatef(str * ((0.45f * pool + 0.6f * edge) * pore + 0.3f * mott + 0.75f * grit));
    float3 col = mix3(make_float3(0.42f, 0.36f, 0.28f), make_float3(0.36f, 0.24f, 0.12f), age);
    float3 o = make_float3(l.x * lerp1(1.0f, col.x, dark), l.y * lerp1(1.0f, col.y, dark), l.z * lerp1(1.0f, col.z, dark));
    float m = luma(o.x, o.y, o.z), ds = 0.4f * dark;
    o = make_float3(lerp1(o.x, m, ds), lerp1(o.y, m, ds), lerp1(o.z, m, ds));
    float3 vd = disp3(o);
    float ta = 3.14159265f * hash01(sd, 7u, 3u), ca = _cosf(ta), sa = _sinf(ta);
    float su = (X * ca + Y * sa) / (420.0f * size), sv = (-X * sa + Y * ca) / (420.0f * size);
    float scuff = sstep(0.62f, 0.9f, fbm(su * 1.6f, sv * 4.8f, 5.0f, 4, sd + 4u)) * str * 0.22f;
    float3 milk = mix3(make_float3(0.62f, 0.6f, 0.56f), make_float3(0.66f, 0.58f, 0.46f), age);
    return mix3(vd, milk, scuff);
}

__DEVICE__ float3 stains(float3 l, float X, float Y, float str, float size, float age, uint sd)
{
    float C = 520.0f * size;
    int cx = (int)(_floorf(X / C)), cy = (int)(_floorf(Y / C));
    float3 T = mix3(make_float3(0.7f, 0.52f, 0.32f), make_float3(0.55f, 0.36f, 0.18f), age);
    float3 o = l;
    for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
        uint a = (uint)(cx + i + 65536), b = (uint)(cy + j + 65536);
        if (hash01(a, b, sd + 80u) > 0.6f) continue;
        float px = ((float)(cx + i) + 0.2f + 0.6f * hash01(a, b, sd + 81u)) * C;
        float py = ((float)(cy + j) + 0.2f + 0.6f * hash01(a, b, sd + 82u)) * C;
        float R = (0.12f + 0.3f * hash01(a, b, sd + 83u)) * C;
        float dx = X - px, dy = Y - py, d = _sqrtf(dx * dx + dy * dy);
        if (d > 1.4f * R) continue;
        float ux = dx / _fmaxf(d, 1e-3f), uy = dy / _fmaxf(d, 1e-3f), off = 10.0f * hash01(a, b, sd + 84u);
        float rr = R * (0.8f + 0.4f * fbm(ux * 1.4f + off, uy * 1.4f + off, 0.0f, 3, sd + 85u));
        float q = d / rr, e = (q - 1.0f) * rr;
        float tw = 2.4f * size;
        float tide = q < 1.0f ? _expf(-e * e / (6.0f * tw * tw)) : _expf(-e * e / (0.3f * tw * tw));
        float inner = sstep(1.0f + 0.4f / rr, 1.0f - 0.4f / rr, q);
        float dens = inner * (0.25f + 0.6f * q * q * q * q * q * q) * (0.6f + 0.8f * fbm(X / 90.0f, Y / 90.0f, off, 3, sd + 86u));
        float r2 = 0.0f;
        if (hash01(a, b, sd + 87u) < 0.5f) { float e2 = (q - 0.78f) * rr; r2 = 0.5f * _expf(-e2 * e2 / (2.0f * tw * tw)) * inner; }
        float s = _saturatef((dens + 0.9f * tide + r2) * str * 1.3f);
        o = make_float3(o.x * lerp1(1.0f, T.x, s), o.y * lerp1(1.0f, T.y, s), o.z * lerp1(1.0f, T.z, s));
    }
    return o;
}

__DEVICE__ float3 scratches(float3 v, float X, float Y, float str, float size, uint sd)
{
    float C = 150.0f * size;
    int cx = (int)(_floorf(X / C)), cy = (int)(_floorf(Y / C));
    float th0 = 3.14159265f * hash01(sd, 9u, 1u);
    int nper = 1 + (int)(str * 2.0f);
    float lit = 0.0f, gouge = 0.0f;
    for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
        uint a = (uint)(cx + i + 65536), b = (uint)(cy + j + 65536);
        for (int k = 0; k < 4; k++) {
            if (k >= nper) break;
            uint z = sd + 100u + 10u * (uint)(k);
            float px = ((float)(cx + i) + hash01(a, b, z)) * C, py = ((float)(cy + j) + hash01(a, b, z + 1u)) * C;
            float hs = hash01(a, b, z + 2u);
            float th = hs < 0.5f ? th0 + (hash01(a, b, z + 3u) - 0.5f) * 1.7f : 3.14159265f * hash01(a, b, z + 3u);
            float hl = hash01(a, b, z + 4u);
            float L = (0.3f + 1.5f * hl * hl) * C;
            float dx = _cosf(th), dy = _sinf(th);
            float2 q = segDist(X, Y, px - 0.5f * L * dx, py - 0.5f * L * dy, dx, dy, L);
            float w = (0.35f + 0.6f * hash01(a, b, z + 5u)) * size;
            if (q.x > 4.0f * w) continue;
            float taper = _sqrtf(_saturatef(4.0f * q.y * (1.0f - q.y)));
            float along = 0.55f + 0.45f * vnoise3(q.y * L / 25.0f + 4096.0f, 4096.0f + (float)(k), 4096.0f, a + b * 31u);
            float m = _expf(-q.x * q.x / (w * w)) * taper * along;
            if (hash01(a, b, z + 6u) < 0.8f) lit = _fmaxf(lit, m * (0.5f + 0.5f * hash01(a, b, z + 7u)));
            else gouge = _fmaxf(gouge, m);
        }
    }
    float ca = _cosf(th0), sa = _sinf(th0);
    float hu = (X * ca + Y * sa) / (60.0f * size), hv = (-X * sa + Y * ca) / (0.9f * size);
    float haze = sstep(0.78f, 0.97f, vnoise3(hu + 4096.0f, hv + 4096.0f, 11.0f, sd + 120u)) * 0.12f;
    float a = _saturatef((lit * 0.75f + haze) * (0.35f + 0.85f * str));
    float3 o = make_float3(1.0f - (1.0f - v.x) * (1.0f - a * 0.9f), 1.0f - (1.0f - v.y) * (1.0f - a * 0.9f), 1.0f - (1.0f - v.z) * (1.0f - a * 0.86f));
    float gd = 1.0f - 0.55f * gouge * (0.35f + 0.65f * str);
    return make_float3(o.x * gd, o.y * gd, o.z * gd);
}

__DEVICE__ float3 flicker(float3 l, float X, float Y, int f, float str, float spd, uint sd)
{
    float rt = 0.05f + 0.55f * spd;
    float base = fbm((float)(f) * rt, 1.3f, 0.0f, 3, sd) - 0.5f;
    float jit = hash01((uint)(f), 90u, sd) - 0.5f;
    float dip = hash01((uint)(f), 91u, sd) < 0.05f * str ? 1.0f : 0.0f;
    float e = str * (1.1f * base + 0.6f * jit * spd) - dip * str * 0.9f;
    float side = fbm(X / 700.0f, Y / 700.0f, (float)(f) * rt * 0.7f, 2, sd + 5u) - 0.5f;
    float g = _exp2f(e * (1.0f + 1.2f * side));
    return make_float3(l.x * _powf(g, 0.85f), l.y * g, l.z * _powf(g, 1.25f));
}

__DEVICE__ float3 edgeBurn(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h, float3 l,
                           float X, float Y, int f, float str, float size, float prog, float key, uint sd)
{
    float sc = (float)(h) / 1080.0f, R = (3.0f + 10.0f * (size - 0.5f)) * sc;
    float kk = sstep(key - 0.08f, key + 0.08f, luma(_powf(l.x, 1.0f / 2.4f), _powf(l.y, 1.0f / 2.4f), _powf(l.z, 1.0f / 2.4f)));
    float t0 = sstep(key - 0.45f, key - 0.35f, luma(_powf(l.x, 1.0f / 2.4f), _powf(l.y, 1.0f / 2.4f), _powf(l.z, 1.0f / 2.4f)));
    float b = kk, gw = 1.0f - t0;
    float3 gs = make_float3(l.x * gw, l.y * gw, l.z * gw);
    for (int j = 1; j <= 3; j++) for (int i = 0; i < 8; i++) {
        float an = 0.7853982f * (float)(i) + 0.2617994f * (float)(j), rr = R * (float)(j) / 3.0f;
        float3 c = rgbAt(tr, tg, tb, x + (int)(_round(rr * _cosf(an))), y + (int)(_round(rr * _sinf(an))), w, h);
        float lc = luma(c.x, c.y, c.z), k = sstep(key - 0.08f, key + 0.08f, lc), t = 1.0f - sstep(key - 0.45f, key - 0.35f, lc);
        b += k;
        gs = make_float3(gs.x + toLin(c.x) * t, gs.y + toLin(c.y) * t, gs.z + toLin(c.z) * t);
        gw += t;
    }
    b = b / 25.0f;
    if (b <= 0.0f) return l;
    for (int j = 0; j < 2; j++) for (int i = 0; i < 8; i++) {
        float an = 0.7853982f * (float)(i) + 0.3926991f * (float)(j), rr = R * (j == 0 ? 4.0f : 10.0f);
        float3 c = rgbAt(tr, tg, tb, x + (int)(_round(rr * _cosf(an))), y + (int)(_round(rr * _sinf(an))), w, h);
        float t = 1.0f - sstep(key - 0.45f, key - 0.35f, luma(c.x, c.y, c.z));
        gs = make_float3(gs.x + toLin(c.x) * t, gs.y + toLin(c.y) * t, gs.z + toLin(c.z) * t);
        gw += t;
    }
    float3 gr = gw > 0.01f ? make_float3(gs.x / gw, gs.y / gw, gs.z / gw) : make_float3(0.0f, 0.0f, 0.0f);
    float n = fbm(X / (70.0f * size), Y / (70.0f * size), (float)(f) * 0.01f, 4, sd);
    float n2 = vnoise3(X / (4.0f * size) + 4096.0f, Y / (4.0f * size) + 4096.0f, 3.0f, sd + 1u);
    float rough = 0.2f + 0.7f * str;
    float fld = b + rough * (0.85f * (n - 0.5f) + 0.15f * (n2 - 0.5f)) - 1.15f * prog;
    float e = fld - 0.5f;
    float gone = sstep(0.008f, -0.008f, e) * t0;
    float3 o = mix3(l, gr, gone);
    float sco = sstep(0.1f, 0.0f, e) * (1.0f - gone) * kk;
    o = make_float3(o.x * lerp1(1.0f, 0.2f, sco), o.y * lerp1(1.0f, 0.08f, sco), o.z * lerp1(1.0f, 0.03f, sco));
    float on = sstep(0.0f, 0.06f, prog);
    float fl = 0.6f + 0.8f * vnoise3(X / 10.0f + 4096.0f, Y / 10.0f + 4096.0f, (float)(f) * 0.45f + 4096.0f, sd + 2u);
    float em = (_expf(-e * e / 0.0006f) + 0.2f * _expf(-e * e / 0.004f)) * on * fl * sstep(0.02f, 0.12f, b);
    return make_float3(o.x + em * 2.4f, o.y + em * 0.7f, o.z + em * 0.1f);
}
