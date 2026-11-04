"""Shimmer and Ambient Wash: the two algorithmic spaces, both on the tank in tank.py."""
import numpy as np
from scipy.signal import butter, sosfilt

from common import as2d, to_stereo64, finish, match_loudness, fade
import tank

def _tone(w, sr, low_cut, high_cut):
    if low_cut and low_cut > 0:
        w = sosfilt(butter(2, low_cut, "highpass", fs=sr, output="sos"), w, axis=0)
    if high_cut and high_cut < 0.48 * sr:
        w = sosfilt(butter(2, high_cut, "lowpass", fs=sr, output="sos"), w, axis=0)
    return w

def _width(w, width):
    if width == 1.0:
        return w
    m = 0.5 * (w[:, 0] + w[:, 1])
    s = 0.5 * (w[:, 0] - w[:, 1]) * width
    return np.stack([m + s, m - s], axis=1)

def _predelay(x2, sr, predelay):
    k = int(round(max(0.0, predelay) * sr))
    if k == 0:
        return x2
    return np.concatenate([np.zeros((k, 2)), x2], axis=0)

def shimmer(x, sr, mix=0.35, decay=6.0, size=1.0, shimmer=0.5, fifth=0.0, damp=0.45, predelay=0.02,
            mod=1.0, low_cut=150.0, high_cut=14000.0, width=1.0, gain_db=0.0, tail=None, seed=7):
    """Shimmer: a dense diffuse reverb with an octave up (and optional fifth) pitch shifter in the feedback.

    mix       dry/wet (equal power), 0 returns x exactly, 1 is the wet alone (wet loudness matched to the input)
    decay     RT60 in seconds at 1 kHz (with shimmer 0; the climbing energy is lost faster at the top)
    size      scales every delay (0.5 to 2)
    shimmer   0 to 1, the share of four of the sixteen lines that is pitch shifted on every pass
    fifth     0 to 1, crossfade of the shifted share from the octave to a fifth (ratio 1.5)
    damp      high frequency RT60 as a fraction of decay (0.1 dark to 1 bright)
    predelay  seconds before the tank sees the input
    mod       scales the delay modulation (0 none, 1 default 0.6 ms)
    low_cut, high_cut   wet only filters in Hz
    Output is stereo and longer than x by tail seconds (default 1.2 x decay, about -72 dB).
    """
    if mix == 0:
        return x.copy()
    x2 = to_stereo64(x)
    dz = tank.design(sr, decay=decay, hf_ratio=damp, size=size, line_ms=(30.0, 95.0), diff_ms=45.0,
                     stages=4, mod_ms=0.6 * mod, mod_hz=(0.12, 0.9), seed=seed)
    tail_s = 1.2 * decay if tail is None else tail
    n_out = x2.shape[0] + int(tail_s * sr)
    w = tank.render(_predelay(x2, sr, predelay), sr, n_out, dz, shimmer=shimmer, fifth=fifth)
    w = _width(_tone(w, sr, low_cut, high_cut), width)
    fade(w, 0, int(0.25 * sr))
    w = match_loudness(w, x2, sr, gain_db)
    return finish(x, w, mix, sr)

def wash(x, sr, mix=0.4, decay=18.0, size=1.6, damp=0.3, predelay=0.03, mod=1.0, low_cut=60.0,
         high_cut=6500.0, freeze_at=None, freeze_for=10.0, width=1.0, gain_db=0.0, tail=None, seed=11):
    """Ambient wash: a very long, heavily diffused and modulated space with Freeze.

    mix        dry/wet (equal power), 0 returns x exactly, 1 is the wet alone (wet loudness matched to the input)
    decay      RT60 in seconds at 1 kHz (4 to 60)
    size       scales every delay (1 to 2.5)
    damp       high frequency RT60 as a fraction of decay
    high_cut   the gentle lowpass on the tail (2nd order, Hz)
    mod        scales the delay modulation (1 is 2.5 ms deep at 0.07 to 0.35 Hz)
    freeze_at  seconds into the input where the tank closes its input and holds forever (None is off)
    freeze_for seconds the tank is held; then it decays at decay
    Output is stereo, as long as max(input, freeze end) plus tail seconds (default 1.2 x decay).
    """
    if mix == 0:
        return x.copy()
    x2 = to_stereo64(x)
    dz = tank.design(sr, decay=decay, hf_ratio=damp, size=size, line_ms=(60.0, 200.0), diff_ms=120.0,
                     stages=6, mod_ms=2.5 * mod, mod_hz=(0.07, 0.35), seed=seed)
    fr = None
    end = x2.shape[0]
    pd = int(round(max(0.0, predelay) * sr))
    if freeze_at is not None:
        a = int(float(freeze_at) * sr) + pd
        b = a + int(float(freeze_for) * sr)
        fr = (a, b)
        end = max(end, b)
    tail_s = 1.2 * decay if tail is None else tail
    n_out = end + int(tail_s * sr)
    w = tank.render(_predelay(x2, sr, predelay), sr, n_out, dz, freeze=fr)
    w = _width(_tone(w, sr, low_cut, high_cut), width)
    fade(w, 0, int(0.5 * sr))
    w = match_loudness(w, x2, sr, gain_db)
    return finish(x, w, mix, sr)
