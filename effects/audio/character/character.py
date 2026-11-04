"""Develop Character: the registry. Every effect is fx(x, sr, **params) -> y, x float32 (samples, channels)
or 1-D, mix 0 returns x exactly, the output's true peak stays under -1 dBTP (4x oversampled).
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import glitch
import lofi
import motion
import shaper
import speakers
import tape

FX = {
    "tape": tape.tape,
    "tape_stop": tape.tape_stop,
    "tape_start": tape.tape_start,
    "vinyl": lofi.vinyl,
    "cassette": lofi.cassette,
    "bitcrush": lofi.bitcrush,
    "memory": lofi.memory,
    "radio": speakers.radio,
    "telephone": speakers.telephone,
    "old_tv": speakers.old_tv,
    "intercom": speakers.intercom,
    "wall": speakers.wall,
    "ghost": speakers.ghost,
    "robot": speakers.robot,
    "ringmod": speakers.ringmod,
    "octaver": speakers.octaver,
    "terminal": speakers.terminal,
    "stutter": glitch.stutter,
    "beat_repeat": glitch.beat_repeat,
    "tape_scrub": glitch.tape_scrub,
    "gate_pattern": glitch.gate_pattern,
    "doppler": motion.doppler,
    "riser": motion.riser,
    "sub_drop": motion.sub_drop,
    "transient": shaper.transient,
}

_WRAPPED = {"radio", "telephone", "old_tv", "intercom", "wall"}

def params(name):
    """The parameters and defaults of an effect."""
    f = speakers.speaker if name in _WRAPPED else FX[name]
    out = {}
    for p in inspect.signature(f).parameters.values():
        if p.name in ("x", "sr", "model") or p.kind in (p.VAR_KEYWORD, p.VAR_POSITIONAL):
            continue
        out[p.name] = p.default
    return out

def run(name, x, sr, **kw):
    return FX[name](x, sr, **kw)
