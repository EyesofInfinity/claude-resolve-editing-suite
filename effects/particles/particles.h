// Develop particles: the shared code of Develop Particles and Develop Particles Depth. MIT License.
//
// Copyright (c) 2026 the Claude Resolve Editing Suite authors
// Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
// documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
// rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
// permit persons to whom the Software is furnished to do so, subject to the following conditions: the above copyright
// notice and this permission notice shall be included in all copies or substantial portions of the Software.
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.
//
// Every particle is a pure function of its cell, the seed and the time, so any frame renders on its own and
// scrubbing works. Particles live in depth: each sits at a disparity q (1 is the nearest thing in the shot, as in
// Develop Depth's pass, 0 is infinity; up to 1.6 is between that thing and the lens). Screen size, spacing and speed
// scale with q as perspective does; a thin lens spreads each one over a disc of radius Blur times |q - focus|; the
// shutter drags it along its path; a depth pass, when given, hides it behind what is nearer. Light is added in linear
// (Rec.709 gamma 2.4 in and out); snow and ash are composited, lit by the light the picture shows around them.

#include "../light/light.h"
#include "../glitch/glitch.h"

__DEVICE__ float segDist(float px, float py, float ax, float ay, float bx, float by)
{
    float vx = bx - ax, vy = by - ay, wx = px - ax, wy = py - ay;
    float l2 = vx * vx + vy * vy;
    float h = l2 > 0.000001f ? _saturatef((wx * vx + wy * vy) / l2) : 0.0f;
    float dx = wx - h * vx, dy = wy - h * vy;
    return _sqrtf(dx * dx + dy * dy);
}

__DEVICE__ float spot(float u, float v, float R, float L, float s0)
{
    float hl = 0.5f * L;
    float du = _fmaxf(_fabs(u) - hl, 0.0f);
    float s = _fmaxf(s0, R * 0.55f);
    float g = _expf(-(du * du + v * v) / (2.0f * s * s)) / (6.2831853f * s * s + 2.5066283f * s * L);
    float Rd = _fmaxf(R, s0);
    float e = 0.5f + 0.06f * Rd;
    float c = _sqrtf(_fmaxf((Rd + e) * (Rd + e) - v * v, 0.0f));
    float Le = _fmaxf(L, 1.0f), hle = 0.5f * Le;
    float ov = _fmaxf(0.0f, _fminf(u + c, hle) - _fmaxf(u - c, -hle));
    float dd = _sqrtf(du * du + v * v);
    float rr = _saturatef(dd / Rd);
    float disc = ov / Le * (1.0f - sstep(Rd - e, Rd + e, dd)) * (0.9f + 0.25f * rr * rr * rr * rr) / (3.1415927f * Rd * Rd);
    return lerp1(g, disc, sstep(1.4f * s0, 3.5f * s0, R));
}

__DEVICE__ float lensSpot(float u, float v, float R, float L, float s0, float ou, float ov, float ring, float ph,
                          float mott, float ma, float mb)
{
    float hl = 0.5f * L;
    float du = _fmaxf(_fabs(u) - hl, 0.0f);
    float av = _fabs(v);
    float s = _fmaxf(s0, R * 0.55f);
    float g = _expf(-(du * du + v * v) / (2.0f * s * s)) / (6.2831853f * s * s + 2.5066283f * s * L);
    float Rd = _fmaxf(R, s0);
    float e = 0.5f + 0.06f * Rd;
    float c = _sqrtf(_fmaxf((Rd + e) * (Rd + e) - av * av, 0.0f));
    float Le = _fmaxf(L, 1.0f), hle = 0.5f * Le;
    float ov2 = _fmaxf(0.0f, _fminf(u + c, hle) - _fmaxf(u - c, -hle));
    float dd = _sqrtf(du * du + av * av);
    float rr = _saturatef(dd / Rd);
    float pu = u - _clampf(u, -hl, hl);
    float dc = _sqrtf((pu - ou) * (pu - ou) + (v - ov) * (v - ov));
    float edge = _fminf(1.0f - sstep(Rd - e, Rd + e, dd), 1.0f - sstep(Rd - e, Rd + e, dc));
    float big = sstep(5.0f, 14.0f, Rd);
    float r2 = rr * rr;
    float prof = (0.8f + 0.42f * r2 * r2 * r2 + big * ring * 0.09f * _sinf(26.0f * r2 + ph) * (1.0f - r2 * r2)) / 0.91f;
    float mo = 1.0f + big * mott * _sinf(3.7f * pu / Rd + 5.1f * v / Rd + ma) * _sinf(4.3f * v / Rd - 2.9f * pu / Rd + mb);
    float disc = ov2 / Le * edge * prof * mo / (3.1415927f * Rd * Rd);
    return lerp1(g, disc, sstep(1.4f * s0, 3.5f * s0, R));
}

__DEVICE__ float3 pathUVs(float px, float py, float ax, float ay, float bx, float by)
{
    float vx = bx - ax, vy = by - ay;
    float l = _sqrtf(vx * vx + vy * vy);
    float ux = l > 0.0001f ? vx / l : 1.0f, uy = l > 0.0001f ? vy / l : 0.0f;
    float wx = px - 0.5f * (ax + bx), wy = py - 0.5f * (ay + by);
    float v = -wx * uy + wy * ux;
    return make_float3(wx * ux + wy * uy, _fabs(v), v);
}

__DEVICE__ float2 pathUV(float px, float py, float ax, float ay, float bx, float by)
{
    float3 p = pathUVs(px, py, ax, ay, bx, by);
    return make_float2(p.x, p.y);
}

__DEVICE__ float poolLight(float d, float rho, float reach)
{
    float q = d * d + rho * rho;
    return rho / (6.2831853f * q * _sqrtf(q)) * (1.0f - sstep(0.5f * reach, reach, d));
}

// ---- the camera match. effects/particles/camera.py bakes a shot's camera path into PC_META and

__DEVICE__ float camG(float q)
{
    if (q <= 1.0f) {
        float x = _fmaxf(q, 0.0f) * 10.0f;
        int i = (int)(_floorf(x));
        if (i > 9) i = 9;
        return PC_META[16 + i] + (PC_META[17 + i] - PC_META[16 + i]) * (x - (float)(i));
    }
    return PC_META[26] + PC_META[14] * (q - 1.0f);
}

__DEVICE__ float camQ(int i, int k, float w0, float w1, float w2)
{
    int b = i * 10 + k;
    return PC_CAM[b] * w0 + PC_CAM[b + 3] * w1 + PC_CAM[b + 6] * w2;
}

__DEVICE__ float4 camAt(float ts, float q, float amt)
{
    int n = (int)(PC_META[0]);
    if (n < 2 || amt <= 0.0f) return make_float4(0.0f, 0.0f, 0.0f, 0.0f);
    float x = _clampf(ts * PC_META[1], 0.0f, (float)(n - 1));
    int i = (int)(_floorf(x));
    if (i > n - 2) i = n - 2;
    float f = x - (float)(i);
    float q0 = PC_META[3], q1 = PC_META[4], q2 = PC_META[5];
    float g = _clampf(camG(q), q0, q2);
    float w0 = (g - q1) * (g - q2) / ((q0 - q1) * (q0 - q2));
    float w1 = (g - q0) * (g - q2) / ((q1 - q0) * (q1 - q2));
    float w2 = (g - q0) * (g - q1) / ((q2 - q0) * (q2 - q1));
    float tx = lerp1(camQ(i, 0, w0, w1, w2), camQ(i + 1, 0, w0, w1, w2), f);
    float ty = lerp1(camQ(i, 1, w0, w1, w2), camQ(i + 1, 1, w0, w1, w2), f);
    float ls = lerp1(camQ(i, 2, w0, w1, w2), camQ(i + 1, 2, w0, w1, w2), f);
    float rl = lerp1(PC_CAM[i * 10 + 9], PC_CAM[i * 10 + 19], f);
    return make_float4(tx * amt, ty * amt, ls * amt, rl * amt);
}

__DEVICE__ float2 camReach(float q, float amt)
{
    if (PC_META[0] < 1.5f || amt <= 0.0f) return make_float2(0.0f, 1.0f);
    float g = _clampf(camG(q), PC_META[3], PC_META[5]);
    float k = g < PC_META[4] ? (g - PC_META[3]) / (PC_META[4] - PC_META[3]) : (g - PC_META[4]) / (PC_META[5] - PC_META[4]);
    float v = g < PC_META[4] ? lerp1(PC_META[6], PC_META[7], k) : lerp1(PC_META[7], PC_META[8], k);
    float s = g < PC_META[4] ? lerp1(PC_META[9], PC_META[10], k) : lerp1(PC_META[10], PC_META[11], k);
    return make_float2(v * amt, _fminf(1.0f, _expf(_logf(_fmaxf(s, 0.05f)) * amt)));
}

__DEVICE__ float2 camFwd(float4 c, float x, float y, float cx, float cy, float sc)
{
    float s = _expf(c.z), cr = _cosf(c.w), sr = _sinf(c.w);
    float ux = x - cx, uy = y - cy;
    return make_float2(cx + s * (cr * ux - sr * uy) + c.x * sc, cy + s * (sr * ux + cr * uy) + c.y * sc);
}

__DEVICE__ float2 camInv(float4 c, float x, float y, float cx, float cy, float sc)
{
    float s = _expf(c.z), cr = _cosf(c.w), sr = _sinf(c.w);
    float ux = x - cx - c.x * sc, uy = y - cy - c.y * sc;
    return make_float2(cx + (cr * ux + sr * uy) / s, cy + (-sr * ux + cr * uy) / s);
}

__DEVICE__ float glowTail(float d, float tau, float reach)
{
    return _expf(-d / tau) / (6.2831853f * tau * tau) * (1.0f - sstep(0.6f * reach, reach, d));
}

__DEVICE__ float3 bbody(float T)
{
    float a = 0.014388f / _fmaxf(T, 300.0f);
    float ur = a / 610e-9f, ug = a / 550e-9f, ub = a / 465e-9f;
    float rg = 0.5963f * _expf(ug - ur) * (1.0f - _expf(-ug)) / (1.0f - _expf(-ur));
    float bg = 2.3097f * _expf(ug - ub) * (1.0f - _expf(-ug)) / (1.0f - _expf(-ub));
    float m = _fmaxf(rg, _fmaxf(1.0f, bg));
    return make_float3(rg / m, 1.0f / m, bg / m);
}

__DEVICE__ float4 probe(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float sx, float sy, float r, int W, int H)
{
    float mr = 0.0f, mg = 0.0f, mb = 0.0f, mx = 0.0f;
    for (int k = 0; k < 9; k++) {
        float ox = 0.0f, oy = 0.0f;
        if (k > 0) {
            float a = 0.7853982f * (float)(k);
            ox = r * _cosf(a); oy = r * _sinf(a);
        }
        float3 c = rgbAt(tr, tg, tb, (int)(sx + ox), (int)(sy + oy), W, H);
        float lr = toLin(_saturatef(c.x)), lg = toLin(_saturatef(c.y)), lb = toLin(_saturatef(c.z));
        mr += lr; mg += lg; mb += lb;
        mx = _fmaxf(mx, luma(lr, lg, lb));
    }
    return make_float4(mr / 9.0f, mg / 9.0f, mb / 9.0f, mx);
}

__DEVICE__ float3 whiteLight(float4 p, float alb)
{
    float ml = _fmaxf(luma(p.x, p.y, p.z), 0.00001f);
    float il = _fminf(6.0f * ml, 1.2f * _fmaxf(p.w, ml)) * alb;
    float cr = lerp1(1.0f, p.x / ml, 0.33f), cg = lerp1(1.0f, p.y / ml, 0.33f), cb = lerp1(1.0f, p.z / ml, 0.33f);
    float cl = _fmaxf(luma(cr, cg, cb), 0.00001f);
    return make_float3(il * cr / cl, il * cg / cl, il * cb / cl);
}

__DEVICE__ float sceneKey(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int W, int H)
{
    float s = 0.0f;
    for (int j = 0; j < 4; j++) {
        for (int i = 0; i < 4; i++) {
            float3 c = rgbAt(tr, tg, tb, (int)(((float)(i) + 0.5f) * (float)(W) * 0.25f), (int)(((float)(j) + 0.5f) * (float)(H) * 0.25f), W, H);
            s += _logf(0.001f + luma(toLin(_saturatef(c.x)), toLin(_saturatef(c.y)), toLin(_saturatef(c.z))));
        }
    }
    return _expf(s / 16.0f);
}

__DEVICE__ float4 airField(float x, float y, float t, float amp, float lam, float w, float base)
{
    float fx = 0.0f, fy = 0.0f, vx = 0.0f, vy = 0.0f;
    for (int k = 0; k < 3; k++) {
        float fk = (float)(k);
        float a1 = base + 2.3999632f * fk, a2 = base + 1.1f + 2.3999632f * fk;
        float ph1 = base * (3.0f + fk), ph2 = base * (5.0f + 2.0f * fk) + 0.7f;
        float kk = 6.2831853f / lam * (0.6f + 0.4f * fk), ww = w * (0.7f + 0.45f * fk);
        float am = amp / (1.0f + 0.6f * fk);
        float u1 = kk * (x * _cosf(a1) + y * _sinf(a1)) + ww * t + ph1;
        float u2 = kk * (x * _cosf(a2) + y * _sinf(a2)) - ww * t + ph2;
        fx += am * _sinf(u1); fy += am * _sinf(u2);
        vx += am * ww * _cosf(u1); vy -= am * ww * _cosf(u2);
    }
    return make_float4(fx, fy, vx, vy);
}

__DEVICE__ float2 burstAt(float t, float per, uint sd)
{
    float k = _floorf(t / per);
    float tk = (k + 0.6f * hash01(sd + 17u, (uint)(k + 65536.0f), 11u)) * per;
    if (t < tk) {
        k = k - 1.0f;
        tk = (k + 0.6f * hash01(sd + 17u, (uint)(k + 65536.0f), 11u)) * per;
    }
    return make_float2(tk, k);
}

__DEVICE__ float2 sparkAt(float tt, float ex, float ey, float vx0, float vy0, float kd, float gk, float th, float hx,
                          float hy, float vxb, float vyb)
{
    if (th >= 0.0f && tt > th) {
        float u = tt - th, eb = (1.0f - _expf(-kd * u)) / kd;
        return make_float2(hx + vxb * eb, hy + vyb * eb + gk * (u - eb));
    }
    float e = (1.0f - _expf(-kd * tt)) / kd;
    return make_float2(ex + vx0 * e, ey + vy0 * e + gk * (tt - e));
}

__DEVICE__ float4 sparkLight(float px, float py, float t, float sh, int n, float ex, float ey, float dir, float cone,
                            float vel, float sizeK, float qC, float qS, float qf, float blurK, float kel, float gainE,
                            float sc, int hasD, float D, uint sd, float burst, float bper, float yF, float glow)
{
    float ar = 0.0f, ag = 0.0f, ab = 0.0f, sl = 0.0f;
    float grav = 1400.0f * sc;
    float2 bk = burstAt(t, bper, sd);
    for (int i = 0; i < 240; i++) {
        if (i >= n) break;
        uint si = sd + (uint)(i) * 7919u;
        float life = 0.25f + 0.75f * hash01(si, 1u, 3u);
        float age = 0.0f, gen = 0.0f, kick = 1.0f, turn = 0.0f;
        if (hash01(si, 10u, 3u) < burst) {
            age = t - bk.x - 0.04f * hash01(si, 11u, 3u);
            gen = bk.y + 8192.0f;
            if (age < 0.0f) continue;
            turn = 0.45f * cone * (2.0f * hash01(sd + 23u, (uint)(bk.y + 65536.0f), 13u) - 1.0f);
            kick = 1.25f;
        } else {
            float rest = 0.05f + 0.6f * hash01(si, 2u, 3u);
            float per = life + rest;
            float off = per * hash01(si, 3u, 3u);
            gen = _floorf((t + off) / per);
            age = t + off - gen * per;
        }
        if (age > life + sh) continue;
        uint sg = si + (uint)(gen + 4096.0f) * 131u;
        float q = qC * _expf(qS * (hash01(sg, 4u, 5u) - 0.5f));
        float ang = dir + turn + cone * (2.0f * hash01(sg, 5u, 5u) - 1.0f) * (0.5f + 0.5f * hash01(sg, 9u, 5u));
        float v0 = vel * q * kick * (0.8f + 1.6f * hash01(sg, 6u, 5u));
        float vx0 = v0 * _sinf(ang), vy0 = -v0 * _cosf(ang);
        float kd = 0.4f + 0.9f * hash01(sg, 7u, 5u);
        float g = grav * q;
        float gk = g / kd;
        float th = -1.0f, hx = 0.0f, hy = 0.0f, vxb = 0.0f, vyb = 0.0f;
        float dyF = yF - ey;
        if (dyF > 4.0f * sc) {
            float tn = (vy0 + _sqrtf(vy0 * vy0 + 2.0f * g * dyF)) / _fmaxf(g, 0.001f);
            for (int k = 0; k < 4; k++) {
                float ek = _expf(-kd * tn), en = (1.0f - ek) / kd;
                float fy = vy0 * en + gk * (tn - en) - dyF;
                float vy = vy0 * ek + gk * (1.0f - ek);
                tn = tn - fy / _fmaxf(vy, 1.0f);
            }
            if (tn > 0.0f && tn < life) {
                th = tn;
                float eh = _expf(-kd * th), en = (1.0f - eh) / kd;
                hx = ex + vx0 * en;
                hy = yF;
                vxb = vx0 * eh * (0.35f + 0.35f * hash01(sg, 12u, 5u));
                vyb = -(vy0 * eh + gk * (1.0f - eh)) * (0.22f + 0.28f * hash01(sg, 13u, 5u));
            }
        }
        float ta = _fmaxf(0.0f, age - sh), tb = _fmaxf(0.0f, age - 0.5f * sh), tc = _fminf(age, life);
        if (tc <= ta) continue;
        if (th > ta && th < tc) tb = th;
        float2 p1 = sparkAt(ta, ex, ey, vx0, vy0, kd, gk, th, hx, hy, vxb, vyb);
        float2 p2 = sparkAt(tb, ex, ey, vx0, vy0, kd, gk, th, hx, hy, vxb, vyb);
        float2 p3 = sparkAt(tc, ex, ey, vx0, vy0, kd, gk, th, hx, hy, vxb, vyb);
        float x1 = p1.x, y1 = p1.y, x2 = p2.x, y2 = p2.y, x3 = p3.x, y3 = p3.y;
        float alive = (tc - ta) / _fmaxf(sh, 0.0001f);
        float jit = 0.9f + 0.2f * hash01(sg, 8u, 5u);
        float hot = th >= 0.0f ? 0.2f : 0.0f;
        float u1 = _saturatef(0.5f * (ta + tb) / life + (th >= 0.0f && tb > th ? hot : 0.0f));
        float u2 = _saturatef(0.5f * (tb + tc) / life + (th >= 0.0f && tc > th ? hot : 0.0f));
        float T1 = kel * (1.0f - 0.55f * u1) * jit, T2 = kel * (1.0f - 0.55f * u2) * jit;
        float b1 = _powf(T1 / 2000.0f, 6.0f) * (1.0f - sstep(0.75f, 1.0f, u1)), b2 = _powf(T2 / 2000.0f, 6.0f) * (1.0f - sstep(0.75f, 1.0f, u2));
        float E = gainE * sizeK * q * q * alive;
        if (glow > 0.0f) {
            float rl = (40.0f + 140.0f * q) * sc;
            float d3 = _sqrtf((px - x3) * (px - x3) + (py - y3) * (py - y3));
            if (d3 < rl) sl += glow * E * b2 * poolLight(d3, 0.3f * rl, rl);
        }
        float R = blurK * _fabs(q - qf);
        float reach = R + 14.0f * sc + 2.0f;
        float bx0 = _fminf(x1, _fminf(x2, x3)) - reach, bx1 = _fmaxf(x1, _fmaxf(x2, x3)) + reach;
        float by0 = _fminf(y1, _fminf(y2, y3)) - reach, by1 = _fmaxf(y1, _fmaxf(y2, y3)) + reach;
        if (px < bx0 || px > bx1 || py < by0 || py > by1) continue;
        float d = _fminf(segDist(px, py, x1, y1, x2, y2), segDist(px, py, x2, y2, x3, y3));
        float L1 = _sqrtf((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1)), L2 = _sqrtf((x3 - x2) * (x3 - x2) + (y3 - y2) * (y3 - y2));
        float L = _fmaxf(L1 + L2, 0.0001f);
        float3 col = bbody(0.5f * (T1 + T2));
        float vis = hasD ? sstep(D - 0.05f, D + 0.01f, q) : 1.0f;
        float2 w1 = pathUV(px, py, x1, y1, x2, y2), w2 = pathUV(px, py, x2, y2, x3, y3);
        float sp2 = L1 / L * b1 * spot(w1.x, w1.y, R, L1, 0.75f * sc) + L2 / L * b2 * spot(w2.x, w2.y, R, L2, 0.75f * sc);
        float I = E * vis * (sp2 + 0.05f * 0.5f * (b1 + b2) * glowTail(d, 3.5f * sc, 14.0f * sc));
        ar += I * col.x; ag += I * col.y; ab += I * col.z;
    }
    return make_float4(ar, ag, ab, sl);
}

__DEVICE__ float3 particlesRun(int W, int H, int x, int y, __TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb,
                               __TEXTURE__ td, int hasD, float amount, float style, float density, float size,
                               float speed, float wind, float dirDeg, float srcX, float srcY, float spread,
                               float depthC, float depthS, float focus, float blur, float shutter, float fps,
                               float temp, float lit, float panX, float panY, float seed, float dAmt,
                               float shotStart, float camera, float glow, float srcGlow, float floorY, float bursts,
                               int frame)
{
    float3 c0 = rgbAt(tr, tg, tb, x, y, W, H);
    if (amount <= 0.0f) return c0;
    float yr = ((float)(y) + 0.5f) / (float)(H);
    if (_fmaxf(c0.x, _fmaxf(c0.y, c0.z)) <= 0.002f && (yr < 0.13f || yr > 0.87f)) {
        float rowMax = 0.0f;
        for (int k = 0; k < 9; k++) {
            float3 cb = rgbAt(tr, tg, tb, (int)((0.05f + 0.1125f * (float)(k)) * (float)(W)), y, W, H);
            rowMax = _fmaxf(rowMax, _fmaxf(cb.x, _fmaxf(cb.y, cb.z)));
        }
        if (rowMax <= 0.002f) return c0;
    }
    int st = (int)(style + 0.5f);
    float sc = (float)(H) / 1080.0f;
    float px = (float)(x) + 0.5f, py = (float)(y) + 0.5f;
    float rate = _fmaxf(fps, 1.0f);
    float t = (float)(frame) / rate;
    float sh = _clampf(shutter, 0.0f, 360.0f) / 360.0f / rate;
    float dens = _saturatef(density / 100.0f), szf = 0.2f + 1.6f * _saturatef(size / 100.0f), sp = 0.1f + 1.8f * _saturatef(speed / 100.0f);
    float wd = wind / 100.0f, tp = temp / 100.0f, lt = _saturatef(lit / 100.0f);
    float qf = _fmaxf(focus, 0.0f) / 100.0f;
    float blurK = _saturatef(blur / 100.0f) * 24.0f * sc;
    uint sd = (uint)(seed + 0.5f) * 977u + 101u;
    float lr = toLin(c0.x), lg = toLin(c0.y), lb = toLin(c0.z);
    float br = lr, bgg = lg, bb = lb;
    float D = 0.0f, dk = 0.0f;
    if (hasD != 0) { D = _saturatef(_tex2D(td, x, y)); dk = _saturatef(dAmt); }
    float key = -1.0f;
    float kAdd = 0.0f, kA = 0.0f;
    float exA = srcX / 100.0f * (float)(W), eyA = srcY / 100.0f * (float)(H);
    float cxs = 0.5f * (float)(W), cys = 0.5f * (float)(H);
    float ts = t - shotStart;
    float cam = _saturatef(camera / 100.0f);
    int camOn = PC_META[0] > 1.5f && cam > 0.0f ? 1 : 0;
    float4 zero4 = make_float4(0.0f, 0.0f, 0.0f, 0.0f);
    float gl = 8.0f * _saturatef(glow / 100.0f);
    float slr = 0.0f, slg = 0.0f, slb = 0.0f;
    if (st == 2) {
        key = sceneKey(tr, tg, tb, W, H);
        float expo = lerp1(1.0f, _clampf(0.06f / key, 0.3f, 3.0f), lt);
        float qC = _clampf(0.4f * depthC / 50.0f, 0.02f, 1.6f), qS = 0.5f * depthS / 50.0f;
        float4 cmS = camOn != 0 ? camAt(ts, qC, cam) : zero4;
        float2 wp = camOn != 0 ? camInv(cmS, px, py, cxs, cys, sc) : make_float2(px, py);
        int n = (int)(16.0f + 224.0f * dens * dens);
        float cone = 0.05f + 1.2f * _saturatef(spread / 100.0f);
        float bsh = _saturatef(bursts / 100.0f);
        float bper = 1.4f + 1.0f / sp;
        float yF = floorY < 140.0f ? floorY / 100.0f * (float)(H) : -1000000.0f;
        float kel = 2100.0f * (1.0f + 0.25f * tp);
        float4 s = sparkLight(wp.x, wp.y, t, sh, n, exA, eyA, dirDeg * 0.0174533f, cone, 2400.0f * sp * sc, szf * szf,
                              qC, qS, qf, blurK, kel, 700.0f * expo, sc, hasD, D * dk, sd, bsh, bper, yF, 0.35f * gl);
        lr += s.x; lg += s.y; lb += s.z;
        kAdd = _fmaxf(s.x, _fmaxf(s.y, s.z));
        float3 cl = bbody(0.8f * kel);
        slr += s.w * cl.x; slg += s.w * cl.y; slb += s.w * cl.z;
        if (srcGlow > 0.0f) {
            float sgA = _saturatef(srcGlow / 100.0f);
            float2 bk = burstAt(t, bper, sd);
            float flare = bsh * 3.0f * _expf(-(t - bk.x) / 0.09f);
            float flick = 0.8f + 0.2f * _sinf(37.0f * t + 1.3f) * _sinf(23.0f * t + 0.4f + 0.01f * (float)(sd));
            float Es = 700.0f * expo * szf * szf * qC * qC * sgA * 2.5f * (flick + flare);
            float ds = _sqrtf((wp.x - exA) * (wp.x - exA) + (wp.y - eyA) * (wp.y - eyA));
            float Rs = blurK * _fabs(qC - qf);
            float rc = (1.0f + 3.0f * _saturatef(spread / 100.0f)) * szf * sc;
            float vsS = hasD != 0 ? lerp1(1.0f, sstep(D - 0.05f, D + 0.01f, qC), dk) : 1.0f;
            float3 cs = bbody(kel * (1.05f + 0.1f * _fminf(flare, 1.0f)));
            float Is = Es * vsS * (spot(ds, 0.0f, Rs, 0.0f, _fmaxf(0.75f * sc, rc)) + 0.06f * glowTail(ds, 9.0f * sc, 80.0f * sc)
                                   + 0.01f * glowTail(ds, 40.0f * sc, 260.0f * sc));
            lr += Is * cs.x; lg += Is * cs.y; lb += Is * cs.z;
            kAdd = _fmaxf(kAdd, Is);
            float rS = 0.42f * (float)(H);
            if (gl > 0.0f && ds < rS) {
                float ps = 1.5f * gl * Es * vsS * poolLight(ds, 0.12f * rS, rS);
                slr += ps * cs.x; slg += ps * cs.y; slb += ps * cs.z;
            }
        }
    } else {
        int N = 6;
        float cell1 = 60.0f, prob = 0.0f, vx = 0.0f, vy = 0.0f, amp = 16.0f, lam = 380.0f, aw = 0.35f, qc = 0.55f, qs = 1.0f;
        float r0b = 0.4f, tailT = 0.0f, tailW = 0.0f, rot = 0.0f;
        if (st == 0) { prob = 0.05f + 0.8f * dens * dens; vx = 30.0f * wd; vy = 5.0f; }
        if (st == 1) { N = 10; cell1 = 100.0f; prob = 0.05f + 0.5f * dens * dens; vx = 90.0f * wd; vy = -1300.0f; amp = 26.0f; lam = 600.0f; aw = 1.3f; qc = 0.45f; qs = 0.7f; r0b = 0.8f; tailT = 3.0f; tailW = 0.06f; rot = 0.45f; }
        if (st == 3) { cell1 = 46.0f; prob = 0.10f + 0.9f * _powf(dens, 1.2f); vx = 170.0f * wd; vy = 110.0f; amp = 14.0f; lam = 340.0f; aw = 0.8f; qc = 0.35f; qs = 1.5f; r0b = 4.0f; rot = 0.18f; }
        if (st == 4) { N = 4; cell1 = 210.0f; prob = 0.06f + 0.6f * dens; vx = 12.0f * wd; vy = -4.0f; amp = 30.0f; lam = 700.0f; aw = 0.5f; qc = 0.45f; qs = 0.9f; r0b = 0.9f; tailT = 5.0f; tailW = 0.12f; }
        if (st >= 5) { N = 4; cell1 = 320.0f; prob = 0.03f + 0.22f * dens; vx = 14.0f * wd; vy = -7.0f; amp = 30.0f; lam = 800.0f; aw = 0.25f; qc = 0.5f; qs = 0.9f; r0b = 4.0f; tailT = 9.0f; tailW = 0.5f; }
        float qcen = _clampf(qc * depthC / 50.0f, 0.02f, 1.6f), qsp = qs * _fmaxf(depthS, 0.0f) / 50.0f;
        float lo = _fmaxf(0.02f, qcen * _expf(-qsp)), hi = _fminf(1.6f, qcen * _expf(qsp));
        if (hi < lo * 1.0001f) hi = lo * 1.0001f;
        float stepq = _powf(hi / lo, 1.0f / (float)(N - 1));
        float pr0 = -1.0f, pg0 = 0.0f, pb0 = 0.0f;
        for (int li = 0; li < 10; li++) {
            if (li >= N) break;
            float q = lo * _powf(stepq, (float)(li));
            uint ls = sd + (uint)(li) * 7907u + (uint)(st) * 131u;
            float base = 6.2831853f * hash01(ls, 1u, 2u);
            float th = rot * (2.0f * hash01(ls, 3u, 2u) - 1.0f), cth = _cosf(th), sth = _sinf(th);
            float4 cm = zero4;
            float csc = 1.0f, wqx = px, wqy = py, cwx = 0.0f, cwy = 0.0f;
            float2 crh = make_float2(0.0f, 1.0f);
            if (camOn != 0) {
                cm = camAt(ts, q, cam);
                csc = _expf(cm.z);
                float2 wq = camInv(cm, px, py, cxs, cys, sc);
                wqx = wq.x; wqy = wq.y;
                if (sh > 0.0f) {
                    float4 ca = camAt(ts - 0.5f * sh, q, cam), cb = camAt(ts + 0.5f * sh, q, cam);
                    float2 pa = camFwd(ca, wqx, wqy, cxs, cys, sc), pb = camFwd(cb, wqx, wqy, cxs, cys, sc);
                    float2 wa = camInv(cm, pa.x, pa.y, cxs, cys, sc), wb = camInv(cm, pb.x, pb.y, cxs, cys, sc);
                    cwx = wb.x - wa.x; cwy = wb.y - wa.y;
                }
                crh = camReach(q, cam);
            }
            float rx = cth * wqx + sth * wqy, ry = -sth * wqx + cth * wqy;
            float chx = 0.5f * (cth * cwx + sth * cwy), chy = 0.5f * (-sth * cwx + cth * cwy);
            float pvx = -3.0f * panX, pvy = -3.0f * panY;
            float Vx = (vx * sp + cth * pvx + sth * pvy) * q * sc, Vy = (vy * sp - sth * pvx + cth * pvy) * q * sc;
            float Aq = amp * q * sc, Lq = lam * q * sc, Wq = aw * sp;
            float Lh = (_sqrtf(Vx * Vx + 1.8225f * Vy * Vy) + Aq * Wq * 2.2f) * sh * 0.5f + crh.x * sc * sh * 0.5f;
            float tail = tailT > 0.0f ? 4.0f * tailT * sc * (st >= 5 ? 1.45f : 1.0f) : 0.0f;
            float r0max = r0b * 1.8f * q * _sqrtf(stepq) * sc;
            float cell = _fmaxf(cell1 * q * sc, (r0max + Lh + tail + 2.0f * sc) / (0.9f * crh.y));
            float Rcap = _fmaxf(0.9f * cell * crh.y - Lh - tail - r0max, 0.5f);
            float reachL = 0.85f * cell * csc;
            float Rw = blurK * _fabs(q - qf);
            float hz = st == 3 ? sstep(1.0f, 2.5f, Rw / Rcap) : 0.0f;
            float visL = lerp1(1.0f, sstep(D - 0.05f, D + 0.01f, q), dk);
            if (hz > 0.0f && visL > 0.0f) {
                if (pr0 < 0.0f) {
                    float4 pp = probe(tr, tg, tb, px, py, 45.0f * sc, W, H);
                    float3 wl = whiteLight(pp, 0.85f);
                    pr0 = lerp1(0.6f, wl.x, lt); pg0 = lerp1(0.62f, wl.y, lt); pb0 = lerp1(0.66f, wl.z, lt);
                }
                float r0v = r0b * szf * q * sc;
                float av = _fminf(0.6f, prob * 0.9f * 3.1415927f * r0v * r0v / (cell * cell)) * hz * visL;
                lr = lerp1(lr, pr0, av); lg = lerp1(lg, pg0, av); lb = lerp1(lb, pb0, av);
                kA = _fmaxf(kA, av);
            }
            float4 f0 = airField(rx, ry, t, Aq, Lq, Wq, base);
            float4 f1 = airField(rx - f0.x, ry - f0.y, t, Aq, Lq, Wq, base);
            float Sx = Vx * t;
            float Xx = rx - f1.x - Sx;
            int ix = (int)(_floorf(Xx / cell));
            for (int i = -1; i <= 1; i++) {
                int cx = ix + i;
                float cvy = Vy * (0.65f + 0.7f * rnd3(cx, 7, ls + 9u));
                float Sy = cvy * t;
                float Xy = ry - f1.y - Sy;
                int iy = (int)(_floorf(Xy / cell));
                for (int j = -1; j <= 1; j++) {
                    int cy = iy + j;
                    if (rnd3(cx, cy, ls) >= prob) continue;
                    float r1 = rnd3(cx, cy, ls + 1u), r2 = rnd3(cx, cy, ls + 2u), r3 = rnd3(cx, cy, ls + 3u);
                    float r4 = rnd3(cx, cy, ls + 4u), r5 = rnd3(cx, cy, ls + 5u);
                    float ow = (1.5f + 3.0f * r3) * Wq * (st == 3 ? 1.6f : 1.0f), wa = (st == 3 ? 0.10f : 0.06f) * cell;
                    float jr = 0.6f;
                    if (st == 1) { ow = (4.0f + 7.0f * r3) * sp; wa = 0.17f * cell; jr = 0.36f; }
                    float ph4 = ow * t + 6.2831853f * r4, ph5 = 0.77f * ow * t + 6.2831853f * r5;
                    float gx = ((float)(cx) + 0.5f + jr * (r1 - 0.5f)) * cell + wa * _sinf(ph4);
                    float gy = ((float)(cy) + 0.5f + jr * (r2 - 0.5f)) * cell + wa * _sinf(ph5);
                    float cdx = Xx - gx, cdy = Xy - gy;
                    if (cdx * cdx + cdy * cdy > 1.69f * cell * cell) continue;
                    float bpx = gx + Sx, bpy = gy + Sy;
                    float4 fp = airField(bpx, bpy, t, Aq, Lq, Wq, base);
                    float sx = bpx + fp.x, sy = bpy + fp.y;
                    float hx = (Vx + fp.z + wa * ow * _cosf(ph4)) * sh * 0.5f + chx, hy = (cvy + fp.w + 0.77f * wa * ow * _cosf(ph5)) * sh * 0.5f + chy;
                    float L = 2.0f * _sqrtf(hx * hx + hy * hy) * csc;
                    float d = segDist(rx, ry, sx - hx, sy - hy, sx + hx, sy + hy) * csc;
                    float3 uvs = pathUVs(rx, ry, sx - hx, sy - hy, sx + hx, sy + hy);
                    float2 uv = make_float2(uvs.x * csc, uvs.y * csc);
                    float wsx = cth * sx - sth * sy, wsy = sth * sx + cth * sy;
                    float2 ssp = camOn != 0 ? camFwd(cm, wsx, wsy, cxs, cys, sc) : make_float2(wsx, wsy);
                    float ssx = ssp.x, ssy = ssp.y;
                    float r6 = rnd3(cx, cy, ls + 6u), r7 = rnd3(cx, cy, ls + 7u), r8 = rnd3(cx, cy, ls + 8u);
                    float qp = q * _powf(stepq, r6 - 0.5f);
                    float r0 = r0b * szf * qp * sc;
                    float R = _fminf(blurK * _fabs(qp - qf), Rcap);
                    float Rd = _sqrtf(R * R + r0 * r0);
                    int seen = d <= Rd + tail + 2.0f * sc ? 1 : 0;
                    float dcen = _sqrtf((rx - sx) * (rx - sx) + (ry - sy) * (ry - sy)) * csc;
                    int lights = gl > 0.0f && dcen < reachL && (st == 4 || st >= 5 || (st == 1 && r7 >= 0.12f)) ? 1 : 0;
                    if (seen == 0 && lights == 0) continue;
                    float vis = lerp1(1.0f, sstep(D - 0.05f, D + 0.01f, qp), dk);
                    if (vis <= 0.0f) continue;
                    float s0p = st >= 5 ? _fmaxf(0.75f * sc, r0) : 0.75f * sc;
                    float pf = 0.0f, pfr = 0.0f, pfb = 0.0f;
                    if (seen != 0) {
                        if (st == 0 || st == 3 || R <= 3.0f * s0p) {
                            pf = spot(uv.x, uv.y, Rd, L, s0p);
                            pfr = pf; pfb = pf;
                        } else {
                            float ocx = cxs - ssx, ocy = cys - ssy;
                            float rn = _sqrtf(ocx * ocx + ocy * ocy) / _sqrtf(cxs * cxs + cys * cys);
                            float om = 1.1f * Rd * rn * _sqrtf(rn) / _fmaxf(_sqrtf(ocx * ocx + ocy * ocy), 0.001f);
                            float olx = (cth * ocx + sth * ocy) * om, oly = (-sth * ocx + cth * ocy) * om;
                            float hl2 = _sqrtf(hx * hx + hy * hy);
                            float pux = hl2 > 0.0001f ? hx / hl2 : 1.0f, puy = hl2 > 0.0001f ? hy / hl2 : 0.0f;
                            float ou = olx * pux + oly * puy, ov = -olx * puy + oly * pux;
                            float vsg = uvs.z * csc;
                            float rg = st >= 5 ? 1.0f : 0.55f + 0.45f * r2;
                            float mt = st >= 5 ? 0.3f : (st == 4 ? 0.08f : 0.04f);
                            float pr = 6.2831853f * r1, ma = 6.2831853f * r4, mb = 6.2831853f * r5;
                            float ca = qp < qf ? 0.05f : -0.05f;
                            pf = lensSpot(uv.x, vsg, Rd, L, s0p, ou, ov, rg, pr, mt, ma, mb);
                            pfr = lensSpot(uv.x, vsg, Rd * (1.0f + ca), L, s0p, ou, ov, rg, pr, mt, ma, mb);
                            pfb = lensSpot(uv.x, vsg, Rd * (1.0f - ca), L, s0p, ou, ov, rg, pr, mt, ma, mb);
                        }
                        if (st >= 5) {
                            float pc = spot(uv.x, uv.y, R, L, 0.75f * sc);
                            pf = 0.72f * pf + 0.28f * pc; pfr = 0.72f * pfr + 0.28f * pc; pfb = 0.72f * pfb + 0.28f * pc;
                        }
                    }
                    float fdp = lerp1(1.0f, 1.0f / (1.0f + 12.0f * (qp - D) * (qp - D)), dk);
                    if (st == 0) {
                        float4 pb = probe(tr, tg, tb, ssx, ssy, 30.0f * sc, W, H);
                        float4 pw = probe(tr, tg, tb, ssx, ssy, 90.0f * sc, W, H);
                        float ml = luma(pb.x, pb.y, pb.z);
                        float lw = _fmaxf(pb.w, pw.w);
                        float beam = sstep(0.08f, 0.55f, 0.5f * ml + 0.5f * pb.w) * (1.0f + 5.0f * sstep(0.55f, 0.98f, lw));
                        float illum = lerp1(0.6f, beam, lt) * (0.15f + 0.85f * r5 * r5);
                        float glint = 0.3f + 0.7f * _powf(0.5f + 0.5f * _sinf((3.0f + 6.0f * r7) * t + 6.2831853f * r8), 10.0f) * (r7 < 0.6f ? 1.0f : 0.4f);
                        float cr = ml > 0.0001f ? pb.x / ml : 1.0f, cg = ml > 0.0001f ? pb.y / ml : 1.0f, cbb = ml > 0.0001f ? pb.z / ml : 1.0f;
                        cr = lerp1(1.0f, cr, 0.6f * lt) * (1.0f + 0.25f * tp); cg = lerp1(1.0f, cg, 0.6f * lt); cbb = lerp1(1.0f, cbb, 0.6f * lt) * (1.0f - 0.25f * tp);
                        float Ib = 12.0f * szf * szf * qp * qp * illum * glint * vis;
                        float I = Ib * pf;
                        lr += Ib * pfr * cr; lg += I * cg; lb += Ib * pfb * cbb;
                        kAdd = _fmaxf(kAdd, I);
                    } else if (st == 1) {
                        float hgt = (eyA - wsy) / (float)(H);
                        float born = sstep(-0.02f, 0.03f, hgt);
                        float xb = wsx - (cth * Vx - sth * cvy) * (hgt * (float)(H)) / _fmaxf(_fabs(sth * Vx + cth * cvy), 1.0f);
                        float spr = _saturatef(spread / 100.0f);
                        float wdt = (0.03f + 0.9f * spr * spr) * (float)(W) * (1.0f + 1.2f * _fmaxf(hgt, 0.0f));
                        float plume = _expf(-((xb - exA) / wdt) * ((xb - exA) / wdt));
                        if (r7 < 0.12f) {
                            float4 pb = probe(tr, tg, tb, ssx, ssy, 40.0f * sc, W, H);
                            float3 wl = whiteLight(pb, 0.3f);
                            float ra = (1.6f + 1.4f * r8) * szf * qp * sc;
                            float Rda = _sqrtf(R * R + ra * ra);
                            float turn = 0.35f + 0.65f * _fabs(_sinf((2.0f + 4.0f * r3) * t + 6.2831853f * r4));
                            float a = _fminf(0.9f, 0.75f * 3.1415927f * ra * ra * spot(uv.x, uv.y, Rda, L, 0.75f * sc)) * turn * born * plume * (1.0f - sstep(1.3f, 1.6f, hgt)) * vis;
                            lr = lerp1(lr, lerp1(0.03f, wl.x, lt), a); lg = lerp1(lg, lerp1(0.03f, wl.y, lt), a); lb = lerp1(lb, lerp1(0.03f, wl.z, lt), a);
                            kA = _fmaxf(kA, a);
                        } else {
                            if (key < 0.0f) key = sceneKey(tr, tg, tb, W, H);
                            float expo = lerp1(1.0f, _clampf(0.06f / key, 0.3f, 3.0f), lt);
                            float hDie = 0.25f + 1.05f * r8;
                            float fade = 1.0f - sstep(0.7f * hDie, hDie, hgt);
                            float Tb = (1200.0f + 400.0f * r5) * (1.0f + 0.2f * tp);
                            float kc = 0.5f + 1.3f * r3;
                            float fl = 0.62f + 0.38f * _sinf((9.0f + 14.0f * r4) * t + 6.2831853f * r1) * _sinf((5.0f + 7.0f * r2) * t + 6.2831853f * r6);
                            float T = (700.0f + (Tb - 700.0f) * _expf(-_fmaxf(hgt, 0.0f) * kc)) * (0.94f + 0.06f * fl);
                            float bright = _powf(_saturatef((T - 650.0f) / 800.0f), 3.0f) * fl;
                            float3 col = bbody(T);
                            float E = 60.0f * szf * szf * qp * qp * bright * expo * born * fade * plume * vis;
                            if (seen != 0) {
                                float tl = tailW * glowTail(d, tailT * sc, tail);
                                float I = E * (pf + tl);
                                lr += E * (pfr + tl) * col.x; lg += I * col.y; lb += E * (pfb + tl) * col.z;
                                kAdd = _fmaxf(kAdd, I);
                            }
                            if (lights != 0) {
                                float pl = 0.35f * gl * E * fdp * poolLight(dcen, 0.3f * reachL + 2.0f * sc, reachL);
                                slr += pl * col.x; slg += pl * col.y; slb += pl * col.z;
                            }
                        }
                    } else if (st == 3) {
                        float4 pb = probe(tr, tg, tb, ssx, ssy, 60.0f * sc, W, H);
                        float3 wl = whiteLight(pb, 0.85f);
                        float fr = lerp1(0.6f, wl.x, lt) * (1.0f + 0.06f * tp), fg = lerp1(0.62f, wl.y, lt);
                        float fb = lerp1(0.66f, wl.z, lt) * (1.0f - 0.06f * tp);
                        float a = _fminf(0.95f, 0.9f * 3.1415927f * r0 * r0 * pf) * (1.0f - hz) * vis;
                        lr = lerp1(lr, fr, a); lg = lerp1(lg, fg, a); lb = lerp1(lb, fb, a);
                        kA = _fmaxf(kA, a);
                    } else {
                        if (key < 0.0f) key = sceneKey(tr, tg, tb, W, H);
                        float expo = lerp1(1.0f, _clampf(0.06f / key, 0.3f, 3.0f), lt);
                        float E = 0.0f, cr = 1.0f, cg = 1.0f, cbb = 1.0f;
                        if (st == 4) {
                            float per = (1.8f + 3.2f * r7) / sp;
                            float tau = (t / per + r8 - _floorf(t / per + r8)) * per;
                            float fl = _expf(-((tau - 0.35f) / 0.16f) * ((tau - 0.35f) / 0.16f)) + (r5 < 0.4f ? 0.5f * _expf(-((tau - 0.85f) / 0.12f) * ((tau - 0.85f) / 0.12f)) : 0.0f);
                            float low = sstep(0.05f, 0.45f, wsy / (float)(H));
                            E = 40.0f * szf * szf * qp * qp * (0.02f + fl) * low;
                            cr = tp >= 0.0f ? lerp1(0.62f, 1.0f, tp) : lerp1(0.62f, 0.25f, -tp);
                            cg = tp >= 0.0f ? lerp1(1.0f, 0.62f, tp) : lerp1(1.0f, 0.9f, -tp);
                            cbb = tp >= 0.0f ? 0.10f + 0.02f * tp : lerp1(0.10f, 1.0f, -tp);
                        } else {
                            float br5 = 0.6f + 0.4f * _sinf((0.5f + 0.8f * r7) * t + 6.2831853f * r8);
                            E = 120.0f * szf * szf * qp * qp * br5;
                            cr = tp >= 0.0f ? 1.0f : lerp1(1.0f, 0.55f, -tp);
                            cg = tp >= 0.0f ? lerp1(0.78f, 0.6f, tp) : lerp1(0.78f, 0.75f, -tp);
                            cbb = tp >= 0.0f ? lerp1(0.5f, 0.25f, tp) : lerp1(0.5f, 1.0f, -tp);
                        }
                        float Eg = E * expo * vis;
                        if (seen != 0) {
                            float tlT = tailT, tlW = tailW;
                            if (st >= 5) {
                                tlT = tailT * (0.55f + 0.9f * r3);
                                tlW = tailW * (0.5f + 0.9f * r5) * (0.8f + 0.2f * _sinf((0.3f + 0.4f * r2) * t + 6.2831853f * r6));
                            }
                            float tl = tlW * glowTail(d, tlT * sc, tail);
                            float I = Eg * (pf + tl);
                            lr += Eg * (pfr + tl) * cr; lg += I * cg; lb += Eg * (pfb + tl) * cbb;
                            kAdd = _fmaxf(kAdd, I);
                        }
                        if (lights != 0) {
                            float pl = gl * Eg * fdp * poolLight(dcen, 0.3f * reachL + 2.0f * sc, reachL);
                            slr += pl * cr; slg += pl * cg; slb += pl * cbb;
                        }
                    }
                }
            }
        }
    }
    if (slr + slg + slb > 0.0f) {
        if (key < 0.0f) key = sceneKey(tr, tg, tb, W, H);
        float ak = 1.0f / (5.5f * _fmaxf(key, 0.002f));
        float ar = _fminf(br * ak, 1.0f) * slr, ag = _fminf(bgg * ak, 1.0f) * slg, ab = _fminf(bb * ak, 1.0f) * slb;
        lr += ar; lg += ag; lb += ab;
        kAdd = _fmaxf(kAdd, _fmaxf(ar, _fmaxf(ag, ab)));
    }
    if (kAdd <= 0.0f && kA <= 0.0f) return c0;
    float Ln = luma(c0.x, c0.y, c0.z);
    float Lm = 0.25f * (lumaAt(tr, tg, tb, x - 1, y, W, H) + lumaAt(tr, tg, tb, x + 1, y, W, H) + lumaAt(tr, tg, tb, x, y - 1, W, H) + lumaAt(tr, tg, tb, x, y + 1, W, H));
    float gamp = 0.35f * sstep(0.003f, 0.03f, _fabs(Ln - Lm));
    float nz = 2.0f * hash01((uint)(x + 65536), (uint)(y + 65536), (uint)(frame + 65536) * 3u + sd) - 1.0f;
    float gm = 1.0f + gamp * nz;
    lr = br + (lr - br) * gm; lg = bgg + (lg - bgg) * gm; lb = bb + (lb - bb) * gm;
    float3 o = lightOut(lr, lg, lb, _fmaxf(kAdd, kA));
    float am = _saturatef(amount / 100.0f);
    return make_float3(lerp1(c0.x, o.x, am), lerp1(c0.y, o.y, am), lerp1(c0.z, o.z, am));
}
