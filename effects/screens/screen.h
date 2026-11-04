// Develop screen: the code of Develop Screen's eight modes, on lens.h (bilinear taps, light.h's hash and noise,
// glitch.h's dither finish) and jpeg.h (the DCT). Every helper takes its values as arguments. Positions are in
// pixels; sizes are given at 1080 lines and scaled by sc = height / 1080. MIT License.

#include "../lens/lens.h"
#include "jpeg.h"

// ---- 0 JPEG Damage ---------------------------------------------------------------------------------------------
__DEVICE__ float3 scJpeg(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h, float sc,
                         float str, float size, float rate, float col, int f, uint sd)
{
    float bs = _fmaxf(1.0f, _floorf(sc * (1.0f + 2.0f * size) + 0.5f));
    float Q = 2.0f + 93.0f * _powf(1.0f - str, 1.5f);
    float S = Q < 50.0f ? 5000.0f / Q : 200.0f - 2.0f * Q;
    float qs = S / 100.0f, qc = qs * _powf(2.0f, 4.0f * col - 2.0f);
    float B = 8.0f * bs, M = 16.0f * bs;
    int mx = (int)((float)(x) / M), my = (int)((float)(y) / M);
    int ncol = (int)((float)(w) / M) + 1, nrow = (int)((float)(h) / M) + 1;
    float dY = 0.0f, dB = 0.0f, dR = 0.0f, garb = 0.0f;
    int shift = 0;
    uint gs = sd * 5u + 1u;
    for (int e = 0; e < 4; e++) {
        uint fe = (uint)(f) * 4u + (uint)(e);
        if (hash01(fe, sd, 3u) >= rate * 0.55f) continue;
        int er = (int)(hash01(fe, sd, 4u) * (float)(nrow)), ec = (int)(hash01(fe, sd, 5u) * (float)(ncol));
        int span = hash01(fe, sd, 13u) < 0.25f ? nrow : 1 + (int)(hash01(fe, sd, 6u) * (1.0f + 3.0f * str));
        if (my < er || my >= er + span || (my == er && mx < ec)) continue;
        dY += (hash01(fe, sd, 7u) - 0.5f) * 80.0f;
        dB += (hash01(fe, sd, 8u) - 0.5f) * 90.0f;
        dR += (hash01(fe, sd, 9u) - 0.5f) * 90.0f;
        int k = 1 + (int)(hash01(fe, sd, 10u) * 5.0f);
        shift += hash01(fe, sd, 11u) < 0.5f ? k : -k;
        int run = (my - er) * ncol + mx - ec;
        if (run < 1 + (int)(hash01(fe, sd, 12u) * 3.0f)) { garb = 1.0f; gs = fe * 7u + 3u; }
    }
    int sx = mx + shift;
    sx = sx - (int)(_floorf((float)(sx) / (float)(ncol))) * ncol;
    float lx = (float)(x) - (float)(mx) * M, ly = (float)(y) - (float)(my) * M;
    int bx = (int)(lx / B), by = (int)(ly / B);
    int px = (int)((lx - (float)(bx) * B) / bs), py = (int)((ly - (float)(by) * B) / bs);
    float ox = (float)(sx) * M, oy = (float)(my) * M;
    float Y = jpegY(tr, tg, tb, ox + (float)(bx) * B, oy + (float)(by) * B, bs, w, h, px, py, qs, garb, gs) + dY;
    float2 C = jpegC(tr, tg, tb, ox, oy, bs, w, h, (int)(lx / (2.0f * bs)), (int)(ly / (2.0f * bs)), qc, garb, gs);
    float cb = C.x + dB, cr = C.y + dR;
    return make_float3(_saturatef((Y + 1.402f * cr) / 255.0f), _saturatef((Y - 0.344136f * cb - 0.714136f * cr) / 255.0f),
                       _saturatef((Y + 1.772f * cb) / 255.0f));
}

// ---- 1 Digital Damage ------------------------------------------------------------------------------------------
__DEVICE__ float3 scDigital(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h, float sc,
                            float str, float size, float rate, float col, int f, uint sd)
{
    float3 c = rgbAt(tr, tg, tb, x, y, w, h);
    if (rate <= 0.0f) return c;
    float M = 16.0f * sc * _powf(2.0f, (size - 0.5f) * 2.0f);
    int mx = (int)((float)(x) / M), my = (int)((float)(y) / M);
    int ncol = (int)((float)(w) / M) + 1, nrow = (int)((float)(h) / M) + 1;
    int G = 24 + (int)((1.0f - rate) * 72.0f);
    int slots = 1 + (int)(rate * 2.99f);
    for (int k = 0; k < 3; k++) {
        if (k >= slots) break;
        int ph = (int)(hash01((uint)(k) + 1u, sd, 11u) * (float)(G));
        int fp = f + ph;
        int gi = fp / G, t = fp - gi * G;
        uint gk = (uint)(gi) * 3u + (uint)(k) + 17u;
        int ts = (int)(hash01(gk, sd, 12u) * 0.45f * (float)(G));
        if (t < ts) continue;
        float age = (float)(t - ts);
        int m0 = (int)(hash01(gk, sd, 13u) * (float)(ncol * nrow));
        float len = (float)(ncol) * (0.25f + 3.0f * str) * (0.3f + 0.7f * hash01(gk, sd, 14u)) * (1.0f + age * (0.05f + 0.1f * str));
        int m = my * ncol + mx;
        if (m < m0 || (float)(m - m0) >= len) continue;
        int r0 = m0 / ncol, c0 = m0 - r0 * ncol;
        int gl = 2 + (int)(hash01(gk, sd, 21u) * 12.0f);
        int run = m - m0;
        int gid = run / gl;
        uint gu = (uint)(gid) + 1u;
        float hm = hash01(gu, gk, 15u);
        float drift = (hash01(gk, sd, 16u) - 0.5f) * 2.0f * age * sc * 1.5f;
        float dc = (hash01((uint)(m) + 1u, gk, 17u) - 0.5f) * 0.08f;
        float cell = 4.0f * sc;
        float fx = (_floorf((float)(x) / cell) + 0.5f) * cell - 0.5f, fy = (_floorf((float)(y) / cell) + 0.5f) * cell - 0.5f;
        float3 o;
        if (hm < 0.55f) {
            int rg = mx >= c0 ? r0 : r0 + 1;
            float ys = _fmaxf((float)(rg) * M - 1.0f, 0.0f);
            o = bilL(tr, tg, tb, fx + drift, ys, w, h);
            float st = (rnd3((int)(fx / cell), rg, gk) - 0.5f) * 0.05f;
            o = make_float3(o.x + st, o.y + st, o.z + st);
        } else {
            float mvx = (hash01(gu, gk, 18u) - 0.5f) * 2.0f * M * (1.0f + 0.3f * age);
            float mvy = (hash01(gu, gk, 19u) - 0.5f) * 1.2f * M * (1.0f + 0.15f * age);
            o = bilL(tr, tg, tb, fx + mvx, fy + mvy, w, h);
            if (hm > 1.0f - 0.35f * col) {
                float Yv = 0.299f * o.x + 0.587f * o.y + 0.114f * o.z;
                float zero = hash01(gu, gk, 20u) < 0.3f ? 0.0f : 1.0f;
                Yv *= zero;
                o = make_float3(Yv - 0.701f, Yv + 0.529f, Yv - 0.886f);
            }
        }
        return make_float3(_saturatef(o.x + dc), _saturatef(o.y + dc), _saturatef(o.z + dc));
    }
    return c;
}

// ---- 2 TV Damage -----------------------------------------------------------------------------------------------
__DEVICE__ float3 scTV(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h, float sc,
                       float str, float size, float rate, float col, int f, uint sd)
{
    float Wf = (float)(w), Hf = (float)(h), ft = (float)(f);
    float s = _saturatef(str * (0.35f + 1.2f * fbm(ft * 0.035f, 3.7f, 0.0f, 2, sd + 1u)));
    int sp = f / 60, ts = f - sp * 60;
    float Ht = Hf * 1.08f, voff = 0.0f;
    if (hash01((uint)(sp) + 1u, sd, 21u) < rate * 0.7f) {
        float st = hash01((uint)(sp) + 1u, sd, 22u) * 20.0f, dur = 10.0f + 26.0f * hash01((uint)(sp) + 1u, sd, 23u);
        float nr = 1.0f + _floorf(hash01((uint)(sp) + 1u, sd, 24u) * 1.99f);
        voff = sstep(0.0f, dur, (float)(ts) - st) * nr * Ht;
    }
    float yr = _fmod((float)(y) + Ht - voff + Ht * 4.0f, Ht);
    float n = (rnd3(x, y, (uint)(f) * 3u + sd) - 0.5f) * (0.06f + 0.6f * s * s);
    if (yr >= Hf) {
        float rel = (yr - Hf) / (Ht - Hf);
        float dash = rel > 0.55f && rel < 0.62f && rnd3((int)((float)(x) / (7.0f * sc)), (int)(rel * 40.0f), 31u) < 0.5f ? 0.55f : 0.0f;
        float v = 0.02f + dash + 0.5f * n;
        return make_float3(v, v, v);
    }
    int sq = f / 45, tq = f - sq * 45;
    float hold = 0.0f;
    if (hash01((uint)(sq) + 1u, sd, 25u) < rate * 0.5f) {
        float amp = (hash01((uint)(sq) + 1u, sd, 26u) - 0.5f) * 6.0f;
        hold = amp * sstep(0.0f, 8.0f, (float)(tq)) * sstep(45.0f, 30.0f, (float)(tq));
    }
    float Lt = Wf * 1.18f;
    float line = (rnd3((int)(yr), f, sd + 2u) - 0.5f) * 2.0f * s * 2.5f * sc;
    float flag = (fbm(ft * 0.3f, 1.1f, 0.0f, 2, sd + 3u) - 0.5f) * 0.08f * Wf * _expf(-yr / (0.04f * Hf)) * (0.3f + s);
    float xr = _fmod((float)(x) + hold * Lt * (yr / Hf) + line + flag + Lt * 8.0f, Lt);
    if (xr >= Wf) {
        float v = 0.015f + 0.4f * n;
        return make_float3(v, v, v);
    }
    float bw = (0.6f + 2.2f * s) * sc;
    float3 a = bilL(tr, tg, tb, xr - bw, yr, w, h), b = bilL(tr, tg, tb, xr, yr, w, h), d = bilL(tr, tg, tb, xr + bw, yr, w, h);
    float gd = (0.008f + 0.05f * size) * Wf;
    float3 g = bilL(tr, tg, tb, xr - gd, yr, w, h), g2 = bilL(tr, tg, tb, xr - 1.7f * gd, yr, w, h);
    float ga = 0.12f + 0.3f * s, g2a = 0.06f + 0.12f * s;
    float r = (0.25f * a.x + 0.5f * b.x + 0.25f * d.x + ga * g.x - g2a * g2.x) / (1.0f + ga - g2a);
    float gg = (0.25f * a.y + 0.5f * b.y + 0.25f * d.y + ga * g.y - g2a * g2.y) / (1.0f + ga - g2a);
    float bb = (0.25f * a.z + 0.5f * b.z + 0.25f * d.z + ga * g.z - g2a * g2.z) / (1.0f + ga - g2a);
    float Y = luma(r, gg, bb), U = bb - Y, V = r - Y;
    float phi = col * 1.6f * (fbm(ft * 0.02f, 9.1f, 0.0f, 2, sd + 5u) - 0.5f);
    float cp = _cosf(phi), sn = _sinf(phi);
    float kill = 1.0f - (0.4f + 0.6f * col) * sstep(0.45f, 0.75f, s + 0.2f * (hash01((uint)(f) + 1u, sd, 27u) - 0.5f));
    float U2 = (U * cp - V * sn) * kill, V2 = (U * sn + V * cp) * kill;
    float Y2 = 0.42f + (Y - 0.42f) * (1.0f - 0.5f * s);
    float ncx = (float)(x) / (2.2f * sc);
    int nc = (int)(ncx);
    float nt = ncx - (float)(nc);
    float sn2 = (lerp1(rnd3(nc, y, (uint)(f) * 5u + sd), rnd3(nc + 1, y, (uint)(f) * 5u + sd), nt) - 0.5f) * (0.08f + 0.9f * s * s);
    float conf = s * s * col * (1.0f - kill * 0.5f);
    int qx = (int)((float)(x) / (4.0f * sc)), qy = (int)((float)(y) / (2.0f * sc));
    float cu = (rnd3(qx, qy, (uint)(f) * 7u + sd) - 0.5f) * 0.5f * conf, cv = (rnd3(qx, qy, (uint)(f) * 7u + sd + 1u) - 0.5f) * 0.5f * conf;
    float hum = 1.0f - 0.16f * str * (0.5f + 0.5f * _sinf(6.2831853f * (yr / Hf + ft * 0.011f)));
    float Yo = (Y2 + sn2 + 0.4f * n) * hum;
    float R = Yo + V2 + cv, Bc = Yo + U2 + cu;
    float Gc = (Yo - 0.2126f * R - 0.0722f * Bc) / 0.7152f;
    return make_float3(_saturatef(R), _saturatef(Gc), _saturatef(Bc));
}

// ---- 3 Night Vision --------------------------------------------------------------------------------------------
__DEVICE__ float nvIn(float3 c)
{
    return 0.45f * toLin(_saturatef(c.x)) + 0.47f * toLin(_saturatef(c.y)) + 0.08f * toLin(_saturatef(c.z));
}

__DEVICE__ float3 scNight(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h, float sc,
                          float str, float size, float rate, float col, float shape, int f, uint sd)
{
    float fx = (float)(x), fy = (float)(y), Wf = (float)(w), Hf = (float)(h);
    float gain = _powf(2.0f, 1.0f + 5.0f * str) * (1.0f + 0.04f * (hash01((uint)(f) + 1u, sd, 41u) - 0.5f));
    float r1 = 0.9f * sc;
    float L = 0.4f * nvIn(bilL(tr, tg, tb, fx, fy, w, h));
    L += 0.15f * (nvIn(bilL(tr, tg, tb, fx - r1, fy, w, h)) + nvIn(bilL(tr, tg, tb, fx + r1, fy, w, h)) +
                  nvIn(bilL(tr, tg, tb, fx, fy - r1, w, h)) + nvIn(bilL(tr, tg, tb, fx, fy + r1, w, h)));
    float R = (6.0f + 30.0f * size) * sc, halo = 0.0f;
    for (int i = 0; i < 16; i++) {
        float an = 6.2831853f * ((float)(i) + 0.5f) / 16.0f;
        float rr = (i & 1) == 0 ? R : 0.55f * R;
        float e = gain * nvIn(bilL(tr, tg, tb, fx + rr * _cosf(an), fy + rr * _sinf(an), w, h));
        halo += sstep(1.5f, 6.0f, e);
    }
    halo /= 16.0f;
    float e0 = gain * L;
    float v = toDisp(1.0f - _expf(-e0) + 0.45f * halo * (1.0f - 0.5f * sstep(1.0f, 4.0f, e0)));
    uint fz = (uint)(f) * 11u + sd;
    float cellf = 1.3f * sc;
    int qx = (int)(fx / cellf), qy = (int)(fy / cellf);
    float nz = rnd3(qx, qy, fz) - 0.5f;
    float spark = rnd3(qx, qy, fz + 1u);
    float dk = 1.0f - _saturatef(v);
    v += rate * (nz * (0.08f + 0.3f * dk) + (spark > 1.0f - 0.006f * dk ? 0.6f * rnd3(qx, qy, fz + 2u) : 0.0f));
    float hs = 5.0f * sc, hx = hs, hy = hs * 1.7320508f;
    float ax = _fmod(fx + 0.5f, hx) - 0.5f * hx, ay = _fmod(fy + 0.5f, hy) - 0.5f * hy;
    float bx = _fmod(fx + 0.5f + 0.5f * hx, hx) - 0.5f * hx, by = _fmod(fy + 0.5f + 0.5f * hy, hy) - 0.5f * hy;
    float hd = _fminf(_sqrtf(ax * ax + ay * ay), _sqrtf(bx * bx + by * by));
    float wall = 1.0f - 0.06f * sstep(0.36f * hs, 0.5f * hs, hd);
    float blem = 1.0f;
    for (int i = 0; i < 7; i++) {
        float bpx = hash01((uint)(i) + 1u, sd, 42u) * Wf, bpy = hash01((uint)(i) + 1u, sd, 43u) * Hf;
        float br = (1.5f + 4.0f * hash01((uint)(i) + 1u, sd, 44u)) * sc;
        float dd = _sqrtf((fx - bpx) * (fx - bpx) + (fy - bpy) * (fy - bpy));
        blem *= 1.0f - 0.75f * sstep(br + 1.0f, br - 1.0f, dd);
    }
    v = _fmaxf(v, 0.0f) * wall * blem;
    float u = fx + 0.5f - 0.5f * Wf, q = fy + 0.5f - 0.5f * Hf, mask;
    int shp = (int)(shape + 0.5f);
    if (shp == 0) {
        float rr = _sqrtf(u * u + q * q) / (0.5f * _sqrtf(Wf * Wf + Hf * Hf));
        mask = 1.0f - 0.55f * rr * rr * rr;
    } else {
        float Rc = (shp == 1 ? 0.47f : 0.44f) * Hf, off = shp == 1 ? 0.0f : 0.29f * Hf, edge = 0.012f * Hf;
        float d1 = _sqrtf((u - off) * (u - off) + q * q), d2 = _sqrtf((u + off) * (u + off) + q * q);
        float dm = _fminf(d1, d2);
        mask = sstep(Rc + edge, Rc - edge, dm) * (1.0f - 0.4f * _powf(_saturatef(dm / Rc), 4.0f));
    }
    v *= mask;
    float vl = toLin(_saturatef(v) * 0.97f);
    float tr0 = lerp1(0.07f, 0.80f, col), tg0 = lerp1(1.0f, 0.90f, col), tb0 = lerp1(0.05f, 1.0f, col);
    float wh = 0.45f * _saturatef(v) * _saturatef(v) * _saturatef(v);
    return make_float3(toDisp(vl * lerp1(tr0, 1.0f, wh)), toDisp(vl * lerp1(tg0, 1.0f, wh)), toDisp(vl * lerp1(tb0, 1.0f, wh)));
}

// ---- 4 X-Ray ---------------------------------------------------------------------------------------------------
__DEVICE__ float xIn(float3 c)
{
    return 0.2126f * _saturatef(c.x) + 0.7152f * _saturatef(c.y) + 0.0722f * _saturatef(c.z);
}

__DEVICE__ float3 scXray(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h, float sc,
                         float str, float size, float rate, float col, float shape, int f, uint sd)
{
    float fx = (float)(x), fy = (float)(y);
    float L = xIn(bilL(tr, tg, tb, fx, fy, w, h));
    float ra = (1.5f + 7.0f * size) * sc, Lb = 0.0f, Lw = 0.0f;
    for (int i = 0; i < 12; i++) {
        float an = 6.2831853f * ((float)(i) + 0.25f) / 12.0f;
        float rr = (i & 1) == 0 ? ra : 2.4f * ra;
        float wt = (i & 1) == 0 ? 1.0f : 0.6f;
        Lb += wt * xIn(bilL(tr, tg, tb, fx + rr * _cosf(an), fy + rr * _sinf(an), w, h));
        Lw += wt;
    }
    Lb = (Lb + L) / (Lw + 1.0f);
    int pos = shape > 0.5f ? 1 : 0;
    float d = pos == 1 ? L : 1.0f - L, db = pos == 1 ? Lb : 1.0f - Lb;
    d = d + (0.3f + 1.0f * str) * (d - db);
    float t = _saturatef(0.5f + (d - 0.5f) * (0.75f + 0.8f * str));
    t = lerp1(t, t * t * (3.0f - 2.0f * t), 0.35f);
    float z = rate > 0.0f ? _floorf((float)(f) * (0.25f + 0.75f * rate)) : 0.0f;
    float mot = vnoise3(fx / (2.2f * sc) + 4096.0f, fy / (2.2f * sc) + 4096.0f, z + 4096.0f, sd + 51u) - 0.5f;
    t = _saturatef(t + mot * 0.07f * (0.3f + t));
    float glow = sstep(0.55f, 1.0f, db) * 0.22f;
    float tl = toLin(t) + glow * toLin(t + 0.2f) * 0.5f;
    float br = lerp1(0.93f, 0.55f, col), bg = lerp1(0.96f, 0.80f, col);
    return make_float3(toDisp(0.0015f + tl * br), toDisp(0.0022f + tl * bg), toDisp(0.0045f + tl));
}

// ---- 5 LED Sign ------------------------------------------------------------------------------------------------
__DEVICE__ float3 ledCell(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, float cx, float cy, float P, int w, int h,
                          int i, int j, float lv, float col, uint sd)
{
    float q = 0.25f * P;
    float3 a = bilL(tr, tg, tb, cx - q, cy - q, w, h), b = bilL(tr, tg, tb, cx + q, cy - q, w, h);
    float3 c = bilL(tr, tg, tb, cx - q, cy + q, w, h), d = bilL(tr, tg, tb, cx + q, cy + q, w, h);
    float r = 0.25f * (_saturatef(a.x) + _saturatef(b.x) + _saturatef(c.x) + _saturatef(d.x));
    float g = 0.25f * (_saturatef(a.y) + _saturatef(b.y) + _saturatef(c.y) + _saturatef(d.y));
    float bl = 0.25f * (_saturatef(a.z) + _saturatef(b.z) + _saturatef(c.z) + _saturatef(d.z));
    float Y = luma(r, g, bl);
    r = _saturatef(Y + (r - Y) * col * 2.0f); g = _saturatef(Y + (g - Y) * col * 2.0f); bl = _saturatef(Y + (bl - Y) * col * 2.0f);
    float t = bayer8(i, j) - 0.5f;
    r = softRound(r * lv + t, 8.0f) / lv; g = softRound(g * lv + t, 8.0f) / lv; bl = softRound(bl * lv + t, 8.0f) / lv;
    float dead = hash01((uint)(i + 70000), (uint)(j + 70000), sd + 61u) < 0.0015f ? 0.0f : 1.0f;
    return make_float3(toLin(_saturatef(r)) * dead, toLin(_saturatef(g)) * dead, toLin(_saturatef(bl)) * dead);
}

__DEVICE__ float3 scLed(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h, float sc,
                        float str, float size, float rate, float col, float dith, float shape, int f, uint sd)
{
    float Wf = (float)(w), Hf = (float)(h), fx = (float)(x), fy = (float)(y);
    float P = (6.0f + 34.0f * size) * sc;
    float u = (fx + 0.5f - 0.5f * Wf) / P, v = (fy + 0.5f - 0.5f * Hf) / P;
    int ci = (int)(_floorf(u)), cj = (int)(_floorf(v));
    float lv = lerp1(48.0f, 3.0f, dith);
    int shp = (int)(shape + 0.5f);
    float band = 1.0f;
    if (rate > 0.0f) {
        float ph = 0.5f + 0.5f * _cosf(6.2831853f * (fy / Hf * 2.5f - (float)(f) * 0.06f * rate));
        band = 1.0f - 0.55f * rate * ph * ph * ph * ph;
    }
    float lr = 0.0008f, lg = 0.0008f, lb = 0.0008f;
    float gr = 0.0f, gg = 0.0f, gb = 0.0f;
    float gw = 0.28f * P, gk = 0.3f * str;
    for (int dj = -1; dj <= 1; dj++) {
        for (int di = -1; di <= 1; di++) {
            int i = ci + di, j = cj + dj;
            float cxp = ((float)(i) + 0.5f) * P + 0.5f * Wf - 0.5f, cyp = ((float)(j) + 0.5f) * P + 0.5f * Hf - 0.5f;
            float3 e = ledCell(tr, tg, tb, cxp, cyp, P, w, h, i, j, lv, col, sd);
            for (int k = 0; k < 3; k++) {
                if (shp != 1 && k > 0) break;
                float ox = 0.0f, oy = 0.0f, rad = 0.36f * P;
                float er = e.x, eg = e.y, eb = e.z;
                if (shp == 2) {
                    float Ye = 0.2126f * er + 0.7152f * eg + 0.0722f * eb;
                    er = Ye * 1.0f; eg = Ye * 0.36f; eb = Ye * 0.025f;
                }
                if (shp == 1) {
                    rad = 0.19f * P;
                    ox = k == 0 ? 0.0f : (k == 1 ? -0.21f * P : 0.21f * P);
                    oy = k == 0 ? -0.2f * P : 0.14f * P;
                    float lum = k == 0 ? er : (k == 1 ? eg : eb);
                    er = k == 0 ? lum * 1.0f : (k == 1 ? lum * 0.06f : lum * 0.03f);
                    eg = k == 0 ? lum * 0.05f : (k == 1 ? lum * 1.0f : lum * 0.22f);
                    eb = k == 0 ? lum * 0.01f : (k == 1 ? lum * 0.28f : lum * 1.0f);
                    float lift = 2.4f;
                    er *= lift; eg *= lift; eb *= lift;
                }
                float dx = fx - (cxp + ox), dy = fy - (cyp + oy);
                float dd = _sqrtf(dx * dx + dy * dy);
                float cov = sstep(rad + 0.75f, rad - 0.75f, dd);
                float dome = 1.15f - 0.4f * (dd / rad) * (dd / rad);
                float shine = 0.006f * sstep(0.3f * rad, 0.05f * rad, _sqrtf((dx + 0.3f * rad) * (dx + 0.3f * rad) + (dy + 0.35f * rad) * (dy + 0.35f * rad)));
                lr = lerp1(lr, 0.0025f + er * dome * band + shine, cov);
                lg = lerp1(lg, 0.0025f + eg * dome * band + shine, cov);
                lb = lerp1(lb, 0.0025f + eb * dome * band + shine, cov);
                float gl = gk * _expf(-(dd / gw) * (dd / gw)) * sstep(1.4f * P, 1.0f * P, dd) * band;
                gr += gl * er; gg += gl * eg; gb += gl * eb;
            }
        }
    }
    return lightOut(lr + gr, lg + gg, lb + gb, 1.0f);
}

// ---- 6 Misalignment --------------------------------------------------------------------------------------------
__DEVICE__ float3 scMisalign(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h, float sc,
                             float str, float size, float rate, float col, int f, uint sd)
{
    float fx = (float)(x), fy = (float)(y), Wf = (float)(w), Hf = (float)(h), ft = (float)(f);
    float u = (fx + 0.5f - 0.5f * Wf) / Hf, v = (fy + 0.5f - 0.5f * Hf) / Hf, r2 = u * u + v * v;
    float wob = 1.0f + rate * (0.18f * _sinf(ft * 0.21f) + 0.08f * _sinf(ft * 0.83f + 1.0f) + 0.05f * (hash01((uint)(f) + 1u, sd, 71u) - 0.5f));
    float A = str * sc * wob;
    float a1 = 6.2831853f * hash01(1u, sd, 72u), a2 = a1 + 2.4f + 1.2f * hash01(2u, sd, 72u);
    float sr = 4.0f * A, dr = 26.0f * A;
    float ka = 0.7f + 0.6f * hash01(3u, sd, 72u), kb = -(0.7f + 0.6f * hash01(4u, sd, 72u));
    float tw = 0.5f * (hash01(5u, sd, 72u) - 0.5f);
    float rx = sr * _cosf(a1) + dr * (ka * u * r2 * 2.0f - tw * v), ry = sr * _sinf(a1) + dr * (ka * v * r2 * 2.0f + tw * u);
    float bx = sr * _cosf(a2) + dr * (kb * u * r2 * 2.0f + tw * v), by = sr * _sinf(a2) + dr * (kb * v * r2 * 2.0f - tw * u);
    float gx = 0.25f * dr * u * r2, gy = 0.25f * dr * v * r2;
    float fr = (0.4f + 1.6f * size) * sc, fb = (0.8f + 3.0f * size) * sc;
    float R = 0.0f, G = 0.0f, B = 0.0f;
    for (int i = 0; i < 5; i++) {
        float ox = i == 1 ? 1.0f : (i == 2 ? -1.0f : 0.0f), oy = i == 3 ? 1.0f : (i == 4 ? -1.0f : 0.0f);
        float wt = i == 0 ? 0.4f : 0.15f;
        R += wt * toLin(_saturatef(bilL(tr, tg, tb, fx + rx + ox * fr, fy + ry + oy * fr, w, h).x));
        G += wt * toLin(_saturatef(bilL(tr, tg, tb, fx + gx + ox * 0.3f * sc, fy + gy + oy * 0.3f * sc, w, h).y));
        B += wt * toLin(_saturatef(bilL(tr, tg, tb, fx + bx + ox * fb, fy + by + oy * fb, w, h).z));
    }
    float p1 = col * sstep(0.52f, 0.78f, fbm(u * 1.4f + 3.0f, v * 1.4f + 3.0f, 0.0f, 3, sd + 73u)) * (0.3f + 2.2f * r2);
    float p2 = col * sstep(0.52f, 0.78f, fbm(u * 1.4f + 9.0f, v * 1.4f + 1.0f, 0.0f, 3, sd + 74u)) * (0.3f + 2.2f * r2);
    p1 = _saturatef(p1) * 0.5f; p2 = _saturatef(p2) * 0.5f;
    float R2 = R * (1.0f - p1) + B * p2, G2 = G + R * p1 * 0.8f, B2 = B * (1.0f - p2) + G * p2 * 0.3f;
    return make_float3(toDisp(R2), toDisp(G2), toDisp(B2));
}

// ---- 7 Video Glitch --------------------------------------------------------------------------------------------
__DEVICE__ float3 scVGlitch(__TEXTURE__ tr, __TEXTURE__ tg, __TEXTURE__ tb, int x, int y, int w, int h, float sc,
                            float str, float size, float rate, float col, int f, uint sd)
{
    float Wf = (float)(w), Hf = (float)(h), fx = (float)(x), fy = (float)(y);
    float e = 0.0f;
    for (int k = 0; k < 2; k++) {
        int fk = f + k * 7;
        int win = fk / 16, tw = fk - win * 16;
        uint wk = (uint)(win) * 2u + (uint)(k) + 1u;
        if (hash01(wk, sd, 81u) >= 0.1f + 0.85f * rate) continue;
        int st = (int)(hash01(wk, sd, 82u) * 8.0f), ln = 2 + (int)(hash01(wk, sd, 83u) * 9.0f);
        if (tw >= st && tw < st + ln) e = _fmaxf(e, 0.5f + 0.5f * hash01((uint)(f) + 1u, sd, 84u + (uint)(k)));
    }
    e *= str;
    uint fz = (uint)(f) * 13u + sd;
    float sx = fx, sy = fy;
    float swap = 0.0f, rgbyuv = 0.0f, dark = 1.0f;
    if (e > 0.0f) {
        float bh = (3.0f + 60.0f * size) * sc;
        int band = (int)(fy / bh);
        float bt = (float)(band) * bh;
        float hb = rnd3(band, f, sd + 85u);
        if (hb < 0.55f * e) {
            float kind = rnd3(band, f, sd + 86u);
            if (kind < 0.3f) {
                sy = _fmaxf(bt - 1.0f, 0.0f);
            } else if (kind < 0.7f) {
                float dx = (rnd3(band, f, sd + 87u) - 0.5f) * 2.0f * Wf * (0.05f + 0.35f * e);
                float xs = _fmod(fx - dx + Wf * 4.0f, Wf);
                float seam = _fmod(dx + Wf * 4.0f, Wf);
                dark = 1.0f - 0.9f * sstep(4.0f * sc, 1.0f * sc, _fabs(fx - seam));
                sx = xs;
            } else {
                int odd = y & 1;
                sx = fx + (odd == 1 ? (rnd3(band, f, sd + 88u) - 0.5f) * 40.0f * sc * (0.3f + e) : 0.0f);
            }
            float cs = rnd3(band, f, sd + 89u);
            if (cs < 0.5f * col) swap = 1.0f;
            else if (cs < 0.75f * col) rgbyuv = 1.0f;
        }
    }
    float3 c = bilL(tr, tg, tb, sx, sy, w, h);
    float r = _saturatef(c.x), g = _saturatef(c.y), b = _saturatef(c.z);
    if (swap > 0.0f) {
        float Y = 0.299f * r + 0.587f * g + 0.114f * b, U = 0.564f * (b - Y), V = 0.713f * (r - Y);
        r = Y + 1.402f * U; g = Y - 0.344f * V - 0.714f * U; b = Y + 1.772f * V;
    }
    if (rgbyuv > 0.0f) {
        float Y = 0.299f * r + 0.587f * g + 0.114f * b, U = 0.564f * (b - Y) + 0.5f, V = 0.713f * (r - Y) + 0.5f;
        r = V; g = Y; b = U;
    }
    r *= dark; g *= dark; b *= dark;
    float dens = str * 0.0006f + e * 0.006f;
    for (int k = 0; k < 4; k++) {
        float hs = rnd3(x - k, y, fz);
        if (hs < dens && (float)(k) < 1.0f + rnd3(x - k, y, fz + 1u) * 4.0f) {
            float kc = rnd3(x - k, y, fz + 2u);
            r = kc < 0.4f ? 1.0f : (kc < 0.6f ? 0.0f : rnd3(x - k, y, fz + 3u));
            g = kc < 0.4f ? 1.0f : (kc < 0.6f ? 0.0f : rnd3(x - k, y, fz + 4u));
            b = kc < 0.4f ? 1.0f : (kc < 0.6f ? 0.0f : rnd3(x - k, y, fz + 5u));
            break;
        }
    }
    return make_float3(_saturatef(r), _saturatef(g), _saturatef(b));
}
