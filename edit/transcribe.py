"""Word-level transcript of a recording for the cut tools, run locally with faster-whisper.

Uses medium.en with a prompt full of fillers and restarts, so the model writes down "um", "uh" and abandoned
half-lines instead of tidying them away: on a real take the small model dropped the false start the cut tools needed
to see. Audio is decoded with ffmpeg (faster-whisper's own reader can clash with the installed PyAV). It tries the
GPU and falls back to the CPU when the CUDA libraries are missing.

usage: python -I transcribe.py <media> <out.json> [--model medium.en] [--track 0]
Writes {"audio_duration_secs": d, "words": [{"text", "start", "end"}]}, the shape cut-silences.mjs reads. MIT License.
"""
import json
import os
import subprocess
import sys

import numpy as np

PROMPT = "Umm, so, uh, I- I mean, like, you know, the the thing is... Hmm. Uh, okay."


def main():
    args = sys.argv[1:]
    if len(args) < 2 or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    media, out = args[0], args[1]
    model_name = args[args.index("--model") + 1] if "--model" in args else "medium.en"
    track = args[args.index("--track") + 1] if "--track" in args else "0"
    if os.path.normcase(os.path.abspath(out)) == os.path.normcase(os.path.abspath(media)):
        sys.exit("the output must be a new .json file, not the recording")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)   # before the long part, not after it
    # from the file's clock zero, as the cut tools read it: an audio stream that starts late is padded
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", media, "-map", f"0:a:{track}", "-af", "aresample=async=1:first_pts=0",
                              "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True)
    if decoded.returncode:
        sys.exit(f"{media} has no audio track {track}, or FFmpeg cannot read it: {decoded.stderr.decode(errors='replace')[-200:]}")
    pcm = decoded.stdout
    audio = np.frombuffer(pcm, np.float32)
    from faster_whisper import WhisperModel
    words = None
    for device, compute in (("cuda", "float16"), ("cpu", "int8")):
        try:
            segs, _ = WhisperModel(model_name, device=device, compute_type=compute).transcribe(audio, word_timestamps=True, initial_prompt=PROMPT)
            words = [{"text": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)} for s in segs for w in s.words]
            break
        except (RuntimeError, ValueError) as e:  # missing CUDA libraries surface as RuntimeError on first use
            print(f"transcribe: {device} unavailable ({str(e).splitlines()[0][:80]}), trying the next device", file=sys.stderr)
    if words is None:
        sys.exit("transcribe: no device could run the model")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"audio_duration_secs": round(len(audio) / 16000, 3), "words": words}, fh, indent=1)
    print(f"{out}: {len(words)} words, {len(audio) / 16000:.1f} s ({model_name}, {device})")


if __name__ == "__main__":
    main()
