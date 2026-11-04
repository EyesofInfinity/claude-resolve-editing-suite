// Develop paint: the code of Develop Paint, on top of light.h, glitch.h and lens.h. Every value comes in as an
// argument. Distances are in pixels; sc is the frame height over 1080. MIT License.

#include "../lens/lens.h"

__DEVICE__ float fr1(float v) { return v - _floorf(v); }
__DEVICE__ float3 mix3(float3 a, float3 b, float t) { return make_float3(lerp1(a.x, b.x, t), lerp1(a.y, b.y, t), lerp1(a.z, b.z, t)); }

__DEVICE__ float3 cross5(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h, int r0)
{
    int r = r0 < 1 ? 1 : r0;
    float3 a = rgbAt(tr, tg, tb, x, y, w, h), b = rgbAt(tr, tg, tb, x - r, y, w, h), c = rgbAt(tr, tg, tb, x + r, y, w, h);
    float3 d = rgbAt(tr, tg, tb, x, y - r, w, h), e = rgbAt(tr, tg, tb, x, y + r, w, h);
    return make_float3((a.x + b.x + c.x + d.x + e.x) / 5.0f, (a.y + b.y + c.y + d.y + e.y) / 5.0f, (a.z + b.z + c.z + d.z + e.z) / 5.0f);
}

__DEVICE__ float3 tent9(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h, int r0)
{
    int r = r0 < 1 ? 1 : r0;
    float3 s = make_float3(0.0f, 0.0f, 0.0f);
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            float3 c = rgbAt(tr, tg, tb, x + i * r, y + j * r, w, h);
            float wt = (i == 0 ? 2.0f : 1.0f) * (j == 0 ? 2.0f : 1.0f);
            s = make_float3(s.x + wt * c.x, s.y + wt * c.y, s.z + wt * c.z);
        }
    }
    return make_float3(s.x / 16.0f, s.y / 16.0f, s.z / 16.0f);
}

__DEVICE__ float3 likeMean(float3 a, float3 b, float3 c, float3 d, float3 e)
{
    float wb = 1.0f - sstep(0.06f, 0.30f, _fmaxf(_fabs(b.x - a.x), _fmaxf(_fabs(b.y - a.y), _fabs(b.z - a.z))));
    float wc = 1.0f - sstep(0.06f, 0.30f, _fmaxf(_fabs(c.x - a.x), _fmaxf(_fabs(c.y - a.y), _fabs(c.z - a.z))));
    float wd = 1.0f - sstep(0.06f, 0.30f, _fmaxf(_fabs(d.x - a.x), _fmaxf(_fabs(d.y - a.y), _fabs(d.z - a.z))));
    float we = 1.0f - sstep(0.06f, 0.30f, _fmaxf(_fabs(e.x - a.x), _fmaxf(_fabs(e.y - a.y), _fabs(e.z - a.z))));
    float t = 1.0f + wb + wc + wd + we;
    return make_float3((a.x + wb * b.x + wc * c.x + wd * d.x + we * e.x) / t, (a.y + wb * b.y + wc * c.y + wd * d.y + we * e.y) / t,
                       (a.z + wb * b.z + wc * c.z + wd * d.z + we * e.z) / t);
}

__DEVICE__ float edgeAt(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h, int r0)
{
    int r = r0 < 1 ? 1 : r0;
    float a = lumaAt(tr, tg, tb, x - r, y - r, w, h), b = lumaAt(tr, tg, tb, x, y - r, w, h), c = lumaAt(tr, tg, tb, x + r, y - r, w, h);
    float d = lumaAt(tr, tg, tb, x - r, y, w, h), f = lumaAt(tr, tg, tb, x + r, y, w, h);
    float g = lumaAt(tr, tg, tb, x - r, y + r, w, h), k = lumaAt(tr, tg, tb, x, y + r, w, h), m = lumaAt(tr, tg, tb, x + r, y + r, w, h);
    float gx = (c + 2.0f * f + m) - (a + 2.0f * d + g), gy = (g + 2.0f * k + m) - (a + 2.0f * b + c);
    return _sqrtf(gx * gx + gy * gy) / 4.0f;
}

__DEVICE__ float3 satur(float3 c, float k)
{
    float L = luma(c.x, c.y, c.z);
    return make_float3(_saturatef(L + (c.x - L) * k), _saturatef(L + (c.y - L) * k), _saturatef(L + (c.z - L) * k));
}

__DEVICE__ float3 toneCut(float3 c, float n, float k)
{
    float L = luma(c.x, c.y, c.z);
    float t = L * (n - 1.0f), fl = _floorf(t);
    float Lt = lerp1(L, _saturatef((fl + sstep(0.35f, 0.65f, t - fl)) / (n - 1.0f)), k);
    float kq = Lt / _fmaxf(L, 0.02f);
    float3 o = make_float3(_saturatef(c.x * kq), _saturatef(c.y * kq), _saturatef(c.z * kq));
    return mix3(o, make_float3(Lt, Lt, Lt), 0.6f * sstep(1.5f, 3.0f, kq));
}

__DEVICE__ float2 runDir(float gx, float gy, float a0, float fw, float sym)
{
    float g2 = gx * gx + gy * gy;
    float ge = _atan2f(gy, gx) + 1.5707963f;
    float wgt = fw * sstep(0.0015f, 0.0080f, g2);
    float mx = lerp1(_cosf(sym * a0), _cosf(sym * ge), wgt), my = lerp1(_sinf(sym * a0), _sinf(sym * ge), wgt);
    float th = _atan2f(my, mx) / sym;
    return make_float2(_cosf(th), _sinf(th));
}

__DEVICE__ float3 strokeAt(float px, float py, float cx, float cy, float tx, float ty, float lh, float wh, float bend, float sc, float dry, uint s)
{
    float dx = px - cx, dy = py - cy;
    float u = (dx * tx + dy * ty) / lh;
    float v = (-dx * ty + dy * tx - bend * u * u) / wh;
    if (_fabs(u) > 1.15f || _fabs(v) > 1.3f) return make_float3(0.0f, 0.0f, 0.5f);
    float tp = 1.0f - 0.35f * sstep(0.1f, 1.0f, u);
    float vv = v / tp;
    float uu = u * u;
    float d = uu * uu + vv * vv;
    float b = 0.65f * vnoise3(v * wh / (1.1f * sc) + 4096.0f, u * lh / (40.0f * sc) + 4096.0f, 0.0f, s)
            + 0.35f * vnoise3(v * wh / (3.0f * sc) + 4196.0f, u * lh / (90.0f * sc) + 4096.0f, 0.0f, s + 17u);
    float de = d - 0.45f * (b - 0.5f) * sstep(0.2f, 1.0f, _fabs(vv));
    float aa = _fminf(1.3f / wh, 0.5f);
    float a = 1.0f - sstep(1.0f - aa, 1.0f + aa, de);
    a *= 1.0f - dry * sstep(0.1f, 1.0f, u) * (1.0f - sstep(0.35f, 0.60f, b));
    float hgt = (1.0f - sstep(0.2f, 1.15f, de)) * (0.7f + 0.3f * b);
    return make_float3(a, hgt, b);
}

__DEVICE__ float4 paintLayer(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float3 base, float3 un, float fx, float fy, int w, int h,
                             float s, int per, float lw, float gate, float a0, float fw, float vib, float tex, float flat, float sc, uint sd)
{
    int ix = (int)(_floorf(fx / s)), iy = (int)(_floorf(fy / s));
    float z1 = -1.0f, z2 = -1.0f, z3 = -1.0f, a1 = 0.0f, a2 = 0.0f, a3 = 0.0f;
    float3 c1 = base, c2 = base, c3 = base;
    int r = (int)(0.35f * s + 0.5f);
    if (r < 1) r = 1;
    float lx = -0.62f, ly = -0.62f;
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            for (int k = 0; k < 2; k++) {
                if (k >= per) break;
                int ci = ix + i, cj = iy + j;
                uint ks = sd + (uint)(k) * 101u;
                float cx = ((float)(ci) + 0.5f + (rnd3(ci, cj, ks + 1u) - 0.5f) * 0.5f) * s;
                float cy = ((float)(cj) + 0.5f + (rnd3(ci, cj, ks + 2u) - 0.5f) * 0.5f) * s;
                int qx = (int)(_floorf(cx)), qy = (int)(_floorf(cy));
                float3 ca = rgbAt(tr, tg, tb, qx, qy, w, h), cl = rgbAt(tr, tg, tb, qx - r, qy, w, h), cr = rgbAt(tr, tg, tb, qx + r, qy, w, h);
                float3 cu = rgbAt(tr, tg, tb, qx, qy - r, w, h), cd = rgbAt(tr, tg, tb, qx, qy + r, w, h);
                float gx = (luma(cr.x, cr.y, cr.z) - luma(cl.x, cl.y, cl.z)) * 0.5f, gy = (luma(cd.x, cd.y, cd.z) - luma(cu.x, cu.y, cu.z)) * 0.5f;
                float ch = _fmaxf(_fmaxf(_fabs(cr.x - cl.x), _fabs(cr.y - cl.y)), _fmaxf(_fabs(cr.z - cl.z), _fmaxf(_fabs(cd.x - cu.x), _fmaxf(_fabs(cd.y - cu.y), _fabs(cd.z - cu.z)))));
                float gk = gate > 0.0f ? sstep(0.7f * gate, 1.3f * gate, 0.5f * ch) : 1.0f;
                if (gk <= 0.0f) continue;
                float wa = a0 + 2.0f * (vnoise3(cx / (4.0f * s) + 4096.0f, cy / (4.0f * s) + 4096.0f, 0.0f, sd + 3u) - 0.5f)
                         + 0.5f * (rnd3(ci, cj, ks + 10u) - 0.5f);
                float2 t = runDir(gx, gy, wa, fw, 2.0f);
                float lh = s * lw * (0.6f + 0.45f * rnd3(ci, cj, ks + 4u)), wh = s * 0.38f * (0.75f + 0.5f * rnd3(ci, cj, ks + 5u));
                float bend = (rnd3(ci, cj, ks + 11u) - 0.5f) * 1.2f * wh;
                uint ss = ks + (uint)((ci & 1023) * 1024 + (cj & 1023)) * 3u;
                float3 st = strokeAt(fx, fy, cx, cy, t.x, t.y, lh, wh, bend, sc, 0.7f * tex * (1.0f - flat), ss);
                if (st.x <= 0.002f) continue;
                float3 pc = make_float3((ca.x + cl.x + cr.x + cu.x + cd.x) / 5.0f, (ca.y + cl.y + cr.y + cu.y + cd.y) / 5.0f, (ca.z + cl.z + cr.z + cu.z + cd.z) / 5.0f);
                float dc = _sqrtf((pc.x - un.x) * (pc.x - un.x) + (pc.y - un.y) * (pc.y - un.y) + (pc.z - un.z) * (pc.z - un.z));
                float a = gk * st.x * (1.0f - 0.95f * sstep(0.10f, 0.22f, dc));
                float jv = 1.0f + 0.07f * (rnd3(ci, cj, ks + 6u) - 0.5f);
                pc = make_float3(pc.x * jv * (1.0f + 0.03f * (rnd3(ci, cj, ks + 7u) - 0.5f)), pc.y * jv, pc.z * jv * (1.0f + 0.03f * (rnd3(ci, cj, ks + 8u) - 0.5f)));
                pc = satur(pc, 1.0f + 0.6f * vib + 0.4f * flat);
                if (flat > 0.0f) pc = toneCut(pc, 5.0f, 1.0f);
                float dr = 0.7f * tex * (1.0f - flat);
                float3 sx = strokeAt(fx + 1.0f, fy, cx, cy, t.x, t.y, lh, wh, bend, sc, dr, ss);
                float3 sy = strokeAt(fx, fy + 1.0f, cx, cy, t.x, t.y, lh, wh, bend, sc, dr, ss);
                float sl = ((sx.y - st.y) * lx + (sy.y - st.y) * ly) * wh;
                float sh = (1.0f - flat) * tex * (0.16f * _clampf(sl, -1.5f, 1.5f) + 0.12f * (st.z - 0.5f));
                pc = make_float3(_saturatef(pc.x * (1.0f - sh)), _saturatef(pc.y * (1.0f - sh)), _saturatef(pc.z * (1.0f - sh)));
                float zz = rnd3(ci, cj, ks + 9u);
                if (zz > z1) { z3 = z2; a3 = a2; c3 = c2; z2 = z1; a2 = a1; c2 = c1; z1 = zz; a1 = a; c1 = pc; }
                else if (zz > z2) { z3 = z2; a3 = a2; c3 = c2; z2 = zz; a2 = a; c2 = pc; }
                else if (zz > z3) { z3 = zz; a3 = a; c3 = pc; }
            }
        }
    }
    float3 o = mix3(mix3(mix3(base, c3, a3), c2, a2), c1, a1);
    return make_float4(o.x, o.y, o.z, 1.0f - (1.0f - a1) * (1.0f - a2) * (1.0f - a3));
}

__DEVICE__ float3 watercolour(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float fx, float fy, int w, int h, float R,
                              float det, float vib, float tex, float sc, uint sd)
{
    float wx = (fbm(fx / (70.0f * sc), fy / (70.0f * sc), 0.0f, 2, sd + 21u) - 0.5f) * 0.8f * R;
    float wy = (fbm(fx / (70.0f * sc), fy / (70.0f * sc), 0.0f, 2, sd + 22u) - 0.5f) * 0.8f * R;
    float qx = fx + wx, qy = fy + wy, hr = 0.5f * R;
    float3 sum = make_float3(0.0f, 0.0f, 0.0f);
    float gx = 0.0f, gy = 0.0f;
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            float3 c = bilL(tr, tg, tb, qx + (float)(i) * hr, qy + (float)(j) * hr, w, h);
            float wt = (i == 0 ? 2.0f : 1.0f) * (j == 0 ? 2.0f : 1.0f);
            sum = make_float3(sum.x + wt * c.x, sum.y + wt * c.y, sum.z + wt * c.z);
            float L = luma(c.x, c.y, c.z);
            gx += (float)(i) * L * (j == 0 ? 2.0f : 1.0f);
            gy += (float)(j) * L * (i == 0 ? 2.0f : 1.0f);
        }
    }
    float3 wc = make_float3(sum.x / 16.0f, sum.y / 16.0f, sum.z / 16.0f);
    float con = 0.25f * _sqrtf(gx * gx + gy * gy);
    float gpx = _fmaxf(con / R, 0.00001f);
    float L = luma(wc.x, wc.y, wc.z);
    float n = 3.0f + _floorf(det * 5.0f + 0.5f);
    float t = L * n, f = fr1(t), fl = _floorf(t);
    float ks = sstep(0.04f, 0.14f, con);
    float qv = (fl + 0.5f - 0.5f * (1.0f - sstep(0.0f, 0.3f, f)) + 0.5f * (1.0f - sstep(0.0f, 0.3f, 1.0f - f))) / n;
    float Lw = lerp1(L, _fminf(qv, 1.0f), 0.3f + 0.4f * det);
    float kk = Lw / _fmaxf(L, 0.01f);
    float3 c = make_float3(_saturatef(wc.x * kk), _saturatef(wc.y * kk), _saturatef(wc.z * kk));
    float3 cq = cross5(tr, tg, tb, (int)(fx), (int)(fy), w, h, (int)(2.0f * sc + 0.5f));
    float dk = luma(cq.x, cq.y, cq.z) - L;
    float dt = -sstep(0.05f, 0.18f, -dk) * (0.10f + 0.35f * det) * _fabs(dk) * 2.0f;
    c = make_float3(_saturatef(c.x * (1.0f + dt)), _saturatef(c.y * (1.0f + dt)), _saturatef(c.z * (1.0f + dt)));
    c = satur(c, 1.15f + 0.5f * vib);
    c = make_float3(1.0f - 0.82f * (1.0f - c.x), 1.0f - 0.82f * (1.0f - c.y), 1.0f - 0.82f * (1.0f - c.z));
    c = mix3(c, make_float3(1.0f, 1.0f, 1.0f), sstep(0.80f, 0.94f, L));
    float rim = 0.8f * ks * _fmaxf(_expf(-((1.0f - f) / (n * gpx)) / (3.0f * sc)), _expf(-(f / (n * gpx)) / (0.7f * sc)));
    float p1 = fbm(fx / (1.5f * sc), fy / (1.5f * sc), 0.0f, 3, sd + 31u);
    float p2 = fbm(fx / (6.0f * sc), fy / (6.0f * sc), 0.0f, 2, sd + 32u);
    float pp = 0.55f * p1 + 0.45f * p2;
    float tu = fbm(fx / (35.0f * sc), fy / (35.0f * sc), 0.0f, 3, sd + 41u) - 0.5f;
    float pig = 1.0f - luma(c.x, c.y, c.z);
    float d = 1.0f + 1.7f * rim + tex * (1.5f * (0.5f - pp) * sstep(0.0f, 0.4f, pig) + 0.6f * tu);
    d = _clampf(d, 0.2f, 3.0f);
    c = make_float3(_saturatef(c.x - (c.x - c.x * c.x) * (d - 1.0f)), _saturatef(c.y - (c.y - c.y * c.y) * (d - 1.0f)), _saturatef(c.z - (c.z - c.z * c.z) * (d - 1.0f)));
    float pr = fbm((fx - 1.0f) / (6.0f * sc), (fy - 1.0f) / (6.0f * sc), 0.0f, 2, sd + 32u);
    float rl = 1.0f + tex * 0.12f * (pr - p2);
    return make_float3(_saturatef(c.x * 0.975f * rl), _saturatef(c.y * 0.962f * rl), _saturatef(c.z * 0.930f * rl));
}

__DEVICE__ float3 tileMosaic(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h, float s,
                             float det, float fw, float tex, float sc, uint sd)
{
    float fx = (float)(x), fy = (float)(y);
    int ix = (int)(_floorf(fx / s)), iy = (int)(_floorf(fy / s));
    int pr = (int)(sc + 0.5f);
    if (pr < 1) pr = 1;
    float3 pa = rgbAt(tr, tg, tb, x, y, w, h), pl = rgbAt(tr, tg, tb, x - pr, y, w, h), pg = rgbAt(tr, tg, tb, x + pr, y, w, h);
    float3 pu = rgbAt(tr, tg, tb, x, y - pr, w, h), pd = rgbAt(tr, tg, tb, x, y + pr, w, h);
    float3 cp = likeMean(pa, pl, pg, pu, pd);
    float ec = 0.5f * _fmaxf(_fmaxf(_fmaxf(_fabs(pg.x - pl.x), _fabs(pg.y - pl.y)), _fabs(pg.z - pl.z)),
                             _fmaxf(_fmaxf(_fabs(pd.x - pu.x), _fabs(pd.y - pu.y)), _fabs(pd.z - pu.z)));
    float3 ql = rgbAt(tr, tg, tb, x - 3 * pr, y, w, h), qg = rgbAt(tr, tg, tb, x + 3 * pr, y, w, h);
    float3 qu = rgbAt(tr, tg, tb, x, y - 3 * pr, w, h), qd = rgbAt(tr, tg, tb, x, y + 3 * pr, w, h);
    ec = _fminf(ec, 0.5f * _fmaxf(_fmaxf(_fmaxf(_fabs(qg.x - ql.x), _fabs(qg.y - ql.y)), _fabs(qg.z - ql.z)),
                                  _fmaxf(_fmaxf(_fabs(qd.x - qu.x), _fabs(qd.y - qu.y)), _fabs(qd.z - qu.z))));
    float f1 = 99.0f, f2 = 99.0f;
    float3 tc = cp;
    int bi = 0, bj = 0;
    int r = (int)(0.3f * s + 0.5f);
    float kc = 0.5f + 2.5f * det;
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            int ci = ix + i, cj = iy + j;
            float cx = ((float)(ci) + 0.5f + (rnd3(ci, cj, sd + 1u) - 0.5f) * 0.12f) * s;
            float cy = ((float)(cj) + 0.5f + (rnd3(ci, cj, sd + 2u) - 0.5f) * 0.12f) * s;
            int qx = (int)(_floorf(cx)), qy = (int)(_floorf(cy));
            float3 ca = rgbAt(tr, tg, tb, qx, qy, w, h), cl = rgbAt(tr, tg, tb, qx - r, qy, w, h), cr = rgbAt(tr, tg, tb, qx + r, qy, w, h);
            float3 cu = rgbAt(tr, tg, tb, qx, qy - r, w, h), cd = rgbAt(tr, tg, tb, qx, qy + r, w, h);
            float gx = (luma(cr.x, cr.y, cr.z) - luma(cl.x, cl.y, cl.z)) * 0.5f, gy = (luma(cd.x, cd.y, cd.z) - luma(cu.x, cu.y, cu.z)) * 0.5f;
            float2 t = runDir(gx, gy, 0.0f, fw, 4.0f);
            float dx = fx - cx, dy = fy - cy;
            float u = (dx * t.x + dy * t.y) / s, v = (-dx * t.y + dy * t.x) / s;
            float dl = _fmaxf(_fabs(u), _fabs(v));
            float3 pc = likeMean(ca, cl, cr, cu, cd);
            float dc = _sqrtf((pc.x - cp.x) * (pc.x - cp.x) + (pc.y - cp.y) * (pc.y - cp.y) + (pc.z - cp.z) * (pc.z - cp.z));
            float dd = dl + kc * sstep(0.06f, 0.36f, dc) * dc;
            if (dd < f1) { f2 = f1; f1 = dd; tc = pc; bi = ci; bj = cj; }
            else if (dd < f2) { f2 = dd; }
        }
    }
    float tv = 0.97f + 0.09f * rnd3(bi, bj, sd + 3u);
    float gap = f2 - f1;
    float bev = 0.90f + 0.10f * sstep(0.0f, 0.10f, gap);
    float sf = 1.0f + tex * 0.07f * (vnoise3(fx / (2.0f * sc) + 4096.0f, fy / (2.0f * sc) + 4096.0f, 0.0f, sd + 4u) - 0.5f);
    float k = tv * bev * sf;
    float3 tile = make_float3(_saturatef(tc.x * k), _saturatef(tc.y * k), _saturatef(tc.z * k));
    float gw = (0.6f + 2.0f * tex) * sc / s, aw = 0.7f / s;
    float grout = 1.0f - sstep(gw - aw, gw + aw, gap);
    grout = _fmaxf(grout, sstep(0.12f, 0.25f, ec) * (0.5f + 0.5f * det));
    float gn = 0.04f * (rnd3(x, y, sd + 5u) - 0.5f);
    float3 gc = make_float3(0.34f + gn, 0.32f + gn, 0.30f + gn);
    return mix3(tile, gc, grout);
}

__DEVICE__ float3 sprayPaint(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float fx, float fy, int w, int h, float R,
                             float det, float vib, float tex, float sc, uint sd)
{
    float n = 3.0f + _floorf(det * 3.0f + 0.5f);
    float hs = 0.5f * R;
    int jx = (int)(fx + (rnd3((int)(fx), (int)(fy), sd + 71u) - 0.5f) * hs), jy = (int)(fy + (rnd3((int)(fx), (int)(fy), sd + 72u) - 0.5f) * hs);
    float3 c = toneCut(tent9(tr, tg, tb, jx, jy, w, h, (int)(hs + 0.5f)), n, 0.75f);
    for (int k = 0; k < 3; k++) {
        float cs = (k == 0 ? 2.5f : (k == 1 ? 5.0f : 10.0f)) * sc;
        float occ = k == 0 ? 0.7f : (k == 1 ? 0.45f : 0.2f);
        int ci = (int)(_floorf(fx / cs)), cj = (int)(_floorf(fy / cs));
        uint ks = sd + (uint)(k) * 37u + 50u;
        float rr = (0.2f + 0.22f * rnd3(ci, cj, ks + 1u)) * cs;
        float px = ((float)(ci) + 0.5f + (rnd3(ci, cj, ks + 2u) - 0.5f) * 0.12f) * cs, py = ((float)(cj) + 0.5f + (rnd3(ci, cj, ks + 3u) - 0.5f) * 0.12f) * cs;
        float dd = _sqrtf((fx - px) * (fx - px) + (fy - py) * (fy - py));
        float on = (1.0f - sstep(rr - 0.6f, rr + 0.6f, dd)) * (rnd3(ci, cj, ks + 4u) < occ ? 1.0f : 0.0f);
        if (on > 0.0f) {
            float ra = 2.5f * R * _sqrtf(rnd3(ci, cj, ks + 5u)), aa = 6.2831853f * rnd3(ci, cj, ks + 6u);
            float3 dc = bilL(tr, tg, tb, px + ra * _cosf(aa), py + ra * _sinf(aa), w, h);
            c = mix3(c, toneCut(dc, n, 0.75f), 0.9f * on);
        }
    }
    c = satur(c, 1.0f + 0.6f * vib);
    float mist = rnd3((int)(fx), (int)(fy), sd + 61u) - 0.5f;
    float g = 1.0f + tex * 0.08f * mist;
    return make_float3(_saturatef(c.x * g), _saturatef(c.y * g), _saturatef(c.z * g));
}
