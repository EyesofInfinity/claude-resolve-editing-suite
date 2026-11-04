"""Freeze and stretch: a phase randomised STFT stretch (the published Paulstretch idea, written here from
the idea) and a granular freeze that holds one moment of a sound."""
import numpy as np

from common import as2d, finish, fade

def _frames_out(n_out, H):
    return n_out // H + 4

def stretch(x, sr, factor=8.0, window=0.25, mix=1.0, link=True, release=None, gain_db=0.0, seed=3):
    """Spectral stretch: any sound to an ambient bed, factor times longer (2 to 50, 1 to 100 accepted).

    Each output hop (window / 4) takes a Hann windowed input frame at position (output time / factor),
    keeps its magnitudes, draws fresh uniform phases, and overlap adds the inverse with a Hann window
    again. Hann squared at 75 percent overlap sums to 1.5 and a Hann frame keeps 0.375 of the power, so
    the output gets 1 / sqrt(0.5625) to keep the input's level on noise like material.
    window   seconds (0.05 crisp to 1.0 smooth); longer windows smear more and resolve pitch finer
    release  seconds of fade at the end of the bed (None is a tenth of the output, at most 3 s), so a
             source cut off mid sound still ends as a bed
    link     the same phases on both channels (keeps a centred image centred)
    mix      dry/wet (equal power), 0 returns x exactly; at 1 the output is the stretch alone
    Output is stereo, round(len(x) * factor) samples long; the dry part (mix under 1) is the original
    at its own length, padded.
    """
    if mix == 0:
        return x.copy()
    a = as2d(x).astype(np.float64)
    if a.shape[1] == 1:
        a = np.repeat(a, 2, axis=1)
    a = a[:, :2]
    factor = float(np.clip(factor, 1.0, 100.0))
    W = int(round(window * sr / 2)) * 2
    W = max(W, 256)
    H = W // 4
    n = a.shape[0]
    n_out = int(round(n * factor))
    pad = np.zeros((n + 2 * W, 2))
    pad[W:W + n] = a
    win = np.hanning(W + 1)[:W]
    rng = np.random.default_rng(seed)
    K = _frames_out(n_out, H)
    out = np.zeros((K * H + W, 2))
    g = 1.0 / np.sqrt(0.375 * 1.5)
    for k in range(K):
        t_out = k * H
        c_in = t_out / factor
        s = int(round(c_in)) + W - W // 2
        s = min(max(s, 0), pad.shape[0] - W)
        fr = pad[s:s + W] * win[:, None]
        mag = np.abs(np.fft.rfft(fr, axis=0))
        if link:
            ph = rng.uniform(0, 2 * np.pi, mag.shape[0])[:, None]
        else:
            ph = rng.uniform(0, 2 * np.pi, mag.shape)
        y = np.fft.irfft(mag * np.exp(1j * ph), n=W, axis=0) * win[:, None]
        o = k * H
        out[o:o + W] += y
    w = out[W // 2:W // 2 + n_out] * g * 10 ** (gain_db / 20)
    rel = min(3.0, 0.1 * n_out / sr) if release is None else float(release)
    fade(w, int(0.01 * sr), max(int(0.05 * sr), int(rel * sr)))
    return finish(x, w, mix, sr)

def freeze(x, sr, at=None, hold=12.0, grain=0.12, spread=0.2, density=60.0, attack=0.4, release=1.5,
           mode="granular", mix=1.0, gain_db=0.0, seed=5):
    """Freeze one moment of a sound and hold it.

    at       seconds (None is the loudest 100 ms of the file)
    hold     seconds the frozen texture lasts, starting at `at` on the input's timeline
    mode     granular: Hann grains of `grain` seconds read from [at - spread/2, at + spread/2] at random,
             `density` grains per second at random start times; spread over 50 ms keeps grains incoherent
             above 20 Hz so they add in power. spectral: one STFT frame's magnitudes at `at` with fresh
             random phases every hop (the stretch at factor infinity), the smoothest hold.
    attack, release   fades of the held texture in seconds
    The texture's level equals the input's level around `at` (100 ms RMS), plus gain_db.
    mix      dry/wet (equal power), 0 returns x exactly, 1 is the texture alone
    Output is stereo, max(len(x), at + hold) seconds long.
    """
    if mix == 0:
        return x.copy()
    a = as2d(x).astype(np.float64)
    if a.shape[1] == 1:
        a = np.repeat(a, 2, axis=1)
    a = a[:, :2]
    n = a.shape[0]
    if at is None:
        e = np.convolve(np.sum(a * a, axis=1), np.ones(int(0.1 * sr)), mode="same")
        at = float(np.argmax(e)) / sr
    c = int(np.clip(round(float(at) * sr), 0, max(0, n - 1)))
    rng = np.random.default_rng(seed)
    nh = int(hold * sr)
    tex = np.zeros((nh, 2))
    if mode == "spectral":
        W = int(round(0.25 * sr / 2)) * 2
        H = W // 4
        win = np.hanning(W + 1)[:W]
        s = min(max(c - W // 2, 0), max(0, n - W))
        fr = np.zeros((W, 2))
        seg = a[s:s + W]
        fr[: seg.shape[0]] = seg
        mag = np.abs(np.fft.rfft(fr * win[:, None], axis=0))
        out = np.zeros((nh + 2 * W, 2))
        for k in range(nh // H + 4):
            ph = rng.uniform(0, 2 * np.pi, mag.shape[0])[:, None]
            out[k * H:k * H + W] += np.fft.irfft(mag * np.exp(1j * ph), n=W, axis=0) * win[:, None]
        tex = out[W:W + nh] / np.sqrt(0.375 * 1.5)
    else:
        G = max(64, int(grain * sr))
        env = np.hanning(G + 1)[:G][:, None]
        sp = int(spread * sr)
        per = sr / density
        count = int((nh + G) / per) + 1
        starts = (-G + np.arange(count) * per + rng.uniform(-0.5, 0.5, count) * per).astype(np.int64)
        for st in starts:
            src = c + int(rng.uniform(-sp / 2, sp / 2)) - G // 2
            src = min(max(src, 0), max(0, n - G))
            g = a[src:src + G]
            if g.shape[0] < G:
                g = np.concatenate([g, np.zeros((G - g.shape[0], 2))], axis=0)
            g = g * env
            o0 = max(st, 0)
            o1 = min(st + G, nh)
            if o1 > o0:
                tex[o0:o1] += g[o0 - st:o1 - st]
        tex /= np.sqrt(density * grain * 0.375)
    r0 = max(0, c - int(0.05 * sr))
    ref = np.sqrt(np.mean(a[r0:r0 + int(0.1 * sr)] ** 2) + 1e-30)
    got = np.sqrt(np.mean(tex[int(min(nh, attack * sr)):max(int(min(nh, attack * sr)) + 1,
                                                            nh - int(release * sr))] ** 2) + 1e-30)
    tex *= (ref / got) * 10 ** (gain_db / 20)
    fade(tex, int(attack * sr), int(release * sr))
    wet = np.zeros((max(n, c + nh), 2))
    wet[c:c + nh] = tex
    return finish(x, wet, mix, sr)
