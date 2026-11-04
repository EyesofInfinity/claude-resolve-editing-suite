"""The light layers of Develop Light Comp: the existing Develop light DCTLs run through the CPU harness
(lightrun.mjs, the same DCTL code Resolve runs), giving the light alone in linear.

Two ways, by what the light is:
- black: the DCTL over a black frame. Stage Light's beams in haze, the Laser's beam, arcs and flash, and Glow
  Dissolve's flare, bulbs and lightning add light in linear and relight by multiplying, so over black only the light
  they emit is left.
- diff: the DCTL over the plate, minus the plate, in linear. Glare, Glow Plus and Glow Dissolve's own-light styles
  answer the plate's own lights, so they need the picture.

Layers are cached as float32 display values under tests/out/lightcomp/layers. MIT License.
"""
import hashlib
import json
import os
import subprocess

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
EFF = os.path.dirname(HERE)
REPO = os.path.dirname(EFF)
CACHE = os.path.join(REPO, "tests", "out", "lightcomp", "layers")
RUN = os.path.join(HERE, "lightrun.mjs")

SL = "stage/build/Develop Stage Light.dctl"
LZ = "stage/build/Develop Laser.dctl"
GD = "glowdis/build/Develop Glow Dissolve.dctl"
GL = "glare/build/Develop Glare.dctl"
GP = "glare/build/Develop Glow Plus.dctl"

LIGHTS = {
    "stage": (SL, {"slMode": 2}, "black", "scene", "Develop Stage Light, Stage Light: beams on a rig through haze"),
    "laser": (LZ, {"lzMode": 0}, "black", "scene", "Develop Laser, Laser Beam"),
    "zap_to": (LZ, {"lzMode": 1}, "black", "scene", "Develop Laser, Zap To"),
    "zap_from": (LZ, {"lzMode": 2}, "black", "scene", "Develop Laser, Zap From"),
    "flash": (LZ, {"lzMode": 3}, "black", "scene", "Develop Laser, Muzzle Flash"),
    "flare": (GD, {"gdStyle": 7, "gdWash": 0}, "black", "lens", "Develop Glow Dissolve, Lens Flare"),
    "bulbs": (GD, {"gdStyle": 4, "gdWash": 0}, "black", "scene", "Develop Glow Dissolve, Flashbulbs"),
    "zap": (GD, {"gdStyle": 5, "gdWash": 0}, "black", "scene", "Develop Glow Dissolve, Zap"),
    "glow_dis": (GD, {"gdStyle": 0, "gdWash": 0}, "diff", "lens", "Develop Glow Dissolve, Glow"),
    "orbs": (GD, {"gdStyle": 6, "gdWash": 0}, "diff", "lens", "Develop Glow Dissolve, Orbs"),
    "glare": (GL, {"glMode": 0}, "diff", "lens", "Develop Glare, Glare"),
    "streaks": (GL, {"glMode": 1}, "diff", "lens", "Develop Glare, Streaks"),
    "glow": (GP, {"gpMode": 0}, "diff", "lens", "Develop Glow Plus, Glow"),
}

def _key(path, params, source, frame, progress, plate, size):
    h = hashlib.sha1()
    h.update(open(path, "rb").read())
    h.update(json.dumps(params, sort_keys=True).encode())
    h.update(f"{source}|{frame}|{progress}|{size[0]}x{size[1]}".encode())
    if plate is not None:
        h.update(hashlib.sha1(plate.tobytes()).digest())
    return h.hexdigest()[:20]

def run_dctl(dctl, params, frame, plate=None, progress=None, size=(1920, 1080)):
    """The DCTL's output, float32 display values HxWx3, over black (plate None) or over the plate (uint8 HxWx3)."""
    path = os.path.join(EFF, dctl) if not os.path.isabs(dctl) else dctl
    W, H = (plate.shape[1], plate.shape[0]) if plate is not None else size
    os.makedirs(CACHE, exist_ok=True)
    k = _key(path, params, "plate" if plate is not None else "black", frame, progress, plate, (W, H))
    out = os.path.join(CACHE, k + ".f32")
    if not os.path.exists(out):
        inp = "black"
        if plate is not None:
            inp = os.path.join(CACHE, f"{k}.{os.getpid()}.rgb")
            np.ascontiguousarray(plate).tofile(inp)
        part = f"{out}.{os.getpid()}.part"
        cmd = ["node", RUN, path, json.dumps(params), inp, str(W), str(H), str(int(frame)), part]
        if progress is not None:
            cmd.append(f"{progress:.6f}")
        if subprocess.run(cmd).returncode != 0:
            subprocess.run(cmd, check=True)
        os.replace(part, out)
        if plate is not None:
            os.remove(inp)
    return np.fromfile(out, np.float32).reshape(H, W, 3)

def layer(name, frame, plate, params=None, progress=None, dctl=None, source=None):
    """The light alone, linear CHW on the device. plate: the frame (uint8 HxWx3), used for a diff layer."""
    import depthfx as dx
    d0, p0, s0, _, _ = LIGHTS[name] if name in LIGHTS else (dctl, {}, source or "black", "scene", "")
    dctl = dctl or d0
    src = source or s0
    P = {**p0, **(params or {})}
    if src == "black":
        o = run_dctl(dctl, P, frame, None, progress, (plate.shape[1], plate.shape[0]))
        t = torch.from_numpy(np.ascontiguousarray(o)).to(dx.DEV).permute(2, 0, 1)
        return t.clamp(0, 1) ** dx.GAMMA
    o = run_dctl(dctl, P, frame, plate, progress)
    t = torch.from_numpy(np.ascontiguousarray(o)).to(dx.DEV).permute(2, 0, 1).clamp(0, 1) ** dx.GAMMA
    return (t - dx.lin(plate)).clamp(min=0)

def before(name, frame, plate, params=None, progress=None):
    """The DCTL itself on the plate, as it is laid today (8-bit, as Resolve shows it)."""
    d0, p0, _, _, _ = LIGHTS[name]
    o = run_dctl(d0, {**p0, **(params or {})}, frame, plate, progress)
    return (np.clip(o, 0, 1) * 255 + 0.5).astype(np.uint8)
