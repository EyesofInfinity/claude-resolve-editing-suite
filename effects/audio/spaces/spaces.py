"""Develop Spaces: the registry. Each effect is fx(x, sr, **params) -> y, x float32 (samples, channels)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from verbs import shimmer, wash
from rooms import room, partitioned_convolve
from preverb import preverb, detect_onset
from stretch import stretch, freeze
import irsynth

FX = {
    "shimmer": shimmer,
    "wash": wash,
    "room": room,
    "preverb": preverb,
    "stretch": stretch,
    "freeze": freeze,
}

PRESETS = sorted(irsynth.PRESETS)
