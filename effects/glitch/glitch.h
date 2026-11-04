// Develop glitch: shared code of the glitch effects, on top of light.h's hash and helpers. MIT License.

__DEVICE__ int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

__DEVICE__ float3 rgbAt(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h)
{
    int cx = clampi(x, 0, w - 1), cy = clampi(y, 0, h - 1);
    return make_float3(_tex2D(tr, cx, cy), _tex2D(tg, cx, cy), _tex2D(tb, cx, cy));
}

__DEVICE__ float lumaAt(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h)
{
    float3 c = rgbAt(tr, tg, tb, x, y, w, h);
    return luma(c.x, c.y, c.z);
}

__DEVICE__ float rnd3(int a, int b, uint c) { return hash01((uint)(a + 65536), (uint)(b + 65536), c); }

__DEVICE__ float bayer8(int cx, int cy)
{
    int bx = cx & 7, by = cy & 7, xr = bx ^ by;
    int v = ((xr & 1) << 5) | ((by & 1) << 4) | ((xr & 2) << 2) | ((by & 2) << 1) | ((xr & 4) >> 1) | ((by & 4) >> 2);
    return ((float)(v) + 0.5f) / 64.0f;
}

__DEVICE__ float3 gritFinish(float3 c, int x, int y, int h, float g, float grit, float dith, uint seed)
{
    if (g <= 0.0f) return c;
    float L = luma(c.x, c.y, c.z);
    float n = hash01((uint)(x + 65536), (uint)(y + 65536), seed) - 0.5f;
    float gr = grit * g * 0.16f * (0.35f + 0.65f * L) * n;
    float r = c.x + gr, gg = c.y + gr, b = c.z + gr;
    float d = dith * g;
    if (d > 0.0f) {
        int cell = (int)(2.0f * (float)(h) / 1080.0f + 0.5f);
        if (cell < 1) cell = 1;
        float t = bayer8((int)(x / cell), (int)(y / cell));
        float lv = 32.0f * (1.0f - d) + 3.0f * d - 1.0f;
        r = _floorf(_saturatef(r) * lv + t) / lv; gg = _floorf(_saturatef(gg) * lv + t) / lv; b = _floorf(_saturatef(b) * lv + t) / lv;
    }
    return make_float3(_saturatef(r), _saturatef(gg), _saturatef(b));
}

__DEVICE__ float3 chromaBleed(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float3 c, int x, int y, int w, int h, int k)
{
    if (k < 1) return c;
    float3 a = rgbAt(tr, tg, tb, x - k, y, w, h), b = rgbAt(tr, tg, tb, x - (int)(k / 2), y, w, h);
    float3 m = make_float3((a.x + b.x + c.x) / 3.0f, (a.y + b.y + c.y) / 3.0f, (a.z + b.z + c.z) / 3.0f);
    float L = luma(c.x, c.y, c.z), Lm = luma(m.x, m.y, m.z);
    return make_float3(m.x - Lm + L, m.y - Lm + L, m.z - Lm + L);
}
