"""Develop Beat, the one command: a music file in, everything an editor needs for it out.

usage: python -I beat.py <music file> [--out <folder>] [--fps 24] [--music-start 0] [--start 0] [--dur 0]
       [--meter 4] [--fast] [--reactions all|none|Glow,Punch In,...] [--drive "<effect.dctl>|<slider>[|<source>]"]
       [--visualizer line,ring,wave] [--vis-size 1920x1080] [--vis-color 230,236,250]

It writes, in --out (default: a folder named after the song next to this script's out/ folder):
  <song>.music.json                  the analysis (beats, downbeats, hits, low hits, band energies), for the renderers'
                                     --link and for a look at it with plot.py
  Develop Beat <Reaction> - <song>.dctl   one per reaction, the song baked in, the reaction's own defaults
  <Effect> Beat - <song>.dctl        for each --drive: that effect with the slider on the beat (drive.py)
  Develop Visualizer <Style> - <song>.mov  for each --visualizer style: ProRes 4444 with alpha, the song's length,
                                     for a track above the picture (visualizer.py)
In Resolve: copy the .dctl files to the LUT folder (or a subfolder), refresh the LUT list, put one on a clip or an
adjustment clip as an OpenFX DCTL effect, set Music Start to where the song starts on the timeline (in seconds from
the timeline's first frame) and Timeline FPS to the timeline's rate.
--fps is only the default written into Timeline FPS; the tables are in seconds. --start and --dur bake a part of the
file (its first second then sits at Music Start). MIT License.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "audio", "link"))
import bake
import music

def main():
    a = sys.argv[1:]
    if not a or a[0].startswith("--"):
        print(__doc__)
        sys.exit(1)
    arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    path = a[0]
    song = bake.song_name(path)
    out = arg("--out", os.path.join(HERE, "out", song))
    os.makedirs(out, exist_ok=True)
    fps = float(arg("--fps", 24))
    mstart = float(arg("--music-start", 0))
    t0 = time.time()
    y = music.load(path, float(arg("--start", 0)), float(arg("--dur", 0)))
    m = music.analyse(y, meter=int(arg("--meter", 4)), fast="--fast" in a)
    t_an = time.time() - t0
    jpath = os.path.join(out, f"{song}.music.json")
    json.dump(m, open(jpath, "w", encoding="utf-8"))
    packed = bake.pack(m)
    tmpl = open(os.path.join(HERE, "build", "Develop Beat.dctl"), encoding="utf-8").read()
    base = bake.put_data(tmpl, bake.data_block(packed, song))
    made = [jpath]
    sel = arg("--reactions", "all")
    names = list(bake.REACTIONS) if sel == "all" else [] if sel == "none" else [s.strip() for s in sel.split(",")]
    for nm in names:
        d = dict(bake.REACTIONS[nm])
        d.update({"btFps": fps, "btStart": mstart})
        p = os.path.join(out, f"Develop Beat {nm} - {song}.dctl")
        open(p, "w", encoding="utf-8", newline="\n").write(bake.set_defaults(base, d))
        made.append(p)
    for i, k in enumerate(a):
        if k != "--drive":
            continue
        import drive as drv
        import shape as shp
        parts = a[i + 1].split("|")
        eff, sliders = parts[0], parts[1].split(",")
        src = parts[2] if len(parts) > 2 else "beats"
        name = os.path.splitext(os.path.basename(eff))[0]
        p = os.path.join(out, f"{name} Beat - {song}.dctl")
        text = drv.drive(open(eff, encoding="utf-8").read(), sliders, packed, song,
                         {"btFps": fps, "btStart": mstart, "btSource": shp.SOURCES[src]})
        open(p, "w", encoding="utf-8", newline="\n").write(text)
        made.append(p)
    vis = arg("--visualizer", "")
    if vis:
        import visualizer as vz
        w, h = (int(v) for v in arg("--vis-size", "1920x1080").split("x"))
        for style in vis.split(","):
            p = os.path.join(out, f"Develop Visualizer {style.capitalize()} - {song}.mov")
            vz.render_parallel(path, p, style=style, w=w, h=h, fps=fps, start=float(arg("--start", 0)),
                               dur=float(arg("--dur", 0)), color=arg("--vis-color", None),
                               jobs=int(arg("--jobs", 8)))
            made.append(p)
    print(f"{m['duration']:.1f} s of music, tempo {m['tempo']:.1f}, {len(m['beats'])} beats, "
          f"{sum(1 for b in m['bar'] if b == 0)} downbeats, {len(m['hits'])} hits, {len(m['kicks'])} low hits; "
          f"analysis {t_an:.1f} s; tables {sum(packed['meta'][:4])} floats {packed['dropped']}")
    for p in made:
        print("  ", p)

if __name__ == "__main__":
    main()
