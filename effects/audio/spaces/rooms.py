"""Convolution rooms: a uniformly partitioned FFT convolution engine (overlap save with a frequency domain
delay line) and the room effect over the synthesised impulse responses in irsynth.py."""
import numpy as np
from functools import lru_cache
from scipy.signal import butter, sosfilt

from common import as2d, to_stereo64, finish, match_loudness
import irsynth

def partitioned_convolve(x, h, block=None, chunk=None):
    """Linear convolution of x (n, ci) with a true stereo IR h (m, ci, co), uniformly partitioned.

    Each IR partition of B samples is a 2B point spectrum; input frames of 2B advance by B; output block k
    sums partition p times input frame k - p (the frequency domain delay line); the last B samples of each
    2B inverse transform are kept (overlap save). Output blocks are made `chunk` at a time, each from
    only the input frames it needs, so memory stays bounded on long files. Returns (n + m - 1, co)
    float64.
    """
    x = np.asarray(x, dtype=np.float64)
    h = np.asarray(h, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    if h.ndim == 1:
        h = h[:, None, None]
    n, ci = x.shape
    m, ci2, co = h.shape
    if ci2 != ci:
        raise ValueError("IR inputs must match the signal's channels")
    if block is None:
        block = int(np.clip(1 << int(np.ceil(np.log2(max(1, m / 16)))), 1024, 16384))
    B = int(block)
    P = -(-m // B)
    hp = np.zeros((P * B, ci, co))
    hp[:m] = h
    Hp = np.fft.rfft(hp.reshape(P, B, ci, co), n=2 * B, axis=1)
    nout = n + m - 1
    nb = -(-nout // B)
    xp = np.zeros(((nb + 1) * B, ci))
    xp[B:B + n] = x
    y = np.zeros((nb * B, co))
    if chunk is None:
        chunk = max(16, int(2 ** 25 // ((B + 1) * max(ci, co) * 16)))
    for c0 in range(0, nb, chunk):
        c1 = min(nb, c0 + chunk)
        f0 = max(0, c0 - P + 1)
        idx = np.arange(f0, c1)[:, None] * B + np.arange(2 * B)[None, :]
        X = np.fft.rfft(xp[idx], axis=1)
        Y = np.zeros((c1 - c0, B + 1, co), dtype=np.complex128)
        for p in range(min(P, c1)):
            k0 = max(c0, p)
            if k0 >= c1:
                continue
            Y[k0 - c0:] += np.einsum("kfc,fco->kfo", X[k0 - p - f0:c1 - p - f0], Hp[p], optimize=True)
        y[c0 * B:c1 * B] = np.fft.irfft(Y, n=2 * B, axis=1)[:, B:, :].reshape(-1, co)
    return y[:nout]

@lru_cache(maxsize=16)
def _ir(preset, sr, n_in, decay, seed):
    return irsynth.synth(preset, sr=sr, n_in=n_in, decay=decay, seed=seed)

def ir(preset, sr=48000, n_in=1, decay=1.0, seed=1):
    return _ir(preset, int(sr), int(n_in), float(decay), int(seed))

def room(x, sr, preset="cathedral", mix=0.3, predelay=0.0, decay=1.0, low_cut=0.0, high_cut=0.0,
         width=1.0, gain_db=0.0, seed=1):
    """Convolution room over a synthesised impulse response.

    preset   cathedral, night_forest, cave, small_room, plate, spring
    mix      dry/wet (equal power), 0 returns x exactly, 1 is the wet alone (wet loudness matched to the input)
    predelay seconds added before the IR (the rooms already carry their own gap to the first reflection)
    decay    scales every band's RT60 (0.5 to 2)
    low_cut, high_cut   optional wet filters in Hz (0 is off)
    Mono in gives a centre source; stereo in gives two sources (true stereo, four paths).
    Output is stereo, longer than x by the IR length (1.15 x the longest band RT60, scaled by decay):
    cathedral 10.0 s, cave 14.5 s, night forest 2.3 s, small room 1.1 s, plate 3.3 s, spring 3.1 s.
    """
    if mix == 0:
        return x.copy()
    a = as2d(x).astype(np.float64)
    n_in = 1 if a.shape[1] == 1 else 2
    h = ir(preset, sr, n_in, decay, seed)
    k = int(round(max(0.0, predelay) * sr))
    if k:
        h = np.concatenate([np.zeros((k,) + h.shape[1:]), h], axis=0)
    w = partitioned_convolve(a[:, :n_in], h)
    if low_cut and low_cut > 0:
        w = sosfilt(butter(2, low_cut, "highpass", fs=sr, output="sos"), w, axis=0)
    if high_cut and 0 < high_cut < 0.48 * sr:
        w = sosfilt(butter(2, high_cut, "lowpass", fs=sr, output="sos"), w, axis=0)
    if width != 1.0:
        mm = 0.5 * (w[:, 0] + w[:, 1])
        ss = 0.5 * (w[:, 0] - w[:, 1]) * width
        w = np.stack([mm + ss, mm - ss], axis=1)
    w = match_loudness(w, to_stereo64(x), sr, gain_db)
    return finish(x, w, mix, sr)
