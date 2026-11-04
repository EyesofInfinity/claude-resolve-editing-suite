"""Reverse reverb swell (pre-verb): the reverb of a word or a hit, reversed, rising into its onset."""
import numpy as np
from scipy.ndimage import uniform_filter1d

from common import as2d, to_stereo64, finish, fade
import rooms
import irsynth

def detect_onset(x, sr, frame_ms=2.0):
    """First onset in seconds: the frame where a 2 ms RMS envelope first comes within 24 dB of the file's
    peak (and at least 12 dB over the floor, the 10th percentile), walked back up to 40 ms to where it
    left the floor plus 6 dB. Breaths and lip noise 24 dB under the voice are passed over."""
    a = as2d(x).astype(np.float64)
    m = np.mean(a * a, axis=1)
    fr = max(1, int(frame_ms * 1e-3 * sr))
    k = m.size // fr
    if k < 4:
        return 0.0
    e = 10 * np.log10(m[: k * fr].reshape(k, fr).mean(axis=1) + 1e-20)
    floor = np.percentile(e, 10)
    peak = e.max()
    thr = max(floor + 12.0, peak - 24.0)
    i = int(np.argmax(e >= thr))
    lo = floor + 6.0
    j = i
    while j > 0 and e[j - 1] > lo and (i - j) * frame_ms < 40.0:
        j -= 1
    return j * fr / sr

def preverb(x, sr, onset=None, length=2.5, word=0.6, preset="cathedral", decay=None, mix=0.5, gain_db=0.0,
            end_ms=12.0, seed=1):
    """Pre-verb: reverb the segment that starts at the onset, reverse it, end it at the onset.

    onset    seconds; None detects the first onset
    length   seconds of swell before the onset
    word     seconds of source after the onset that are reverbed (the word or the hit)
    preset   any convolution room preset (cathedral by default)
    decay    scales the preset's RT60; None sets the 1 kHz RT60 equal to length, so the swell rises about
             60 dB across its length
    mix      dry/wet (equal power), 0 returns x exactly, 1 is the swell alone; the swell's peak short term level equals
             the segment's peak short term level (plus gain_db)
    end_ms   after the onset the swell falls to zero over end_ms (a raised cosine), so it peaks at the
             onset without a click
    When the onset is earlier than length, the output gains a lead of (length - onset) seconds of
    silence at its start: place the file that much earlier on the timeline. preverb.last_lead holds it.
    The output is stereo, as long as the input plus that lead.
    """
    global last_lead
    if mix == 0:
        last_lead = 0.0
        return x.copy()
    a = as2d(x).astype(np.float64)
    t0 = detect_onset(a, sr) if onset is None else float(onset)
    i0 = int(round(t0 * sr))
    seg = a[i0:i0 + int(word * sr)].copy()
    fade(seg, int(0.002 * sr), int(0.02 * sr))
    n_in = 1 if a.shape[1] == 1 else 2
    if decay is None:
        decay = round(float(length) / float(irsynth.T_of_f(preset, np.array([1000.0]))[0]), 3)
    h = rooms.ir(preset, sr, n_in, decay, seed)
    w = rooms.partitioned_convolve(seg[:, :n_in], h)
    win = int(0.02 * sr)
    env = uniform_filter1d(np.sum(w * w, axis=1), win, mode="nearest")
    p = int(np.argmax(env))
    L = int(length * sr)
    r = w[p:p + L][::-1].copy()
    if r.shape[0] < L:
        r = np.concatenate([np.zeros((L - r.shape[0], 2)), r], axis=0)
    w10 = int(0.01 * sr)
    env = np.sqrt(uniform_filter1d(np.mean(r * r, axis=1), w10, mode="nearest")) + 1e-12
    suf = np.minimum.accumulate(env[::-1])[::-1]
    rt = float(irsynth.T_of_f(preset, np.array([1000.0]), decay)[0])
    tt = (np.arange(r.shape[0]) - (r.shape[0] - 1)) / sr
    line = env[-1] * 10 ** (tt * (60.0 / rt) / 20.0)
    g = uniform_filter1d(np.minimum(suf, line) / env, max(1, int(0.005 * sr)), mode="nearest")
    r *= g[:, None]
    ref = uniform_filter1d(np.mean(seg * seg, axis=1), win, mode="nearest").max()
    got = uniform_filter1d(np.sum(r * r, axis=1) / 2, win, mode="nearest").max() + 1e-30
    r *= np.sqrt(ref / got) * 10 ** (gain_db / 20)
    ne = int(end_ms * 1e-3 * sr)
    pre = w[max(0, p - ne):p][::-1] * np.sqrt(ref / got) * 10 ** (gain_db / 20)
    if pre.shape[0] < ne:
        pre = np.concatenate([pre, np.zeros((ne - pre.shape[0], 2))], axis=0)
    pre *= (0.5 + 0.5 * np.cos(np.pi * (np.arange(ne) + 0.5) / ne))[:, None]
    fade(r, int(0.1 * L), 0)
    r = np.concatenate([r, pre], axis=0)
    lead = max(0, L - i0)
    last_lead = lead / sr
    start = i0 + lead - L
    n = a.shape[0] + lead
    sw = np.zeros((max(n, start + r.shape[0]), 2))
    sw[start:start + r.shape[0]] += r
    return finish(x, sw, mix, sr, front=lead)

last_lead = 0.0
