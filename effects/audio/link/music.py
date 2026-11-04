"""Music analysis for the audio link: the beat grid, the downbeats, the hits, the kicks and the energy of the
bass, mids and highs, from any music file, for the beat family (effects/beat) and the renderers' --link.

What it finds, all times in seconds of the file:
  beats      the beat tracker (librosa's dynamic programme) run on a percussive onset envelope, with a local tempo
             curve folded to the track's own octave so a slow rubato or a drifting live tempo is followed, each beat
             then moved to the onset peak within 35 ms of it
  bar        each beat's place in its bar (0 the downbeat), by a Viterbi pass over four cues per beat: a change of
             harmony (chroma), a change of bass note, a kick, a snare. A bar of the wrong length (a 2/4 bar in a
             bridge) costs a fixed penalty, so the phase can move where the music does and holds where it is unsure
  hits       onsets of the whole mix (spectral flux with a maximum filter, so vibrato is not read as a hit), each
             with a strength over the track's own local loudness (its 95th percentile over 10 s)
  kicks      onsets under 150 Hz, the same way
  tier       per event, how sparse a list it survives: tier 3 events are at least 0.5 s apart, tier 2 at least
             0.36 s, tier 1 0.25 s, tier 0 0.125 s. Each list is the next sparser one plus the strongest events that
             keep its gap, so the lists nest. Tier 2 is the photosensitive limit: no more than 3 flashes in any second
  curves     low (under 150 Hz), mid (150 Hz to 2.5 kHz), high (above 2.5 kHz), each the band's amplitude over its own
             98th percentile, followed with a 30 ms attack and a 250 ms release

usage: python -I music.py <audio or video> <out.json> [--start s] [--dur s] [--meter 4] [--fast]
--fast skips the harmonic and percussive split (about 3 times quicker on a long track, a little less steady on
music with pads). MIT License.
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

SR = 22050
HOP = 256
NFFT = 2048
GAPS = (0.125, 0.25, 0.36, 0.5)
LAT_ONSET, LAT_LOW = 0.015, 0.025

def load(path, start=0.0, dur=0.0, sr=SR):
    """Any file ffmpeg reads, as mono float32 at sr."""
    import soundfile as sf
    tmp = os.path.join(tempfile.gettempdir(), f"music_{os.getpid()}.wav")
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{start}", "-i", path]
    if dur:
        cmd += ["-t", f"{dur}"]
    subprocess.run(cmd + ["-vn", "-ac", "1", "-ar", str(sr), "-c:a", "pcm_f32le", tmp], check=True)
    x, _ = sf.read(tmp, dtype="float32")
    os.remove(tmp)
    return x

def follow(v, rate, attack, release):
    """A peak follower at rate samples a second: rises with time constant attack, falls with release (seconds)."""
    a, r = np.exp(-1.0 / max(1e-3, attack * rate)), np.exp(-1.0 / max(1e-3, release * rate))
    out, y = np.empty(len(v)), 0.0
    for i, s in enumerate(v):
        k = a if s > y else r
        y = k * y + (1 - k) * s
        out[i] = y
    return out

def local_norm(env, rate, win=10.0, q=95):
    """env over its own q-th percentile in a window of win seconds, so a quiet intro has hits of its own."""
    from scipy.ndimage import percentile_filter
    step = max(1, int(rate * 0.5))
    coarse = env[::step]
    w = max(3, int(win * rate / step) | 1)
    ref = percentile_filter(coarse, q, size=w, mode="nearest")
    ref = np.interp(np.arange(len(env)), np.arange(len(coarse)) * step, ref)
    floor = np.percentile(env, 95) * 0.15 + 1e-9
    return env / np.maximum(ref, floor)

def peaks(env, rate, wait, k=1.0, win=2.0):
    """Peaks of env above a moving threshold (median plus k times the spread over win seconds), wait s apart."""
    from scipy.ndimage import median_filter
    w = max(3, int(win * rate) | 1)
    med = median_filter(env, size=w, mode="nearest")
    mad = median_filter(np.abs(env - med), size=w, mode="nearest") * 1.4826
    thr = med + k * mad + 1e-6
    out, last = [], -10 ** 9
    gap = int(round(wait * rate))
    for i in range(1, len(env) - 1):
        if env[i] > thr[i] and env[i] >= env[i - 1] and env[i] >= env[i + 1]:
            if i - last >= gap:
                out.append(i)
                last = i
            elif env[i] > env[last]:
                out[-1] = i
                last = i
    return np.array(out, dtype=int)

def tiers(times, strength, gaps=GAPS):
    """Nested sparse lists: tier[i] is the largest g such that event i is in the list of gap gaps[g], or -1."""
    import bisect
    times = [float(t) for t in times]
    order = np.argsort(-np.asarray(strength, dtype=float), kind="stable")
    tier = np.full(len(times), -1, dtype=int)
    sel = []
    for g in range(len(gaps) - 1, -1, -1):
        for i in order:
            if tier[i] >= 0:
                continue
            t = times[i]
            j = bisect.bisect_left(sel, t)
            if (j > 0 and t - sel[j - 1] < gaps[g] - 1e-9) or (j < len(sel) and sel[j] - t < gaps[g] - 1e-9):
                continue
            tier[i] = g
            sel.insert(j, t)
    return tier

def robust_z(v):
    v = np.asarray(v, dtype=np.float64)
    med = np.median(v)
    mad = np.median(np.abs(v - med)) * 1.4826 + 1e-9
    return np.clip((v - med) / mad, -3, 3)

def bar_positions(feat, meter=4, jump=6.0):
    """Each beat's place in its bar by Viterbi over per-beat cues (z-scored): harm, bass, kick, snare."""
    n = len(feat["harm"])
    if n == 0:
        return np.zeros(0, dtype=int)
    h, b, k, s = (robust_z(feat[c]) for c in ("harm", "bass", "kick", "snare"))
    em = np.zeros((n, meter))
    em[:, 0] = 1.0 * h + 0.7 * b + 0.5 * k - 0.3 * s
    for p in range(1, meter):
        backbeat = (meter == 4 and p in (1, 3)) or (meter == 3 and p in (1, 2))
        em[:, p] = (0.45 * s if backbeat else 0.2 * k) - 0.25 * h - 0.15 * b
    score = em[0].copy()
    back = np.zeros((n, meter), dtype=int)
    for i in range(1, n):
        new = np.empty(meter)
        for p in range(meter):
            cand = score - jump
            cand[(p - 1) % meter] += jump
            j = int(np.argmax(cand))
            new[p] = cand[j] + em[i, p]
            back[i, p] = j
        score = new
    pos = np.zeros(n, dtype=int)
    pos[-1] = int(np.argmax(score))
    for i in range(n - 1, 0, -1):
        pos[i - 1] = back[i, pos[i]]
    return pos

def analyse(y, sr=SR, meter=4, fast=False):
    import librosa
    rate = sr / HOP
    S = np.abs(librosa.stft(y, n_fft=NFFT, hop_length=HOP)).astype(np.float32)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=NFFT)
    mel = librosa.feature.melspectrogram(S=S ** 2, sr=sr, n_mels=128, fmax=11000)
    mel_f = librosa.mel_frequencies(n_mels=128, fmax=11000)
    P = mel if fast else librosa.decompose.hpss(mel, kernel_size=(17, 17), power=2.0)[1]

    def superflux(M):
        return librosa.onset.onset_strength(S=librosa.power_to_db(M, ref=np.max), sr=sr, hop_length=HOP,
                                            lag=2, max_size=3, center=False)
    env_p = superflux(P)
    env_a = superflux(mel)
    lowmask = freqs < 150
    ll = np.log1p(100 * S[lowmask] / (S[lowmask].max() + 1e-9))
    low_flux = np.concatenate([[0], np.maximum(ll[:, 1:] - ll[:, :-1], 0).sum(0)])
    mh = (mel_f >= 1000) & (mel_f < 6000)
    pm = np.log1p(100 * np.sqrt(P[mh]) / (np.sqrt(P[mh]).max() + 1e-9))
    snare_flux = np.concatenate([[0], np.maximum(pm[:, 1:] - pm[:, :-1], 0).sum(0)])

    tg = float(np.atleast_1d(librosa.feature.tempo(onset_envelope=env_p, sr=sr, hop_length=HOP))[0])
    try:
        tl = librosa.feature.tempo(onset_envelope=env_p, sr=sr, hop_length=HOP, aggregate=None, ac_size=8.0)
        tl = np.where(tl > 0, tl, tg)
        tl = tl * 2.0 ** np.round(np.log2(tg / tl))
        from scipy.ndimage import median_filter
        tl = median_filter(tl, size=max(3, int(10 * rate) | 1), mode="nearest")
        tl = np.clip(tl, tg / 1.45, tg * 1.45)
        _, bf = librosa.beat.beat_track(onset_envelope=env_p, sr=sr, hop_length=HOP, bpm=tl, tightness=100,
                                        trim=False, units="frames")
    except Exception as e:
        print("local tempo skipped:", e)
        _, bf = librosa.beat.beat_track(onset_envelope=env_p, sr=sr, hop_length=HOP, bpm=tg, tightness=100,
                                        trim=False, units="frames")
    bf = np.asarray(bf, dtype=int)
    rms = librosa.feature.rms(S=S, frame_length=NFFT)[0]
    loud = rms > 0.05 * np.percentile(rms, 95)
    if loud.any():
        first, last = np.argmax(loud), len(loud) - 1 - np.argmax(loud[::-1])
        bf = bf[(bf >= first - 2) & (bf <= last + 2)]
    r = max(1, int(round(0.035 * rate)))
    ref = []
    for b in bf:
        lo, hi = max(0, b - r), min(len(env_p), b + r + 1)
        seg = env_p[lo:hi]
        j = lo + int(np.argmax(seg))
        ref.append(j if seg.max() > 1.3 * env_p[b] + 1e-9 else b)
    bf = np.array(sorted(set(ref)), dtype=int)
    beats = bf * HOP / sr + LAT_ONSET

    from scipy.ndimage import median_filter as _mf
    chroma = _mf(librosa.feature.chroma_stft(S=S ** 2, sr=sr, n_fft=NFFT, hop_length=HOP), size=(1, 17))
    bassmask = (freqs >= 35) & (freqs < 250)
    bass = S[bassmask]
    harm, bnov, kick, snare = [], [], [], []
    edges = np.concatenate([bf, [S.shape[1]]])
    prev_c, prev_b = None, None
    w2 = max(1, int(round(0.05 * rate)))
    for i, b in enumerate(bf):
        seg = slice(b, max(b + 1, edges[i + 1]))
        c = np.median(chroma[:, seg], axis=1)
        bb = np.log1p(np.mean(bass[:, seg], axis=1))
        if prev_c is None:
            harm.append(0.0)
            bnov.append(0.0)
        else:
            harm.append(1 - float(np.dot(c, prev_c) / (np.linalg.norm(c) * np.linalg.norm(prev_c) + 1e-9)))
            bnov.append(1 - float(np.dot(bb, prev_b) / (np.linalg.norm(bb) * np.linalg.norm(prev_b) + 1e-9)))
        prev_c, prev_b = c, bb
        kick.append(float(low_flux[max(0, b - w2):b + w2 + 1].max()))
        snare.append(float(snare_flux[max(0, b - w2):b + w2 + 1].max()))
    pos = bar_positions({"harm": harm, "bass": bnov, "kick": kick, "snare": snare}, meter)
    beat_strength = np.clip(local_norm(env_p, rate)[bf] if len(bf) else np.zeros(0), 0, 1)

    na = local_norm(env_a, rate)
    hf = peaks(na, rate, wait=0.08, k=1.5)
    hits, hstr = hf * HOP / sr + LAT_ONSET, np.clip(na[hf] / 1.5, 0, 1) if len(hf) else np.zeros(0)
    nl = local_norm(low_flux, rate)
    kf = peaks(nl, rate, wait=0.15, k=2.0)
    low_amp = np.sqrt((S[lowmask] ** 2).sum(0))
    after = max(1, int(round(0.07 * rate)))
    keep = [i for i, f in enumerate(kf) if low_amp[f:f + after].max() > 0.25 * np.percentile(low_amp, 95)]
    kf = kf[keep]
    kicks, kstr = kf * HOP / sr + LAT_LOW, np.clip(nl[kf] / 1.5, 0, 1) if len(kf) else np.zeros(0)

    def band(mask):
        v = np.sqrt((S[mask] ** 2).sum(0))
        v = np.clip(v / (np.percentile(v, 98) + 1e-9), 0, 1)
        return follow(v, rate, 0.03, 0.25)
    curves = {"low": band(lowmask), "mid": band((freqs >= 150) & (freqs < 2500)), "high": band(freqs >= 2500)}

    def on_downbeat(times):
        db = beats[pos == 0] if len(beats) else np.zeros(0)
        if len(db) == 0:
            return np.zeros(len(times), dtype=bool)
        j = np.clip(np.searchsorted(db, times), 1, len(db) - 1) if len(db) > 1 else np.zeros(len(times), int)
        d = np.minimum(np.abs(db[j] - times), np.abs(db[np.maximum(j - 1, 0)] - times))
        return d < 0.05

    bstr_for_tier = np.where(pos == 0, 1.0, 0.5) if len(beats) else np.zeros(0)
    return {
        "sr": sr, "hop": HOP, "duration": len(y) / sr, "tempo": tg, "meter": meter,
        "beats": [round(float(t), 4) for t in beats],
        "bar": [int(p) for p in pos],
        "beat_strength": [round(float(s), 3) for s in beat_strength],
        "beat_tier": [int(t) for t in tiers(beats, bstr_for_tier)],
        "hits": [round(float(t), 4) for t in hits], "hit_strength": [round(float(s), 3) for s in hstr],
        "hit_tier": [int(t) for t in tiers(hits, hstr)], "hit_down": [bool(v) for v in on_downbeat(hits)],
        "kicks": [round(float(t), 4) for t in kicks], "kick_strength": [round(float(s), 3) for s in kstr],
        "kick_tier": [int(t) for t in tiers(kicks, kstr)], "kick_down": [bool(v) for v in on_downbeat(kicks)],
        "curve_rate": rate,
        "curves": {k: [round(float(v), 4) for v in c] for k, c in curves.items()},
    }

def main():
    a = sys.argv[1:]
    arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    import time
    t0 = time.time()
    y = load(a[0], float(arg("--start", 0)), float(arg("--dur", 0)))
    m = analyse(y, meter=int(arg("--meter", 4)), fast="--fast" in a)
    m["seconds"] = round(time.time() - t0, 2)
    json.dump(m, open(a[1], "w", encoding="utf-8"))
    print(f"{m['duration']:.1f} s, tempo {m['tempo']:.1f}, {len(m['beats'])} beats "
          f"({sum(1 for p in m['bar'] if p == 0)} downbeats), {len(m['hits'])} hits, {len(m['kicks'])} kicks, "
          f"{m['seconds']} s -> {a[1]}")

if __name__ == "__main__":
    main()
