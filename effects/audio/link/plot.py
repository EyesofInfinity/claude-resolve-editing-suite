"""A picture of a link json against its waveform: one row per feature, hits as red ticks, beats as blue.
usage: python -I plot.py <link.json> <audio> <out.png> [--start s] [--dur s]
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyse

a = sys.argv[1:]
arg = lambda k, d: a[a.index(k) + 1] if k in a else d
link = json.load(open(a[0], encoding="utf-8"))
x = analyse.load(a[1], float(arg("--start", 0)), float(arg("--dur", 0)))
names = [k for k in ["rms", "low", "mid", "high", "onset", "beat", "downbeat", "kick", "centroid"]
         if k in link["features"]]
W, RH = 1600, 70
im = Image.new("RGB", (W, RH * (len(names) + 1)), (12, 14, 22))
d = ImageDraw.Draw(im)
font = ImageFont.truetype("arial.ttf", 14)
n = link["n"]
cols = np.array_split(np.abs(x), W)
for i, c in enumerate(cols):
    h = float(c.max()) * (RH - 8) / 2 if len(c) else 0
    d.line((i, RH / 2 - h, i, RH / 2 + h), fill=(120, 130, 160))
d.text((6, 4), "waveform", font=font, fill=(230, 236, 250))
for r, nm in enumerate(names, start=1):
    v = np.asarray(link["features"][nm])
    y0 = r * RH
    pts = [(i * W / n, y0 + RH - 6 - v[i] * (RH - 12)) for i in range(n)]
    d.line(pts, fill=(166, 179, 210), width=2)
    d.text((6, y0 + 4), nm, font=font, fill=(230, 236, 250))
for f in link["hits"]:
    d.line((f * W / n, 0, f * W / n, 10), fill=(230, 80, 80), width=2)
for f in link["beats"]:
    d.line((f * W / n, RH - 10, f * W / n, RH), fill=(90, 140, 255), width=2)
im.save(a[2])
print("wrote", a[2])
