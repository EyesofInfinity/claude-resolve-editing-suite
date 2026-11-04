// Develop Beat's envelope engine: the music data a song was baked into (btdata.h, or the grid of a BPM when
// no song is baked) turned into one value 0 to 1 per frame for any slider. A DCTL cannot read audio, so beat.py
// writes the song's events into constant tables: each beat, hit and low hit as one float (its time in hundredths
// of a second times 128, plus 7 bits: its tier, its place in the bar or a downbeat flag, its strength), and the
// bass, mid and high energies 8 times a second as one float (three bytes). Times are in seconds, so a song baked
// once plays at any timeline rate. Every name here starts with bt so the engine can be written into any Develop
// effect (effects/beat/drive.py). MIT License.

#include "btdata.h"

__DEVICE__ float btSmooth(float a, float b, float x) { float t = _saturatef((x - a) / (b - a)); return t * t * (3.0f - 2.0f * t); }

__DEVICE__ float btRaw(int s, int i)
{
    if (s == 0) return BT_BEAT[i];
    if (s == 1) return BT_HIT[i];
    return BT_KICK[i];
}

__DEVICE__ float btFe(float v, float fps) { return _floorf(_floorf(v / 128.0f) * fps / 100.0f + 0.5f); }

__DEVICE__ int btLast(int s, int n, float tf, float fps)
{
    int lo = 0, hi = n - 1, r = -1;
    while (lo <= hi) {
        int m = (lo + hi) >> 1;
        if (btFe(btRaw(s, m), fps) <= tf) { r = m; lo = m + 1; } else { hi = m - 1; }
    }
    return r;
}

__DEVICE__ float btPass(int s, float v, int src, float minTier, float accent)
{
    float pay = v - 128.0f * _floorf(v / 128.0f);
    float tier = pay - 4.0f * _floorf(pay / 4.0f);
    if (tier < minTier - 0.5f) return 0.0f;
    if (s == 0) {
        float bar = _floorf(pay / 4.0f) - 8.0f * _floorf(pay / 32.0f);
        float bs = _floorf(pay / 32.0f);
        if (src == 1 && bar > 0.5f) return 0.0f;
        return (bar < 0.5f ? 1.0f : 1.0f - accent) * (0.8f + 0.2f * bs / 3.0f);
    }
    float down = _floorf(pay / 4.0f) - 2.0f * _floorf(pay / 8.0f);
    float hs = _floorf(pay / 8.0f);
    return (down > 0.5f ? 1.0f : 1.0f - accent) * (0.35f + 0.65f * hs / 15.0f);
}

__DEVICE__ float btAfter(float dt, float s, int shape, float rel)
{
    if (shape == 0) return s * _expf(-2.302585f * dt / rel);
    if (shape == 1) return s * (1.0f - btSmooth(0.0f, rel, dt));
    return s * _expf(-2.302585f * dt / 1.5f);
}

__DEVICE__ float btBefore(float d, float s, int shape, float atk, float rel)
{
    float len = shape == 2 ? rel : atk;
    if (len <= 0.0f || d >= len) return 0.0f;
    float u = 1.0f - d / len;
    return s * u * u;
}

__DEVICE__ float btFinish(float duck, float near, int shape, float fps)
{
    if (shape != 1) return duck;
    return (1.0f - duck) * (1.0f - btSmooth(2.0f * fps, 4.0f * fps, near));
}

__DEVICE__ float btEventEnv(int src, float tf, float fps, int shape, float atk, float rel, float accent, float minTier)
{
    int s = src < 2 ? 0 : src - 1;
    int n = (int)(BT_META[s]);
    if (n <= 0) return 0.0f;
    int i = btLast(s, n, tf, fps);
    float e = 0.0f, near = 1e9f;
    int found = 0;
    for (int j = i; j >= 0 && j > i - 32 && found < 3; j--) {
        float v = btRaw(s, j);
        float st = btPass(s, v, src, minTier, accent);
        if (st > 0.001f) {
            float dt = tf - btFe(v, fps);
            if (found == 0) near = dt;
            e = _fmaxf(e, btAfter(dt, st, shape, rel));
            found = found + 1;
        }
    }
    for (int j = i + 1; j < n && j < i + 33; j++) {
        float v = btRaw(s, j);
        float st = btPass(s, v, src, minTier, accent);
        if (st > 0.001f) {
            float d = btFe(v, fps) - tf;
            near = _fminf(near, d);
            e = _fmaxf(e, btBefore(d, st, shape, atk, rel));
            break;
        }
    }
    return btFinish(e, near, shape, fps);
}

__DEVICE__ float btGridEnv(int src, float tf, float fps, float bpm, float meter, int shape, float atk, float rel, float accent, float minTier)
{
    float spb = 60.0f / bpm;
    float pf = fps * spb;
    float gap = minTier > 2.5f ? 0.5f : (minTier > 1.5f ? 0.36f : (minTier > 0.5f ? 0.25f : 0.125f));
    float stride = src == 1 ? meter : 1.0f;
    for (int k = 0; k < 6 && stride * spb < gap - 0.0001f; k++) stride = stride * 2.0f;
    float kb = _floorf(tf / (pf * stride));
    if (_floorf(kb * stride * pf + 0.5f) > tf) kb = kb - 1.0f;
    if (_floorf((kb + 1.0f) * stride * pf + 0.5f) <= tf) kb = kb + 1.0f;
    float e = 0.0f, near = 1e9f;
    for (int k = 0; k < 3; k++) {
        float nb = (kb - k) * stride;
        if (nb < 0.0f) break;
        float fe = _floorf(nb * pf + 0.5f);
        float bar = nb - meter * _floorf(nb / meter);
        float st = bar < 0.5f ? 1.0f : 1.0f - accent;
        if (k == 0) near = tf - fe;
        if (st > 0.001f) e = _fmaxf(e, btAfter(tf - fe, st, shape, rel));
    }
    float nn = (kb + 1.0f) * stride;
    if (nn >= 0.0f) {
        float fe = _floorf(nn * pf + 0.5f);
        float bar = nn - meter * _floorf(nn / meter);
        float st = bar < 0.5f ? 1.0f : 1.0f - accent;
        near = _fminf(near, fe - tf);
        if (st > 0.001f) e = _fmaxf(e, btBefore(fe - tf, st, shape, atk, rel));
    }
    return btFinish(e, near, shape, fps);
}

__DEVICE__ float btBand(float v, int band)
{
    float lo = _floorf(v / 65536.0f);
    float mi = _floorf(v / 256.0f) - 256.0f * lo;
    float hi = v - 65536.0f * lo - 256.0f * mi;
    return (band == 0 ? lo : (band == 1 ? mi : hi)) / 255.0f;
}

__DEVICE__ float btCurve(int band, float tsec)
{
    int n = (int)(BT_META[3]);
    if (n <= 0 || tsec < 0.0f) return 0.0f;
    float x = tsec * BT_META[4];
    if (x >= n - 1.0f) return x > n ? 0.0f : btBand(BT_CURVE[n - 1], band);
    int i = (int)(_floorf(x));
    float f = x - _floorf(x);
    return btBand(BT_CURVE[i], band) * (1.0f - f) + btBand(BT_CURVE[i + 1], band) * f;
}

__DEVICE__ float btEnv(float frame, float startS, float nudge, float fps, int src, int shape, float atk, float rel, float accent, float minTier, float bpm, float floorv)
{
    float tf = frame - _floorf(startS * fps + 0.5f) - nudge;
    float rl = _fmaxf(rel, 0.5f);
    float e = 0.0f;
    if (src >= 4) {
        float v = btCurve(src - 4, tf / fps);
        e = _saturatef((v - floorv) / _fmaxf(0.001f, 1.0f - floorv));
        if (shape == 1) e = (tf < 0.0f || tf / fps > BT_META[7]) ? 0.0f : 1.0f - e;
        if (shape == 2) e = e * e;
    } else if (bpm > 0.5f || BT_META[7] <= 0.0f) {
        e = btGridEnv(src, tf, fps, bpm > 0.5f ? bpm : 120.0f, _fmaxf(1.0f, BT_META[6]), shape, atk, rl, accent, minTier);
    } else {
        e = btEventEnv(src, tf, fps, shape, atk, rl, accent, minTier);
    }
    return e < 0.004f ? 0.0f : _saturatef(e);
}

__DEVICE__ float btTier(float rate, int bright)
{
    float t = rate >= 7.99f ? 0.0f : (rate >= 3.99f ? 1.0f : (rate >= 2.77f ? 2.0f : 3.0f));
    return bright == 1 ? _fmaxf(t, 2.0f) : t;
}
