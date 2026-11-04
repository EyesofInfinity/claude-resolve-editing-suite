"""Measure every join of a cut: did it cut through sound (clipped word ending or onset), does it click, does the room
tone step. usage: join_check.py <source media> <edl.json with keep_ranges> <output media> [--track n]
Levels are in dB relative to the median loudness of speech in the source. A join next to a removed flub reads as
"through a word ending" when the flub itself starts at speech, so check those by ear. MIT License."""
import json, subprocess, sys
import numpy as np

SR = 48000
if "--track" in sys.argv:
    k = sys.argv.index("--track")
    TRACK = sys.argv[k + 1]
    del sys.argv[k:k + 2]
else:
    TRACK = "0"
if len(sys.argv) != 4:
    sys.exit(__doc__)
def pcm(path, track="0"):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", path, "-map", f"0:a:{track}", "-af", "aresample=async=1:first_pts=0", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)
def db(x):
    return 20 * np.log10(np.sqrt(np.mean(x.astype(np.float64) ** 2)) + 1e-9)

src, out = pcm(sys.argv[1], TRACK), pcm(sys.argv[3])
keep = json.load(open(sys.argv[2], encoding="utf-8"))["keep_ranges"]
frames = np.array([db(src[i:i + 960]) for i in range(0, len(src) - 960, 960)])  # 20 ms frames
speech = np.median(frames[frames > np.percentile(frames, 60)])
room = np.percentile(frames, 10)
print(f"speech level {speech:.1f} dBFS, room tone {room:.1f} dBFS ({speech - room:.0f} dB below speech)")
rows, t_out = [], 0.0
for a, b in zip(keep, keep[1:]):
    t_out += a["end"] - a["start"]
    e1, s2 = int(a["end"] * SR), int(b["start"] * SR)
    # sound just past the kept end (cut a word's tail?) and just before the next kept start (cut an onset?)
    tail = db(src[e1:e1 + int(0.04 * SR)]) - speech
    onset = db(src[max(0, s2 - int(0.04 * SR)):s2]) - speech
    # click: the sample step at the join against the steps around it in the output
    j = int(t_out * SR)
    w = out[max(1, j - 2400):j + 2400]
    steps = np.abs(np.diff(w))
    near = np.abs(np.diff(out[max(1, j - 48):j + 48])).max() if j + 48 < len(out) else 0
    click = near / (np.percentile(steps, 99) + 1e-9)
    # room-tone step: level 60 ms either side of the join in the output
    step = abs(db(out[max(0, j - 2880):j]) - db(out[j:j + 2880]))
    rows.append((t_out, tail, onset, click, step))
cut_tail = [r for r in rows if r[1] > -25]
cut_onset = [r for r in rows if r[2] > -25]
clicks = [r for r in rows if r[3] > 2.0]
print(f"{len(rows)} joins | cut through a word ending (sound within 25 dB of speech just after the cut): {len(cut_tail)}"
      f" | through an onset: {len(cut_onset)} | possible clicks (step over 2x the local 99th percentile): {len(clicks)}")
print(" join(out s)  tail_dB  onset_dB  click_x  level_step_dB")
worst = sorted(rows, key=lambda r: -(max(r[1], r[2]) + 25 + 10 * max(0, r[3] - 1)))
for r in worst[:8]:
    print(f"   {r[0]:8.2f}  {r[1]:7.1f}  {r[2]:8.1f}  {r[3]:7.2f}  {r[4]:8.1f}")
