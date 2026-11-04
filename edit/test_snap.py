"""Checks of snap_edl.py on synthetic audio with known quiet. Each would fail if the tool did the wrong thing: removed
speech coming back at a mistake cut, a kept word lost at one, a room floor that hides every pause, a source or an earlier
render replaced. Also apply-cuts.mjs and cut-silences.mjs refusing to replace the source.

usage: python -I test_snap.py   (needs numpy, ffmpeg, node). MIT License."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 48000
fails = 0


def check(name, ok, detail=""):
    global fails
    fails += 0 if ok else 1
    print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f": {detail}" if detail else ""))


def take(path, words, dur, floor_db=-90.0):
    """A wav: each word a stretch of loud tone at -20 dBFS, the rest the room's noise at floor_db."""
    rng = np.random.default_rng(3)
    x = 10 ** (floor_db / 20) * rng.standard_normal(int(dur * SR)) / 1.0
    t = np.arange(len(x)) / SR
    tone = 0.1 * np.sqrt(2) * np.sin(2 * np.pi * 220 * t)
    for a, b in words:
        i, j = int(a * SR), int(b * SR)
        x[i:j] += tone[i:j]
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def run(*args):
    if len(args) > 2 and args[2] != args[1] and os.path.exists(args[2]):
        os.remove(args[2])                      # each case starts with no output EDL, so a refusal is for its own reason
    return subprocess.run([sys.executable, "-I", os.path.join(HERE, "snap_edl.py"), *args], capture_output=True, text=True)


def main():
    td = tempfile.mkdtemp(prefix="snaptest")
    try:
        # kept word, a quiet gap, removed word, a quiet gap, kept word; a kept word sits 160 ms before the first cut
        words = [(0.50, 1.00), (1.16, 1.60), (1.68, 2.40), (2.48, 3.20)]
        wav = os.path.join(td, "take.wav")
        take(wav, words, 4.0)
        # the removed speech is 1.68 to 2.40, cut placed on the transcript's times
        edl = {"keep_ranges": [{"start": 0.40, "end": 1.68, "end_at_cut": True}, {"start": 2.40, "end": 3.40, "start_at_cut": True}]}
        a, b = os.path.join(td, "in.json"), os.path.join(td, "out.json")
        json.dump(edl, open(a, "w"))
        r = run(wav, a, b)
        check("runs", r.returncode == 0, r.stderr.strip()[:200])
        out = json.load(open(b))["keep_ranges"]
        check("the end at a cut stays on the kept word's side (1.60 to 1.68)", 1.58 <= out[0]["end"] <= 1.68, str(out[0]["end"]))
        check("the end at a cut does not reach back past the kept word (1.16 to 1.60)", out[0]["end"] > 1.55, str(out[0]["end"]))
        check("the start at a cut never reaches back into removed speech (1.68 to 2.40)", out[1]["start"] >= 2.38, str(out[1]["start"]))
        check("the start at a cut stays before the kept word (2.48)", out[1]["start"] <= 2.48, str(out[1]["start"]))

        # no quiet near a mistake cut: speech on both sides, so the edge stays on the transcript's time
        wav2 = os.path.join(td, "solid.wav")
        take(wav2, [(0.40, 3.40)], 4.0)
        json.dump({"keep_ranges": [{"start": 0.3, "end": 1.5, "end_at_cut": True}, {"start": 2.0, "end": 3.5, "start_at_cut": True}]}, open(a, "w"))
        r = run(wav2, a, b)
        out = json.load(open(b))["keep_ranges"]
        check("no quiet: the end stays put", abs(out[0]["end"] - 1.5) < 0.001, str(out[0]["end"]))
        check("no quiet: the start stays put", abs(out[1]["start"] - 2.0) < 0.001, str(out[1]["start"]))

        # a room with a noise floor at -50 dBFS: an ordinary end of a word still finds the quiet after it
        wav3 = os.path.join(td, "room.wav")
        take(wav3, [(0.50, 1.00), (1.60, 2.20)], 3.0, floor_db=-50.0)
        json.dump({"keep_ranges": [{"start": 0.45, "end": 0.95}, {"start": 1.65, "end": 2.25}]}, open(a, "w"))
        r = run(wav3, a, b)
        out = json.load(open(b))["keep_ranges"]
        check("a room at -50 dBFS still has quiet", "found no quiet" not in r.stdout, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "")
        check("the word's end snapped past its tail", out[0]["end"] >= 1.0, str(out[0]["end"]))

        # the source and earlier renders are safe
        src = os.path.join(td, "src.wav")
        shutil.copy2(wav, src)
        before = open(src, "rb").read()
        json.dump({"keep_ranges": [{"start": 0.4, "end": 3.4}]}, open(a, "w"))
        here = os.getcwd()
        os.chdir(td)
        try:
            for name in ("./src.wav", "SRC.WAV" if os.name == "nt" else "./src.wav", "src.wav"):
                r = run(src, a, b, name)
                check(f"refuses output {name} (the source)", r.returncode != 0 and open(src, "rb").read() == before, r.stderr.strip()[:80])
            r = run(src, a, a)
            check("refuses an output EDL that is the input EDL", r.returncode != 0, r.stderr.strip()[:80])
            old = os.path.join(td, "old.mp4")
            open(old, "wb").write(b"an earlier render")
            r = run(src, a, b, old)
            check("refuses an existing output", r.returncode != 0 and open(old, "rb").read() == b"an earlier render", r.stderr.strip()[:80])
        finally:
            os.chdir(here)

        # an earlier EDL is safe; a second snap keeps the mistake-cut marks
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "snap_edl.py"), src, a, old], capture_output=True, text=True)
        check("refuses an existing output EDL", r.returncode != 0 and open(old, "rb").read() == b"an earlier render", r.stderr.strip()[:80])
        json.dump(edl, open(a, "w"))
        run(wav, a, b)
        marks = json.load(open(b))["keep_ranges"]
        check("the mistake-cut marks stay in the output", marks[0].get("end_at_cut") and marks[1].get("start_at_cut"), str(marks))
        again = os.path.join(td, "again.json")
        run(wav, b, again)
        twice = json.load(open(again))["keep_ranges"]
        check("snapping twice never brings removed speech back", twice[1]["start"] >= 2.38 and twice[0]["end"] <= 1.68, str(twice))

        # audio that starts late: the times stay on the file's clock
        late = os.path.join(td, "late.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=4", "-itsoffset", "0.23", "-i", wav, "-map", "0:v", "-map", "1:a",
                        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", late], check=True)
        json.dump({"keep_ranges": [{"start": 0.6, "end": 1.1}]}, open(a, "w"))
        rendered = os.path.join(td, "late_out.mp4")
        r = run(late, a, b, rendered)
        check("a video source renders; cuts land on whole frames", r.returncode == 0 and all(abs(x["start"] * 30 - round(x["start"] * 30)) < 0.01 for x in json.load(open(b))["keep_ranges"]), r.stderr.strip()[:120])
        kept = json.load(open(b))["keep_ranges"][0]
        check("audio that starts 0.23 s late: the word (0.73 to 1.23) is found on the file's clock", kept["end"] >= 1.2, str(kept))

        # a voice take with no picture renders sound only; a file with no sound stops with a message
        audio_out = os.path.join(td, "voice_out.m4a")
        json.dump({"keep_ranges": [{"start": 0.4, "end": 1.1}]}, open(a, "w"))
        r = run(wav, a, b, audio_out)
        check("a take with no picture renders sound only", r.returncode == 0 and os.path.getsize(audio_out) > 0, r.stderr.strip()[:120])
        silent = os.path.join(td, "silent.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=1", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", silent], check=True)
        r = run(silent, a, b)
        check("a file with no sound stops with a message", r.returncode != 0 and "no audio track" in r.stderr, r.stderr.strip()[:120])
        json.dump({"keep_ranges": []}, open(a, "w"))
        r = run(wav, a, b)
        check("an empty EDL stops with a message", r.returncode != 0 and "no keep ranges" in r.stderr, r.stderr.strip()[:120])

        # the two cutters from the kit refuse the source too
        t = os.path.join(td, "t.json")
        json.dump({"audio_duration_secs": 4.0, "words": [{"text": "a", "start": 0.5, "end": 1.0}, {"text": "b", "start": 2.48, "end": 3.2}]}, open(t, "w"))
        cuts = os.path.join(td, "cuts.json")
        json.dump({"cuts": [{"start": 1.2, "end": 2.0, "reason": "test"}]}, open(cuts, "w"))
        r = subprocess.run(["node", os.path.join(HERE, "apply-cuts.mjs"), t, "--cuts", cuts, "--video", src, "--output", src.upper() if os.name == "nt" else src, "--apply", "--out-dir", td], capture_output=True, text=True)
        check("apply-cuts refuses the source as output", r.returncode != 0 and open(src, "rb").read() == before, r.stderr.strip()[:80])
        r = subprocess.run(["node", os.path.join(HERE, "cut-silences.mjs"), t, "--video", src, "--output", src, "--apply", "--out-dir", td], capture_output=True, text=True)
        check("cut-silences refuses the source as output", r.returncode != 0 and open(src, "rb").read() == before, r.stderr.strip()[:80])
    finally:
        shutil.rmtree(td, ignore_errors=True)
    print(f"{fails} failed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
