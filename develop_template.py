"""Build a Develop look as a node template for DaVinci Resolve: baked node DCTLs plus a grade file (.drx).

usage: python -I develop_template.py <outdir> <look name> [options] name=value [name=value ...]
options:
  --base <file.drx>   a one-node grade whose node carries a LUT; its container and node record are reused
                      (default: tools/base.drx, a neutral one)
  --lut-dir <name>    folder inside Resolve's LUT folder that will hold the look (default: Develop)
  --install           copy the baked DCTLs into <LUT root>/<lut-dir>/<look name>/. When that folder holds another build of
                      this look, the new build goes to "<look name> 2" (then 3, ...), so clips on the old build stay
  --lut-root <dir>    Resolve's LUT folder (default: the Windows ProgramData location)
  --frame <file>      a still of the shot; with bloomThr=auto the threshold is judged from it (tools/judge.py)
  --judge-base <n>    the look's own threshold that auto may only raise (default 45)
  --live <keys>       nodes to build as DCTL plugin nodes with their slider values in the grade, comma separated
                      (look, night, orton, linear, bright, L0 to L6, print, encode, sparkH, sparkV, stkBright, stkMid,
                      stkLong, vign, acute, grain, matte); a live node's sliders can be moved in Resolve and set per
                      shot by develop_apply.py. A live look is two plugin nodes in a row, Develop 1 Light then Develop
                      2 Color (keys light and color; naming either, or look, makes both live): a DCTL plugin node takes
                      at most 64 sliders and Develop.dctl has 67. Both are cut from Develop.dctl by
                      split_develop.py and together give its picture. A look that is not live stays one LUT node on
                      Develop.dctl.

Values go to whichever node declares the slider: Develop.dctl (the look node; live, Develop 1 Light or Develop 2
Color, and Highlight Rolloff and Deband to both, as both declare them), the Bloom nodes
(bloomAmt, bloomThr, bloomKnee, bloomFall, bloomWarm, bloomRoll) or Print (pr...). With bloomAmt above 0 the
template is

    input ── look ─┬─ Bloom Linear ───────────────────────────────┐
                   └─ Bloom Bright ── L0 ── L1 ── ... ── L6        │  every level also feeds the mixer
                                                   Layer Mixer (Add, eight inputs) ── [Print] ── Bloom Encode ── output

and without it, the look node alone, or with prAmt above 0, look ── Bloom Linear ── Print ── Bloom Encode. Print (film
negative and print, nodes/Develop Print.dctl) works on linear light, so the bloom reaches it whole. With ntAmt above
0, Night (day for night, nodes/Develop Night.dctl) follows the look node and everything after takes its picture; a
look-only grade carries it too. With ortAmt above 0, Orton (the dream glow, nodes/Develop Orton.dctl) ends the look
stage the same way, after Night. With stkAmt above 0 (Bloom on), the anamorphic streak (Streak Bright, Mid and Long,
three passes along the row) runs beside the bloom from the end of the look stage into one more mixer input. Then,
each only
when one of its switching sliders is on: Vignette (lvFocal or
lvOptical above 0, or lvCreative not 0; light falloff in linear light, nodes/Develop Vignette.dctl), Acutance
(acuAmt or acuFilm above 0;
sharpening, nodes/Develop Acutance.dctl), Film Grain (filmGrain, a plugin node), Matte (matAspect; letterbox bars,
last of all). Apply the .drx with Graph.ApplyGradeFromDRX(path, 0) after Project.RefreshLUTList(), called twice
(a plugin node whose file changed its slider list keeps the old layout after one; resolve_live.refresh_luts).

As a library (develop_apply.py): Look(name, values) bakes the nodes once; Look.grade(path, shot) writes a grade
whose live nodes carry the shot's slider values, so a value set per shot needs no new DCTL file.
"""
import glob
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from template import Grade  # noqa: E402

PAT = re.compile(r"(DEFINE_UI_PARAMS\(\s*(\w+)\s*,[^,]+,\s*DCTLUI_SLIDER_FLOAT\s*,\s*)([-0-9.]+)(\s*,)")
UI = re.compile(r"DEFINE_UI_PARAMS\(\s*(\w+)\s*,[^,]+,\s*(DCTLUI_\w+)")
NODES = {
    "look": "Develop.dctl",
    # the look as DCTL plugin nodes: one plugin node takes at most 64 sliders, Develop.dctl has 67
    "light": "Develop 1 Light.dctl",
    "color": "Develop 2 Color.dctl",
    "linear": os.path.join("nodes", "Develop Bloom Linear.dctl"),
    "bright": os.path.join("nodes", "Develop Bloom Bright.dctl"),
    "level": os.path.join("nodes", "Develop Bloom Level.dctl"),
    "encode": os.path.join("nodes", "Develop Bloom Encode.dctl"),
    "print": os.path.join("nodes", "Develop Print.dctl"),
    "night": os.path.join("nodes", "Develop Night.dctl"),
    "orton": os.path.join("nodes", "Develop Orton.dctl"),
    "stkBright": os.path.join("nodes", "Develop Streak Bright.dctl"),
    "stkMid": os.path.join("nodes", "Develop Streak Mid.dctl"),
    "stkLong": os.path.join("nodes", "Develop Streak Long.dctl"),
    "sparkH": os.path.join("nodes", "Develop Bloom Sparkle H.dctl"),
    "sparkV": os.path.join("nodes", "Develop Bloom Sparkle V.dctl"),
    "grain": os.path.join("nodes", "Develop Grain.dctl"),
    "vign": os.path.join("nodes", "Develop Vignette.dctl"),
    "acute": os.path.join("nodes", "Develop Acutance.dctl"),
    "matte": os.path.join("nodes", "Develop Matte.dctl"),
}
DEFAULTS = {"base": os.path.join(HERE, "tools", "base.drx"), "lut-dir": "Develop",
            "lut-root": r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT"}


def args():
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    opts = dict(DEFAULTS, install=False)
    rest = []
    i = 2
    known = {"base", "lut-dir", "lut-root", "frame", "judge-base", "live"}
    while i < len(a):
        if a[i] == "--install":
            opts["install"] = True
        elif a[i].startswith("--"):
            if a[i][2:] not in known:
                sys.exit(f"unknown option {a[i]} (known: --install, --" + ", --".join(sorted(known)) + ")")
            if i + 1 >= len(a):
                sys.exit(f"{a[i]} needs a value")
            opts[a[i][2:]] = a[i + 1]
            i += 1
        else:
            rest.append(a[i])
        i += 1
    return a[0], a[1], opts, dict(r.split("=", 1) for r in rest)


def bake(src, values, used):
    def repl(m):
        var = m.group(2)
        if var not in values:
            return m.group(0)
        used.add(var)
        return f"{m.group(1)}{float(values[var])}{m.group(4)}"
    return PAT.sub(repl, src)


def sliders(text):
    """The node's float sliders in DEFINE_UI_PARAMS order, as (name, baked value); the plugin counts them from 0."""
    kinds = {m.group(1): m.group(2) for m in UI.finditer(text)}
    other = [k for k, v in kinds.items() if v != "DCTLUI_SLIDER_FLOAT"]
    if other:
        raise ValueError("a live node with non-float controls (" + ", ".join(other) + ") is not supported")
    found = [(m.group(2), float(m.group(3))) for m in PAT.finditer(text)]
    if len(found) != len(kinds):
        # a default the pattern cannot read (1e-3, 1.0f) would shift every later slider's index without a word
        raise ValueError("a float slider's default is written in a form the builder cannot read: "
                         + ", ".join(sorted(set(kinds) - {v for v, _ in found})))
    return found


class LookError(Exception):
    pass


class Effect:
    """An installed effect carried by a look: a DCTL plugin node after the grade, with its slider values in the grade."""

    def __init__(self, spec, opts):
        name = spec.get("effect", "")
        hits = glob.glob(os.path.join(glob.escape(HERE), "effects", "*", "build", glob.escape(name) + ".dctl"))
        if not name or not hits:
            raise LookError(f"no effect named {name!r}: effects are the files in effects/<family>/build/, without .dctl")
        self.path = hits[0]
        self.name = name
        family = os.path.basename(os.path.dirname(os.path.dirname(self.path))).capitalize()
        self.lut = f"{opts['lut-dir']}\\{family}\\{name}.dctl"
        installed = os.path.join(opts["lut-root"], opts["lut-dir"], family, name + ".dctl")
        if not os.path.isfile(installed):
            raise LookError(f"{name} is not installed in Resolve's LUT folder: run Install.bat")
        text = open(self.path, encoding="utf-8").read()
        if re.search(r"__DEVICE__\s+float[34]\s+transition\s*\(", text):
            raise LookError(f"{name} is a transition, which goes on a cut: a look cannot carry it, so drag it onto the cut by hand")
        self.sliders = sliders(text)
        # a value lands by its slider's position, so the installed file must have the same sliders as this folder's
        if sliders(open(installed, encoding="utf-8").read()) != self.sliders:
            raise LookError(f"the installed {name} differs from this folder's: run Install.bat again")
        known = {v for v, _ in self.sliders}
        self.values = {k: float(v) for k, v in spec.get("values", {}).items()}
        unknown = set(self.values) - known
        if unknown:
            raise LookError(f"{name} has no slider " + ", ".join(sorted(unknown)) + ". It has: " + ", ".join(sorted(known)))

    def params(self):
        return [("DCTLs", "str", self.lut)] + [(f"sliderFloatParam{n}", "f64", self.values.get(var, val))
                                               for n, (var, val) in enumerate(self.sliders)]


class Look:
    """A look baked once: its node texts, which nodes are live, the effects it carries, and the grade writer."""

    def __init__(self, name, values, live=(), opts=None, effects=()):
        if not re.fullmatch(r"[A-Za-z0-9 _-]+", name):
            raise LookError("look name: letters, digits, spaces, _ and - only")
        self.name, self.values = name, dict(values)
        self.opts = dict(DEFAULTS, **(opts or {}))
        self.effects = [Effect(spec, self.opts) for spec in effects]
        self.bloom = float(self.values.get("bloomAmt", 0)) > 0
        wants_spark = float(self.values.get("bloomSpark", 0)) > 0 or float(self.values.get("bloomVeil", 0)) > 0
        if wants_spark and not self.bloom:
            raise LookError("Bloom Sparkle and Bloom Veil ride on Bloom: set bloomAmt above 0")
        self.spark = self.bloom and wants_spark
        self.streak = float(self.values.get("stkAmt", 0)) > 0
        if self.streak and not self.bloom:
            raise LookError("Streak adds into the Bloom mixer: set bloomAmt above 0")
        self.grain = float(self.values.get("filmGrain", 0)) > 0
        self.vign = (float(self.values.get("lvFocal", 0)) > 0 or float(self.values.get("lvOptical", 0)) > 0
                     or float(self.values.get("lvCreative", 0)) != 0)
        self.acute = float(self.values.get("acuAmt", 0)) > 0 or float(self.values.get("acuFilm", 0)) > 0
        self.matte = float(self.values.get("matAspect", 0)) > 0
        self.print = float(self.values.get("prAmt", 0)) > 0
        self.night = float(self.values.get("ntAmt", 0)) > 0
        live = set(live)
        # a live look: Develop 1 Light then Develop 2 Color as two plugin nodes; otherwise one LUT node on Develop.dctl
        self.split = bool(live & {"look", "light", "color"})
        if self.split:
            live = (live - {"look"}) | {"light", "color"}
            plan = [("light", "light", {}), ("color", "color", {})]
        else:
            plan = [("look", "look", {})]
        if self.night:
            # day for night right after the look, so the night picture is what blooms and prints
            plan += [("night", "night", {})]
        self.orton = float(self.values.get("ortAmt", 0)) > 0
        if self.orton:
            # the Orton dream glow ends the look stage (after Night), so the dream picture blooms and prints too
            plan += [("orton", "orton", {})]
        if self.bloom:
            plan += [("linear", "linear", {}), ("bright", "bright", {})]
            plan += [(f"L{k}", "level", {"level": str(k)}) for k in range(7)]
            if self.print:
                plan += [("print", "print", {})]
            plan += [("encode", "encode", {})]
        elif self.print:
            # Print works on linear light: Bloom Linear before it, Bloom Encode after it
            plan += [("linear", "linear", {}), ("print", "print", {}), ("encode", "encode", {})]
        if self.spark:
            plan += [("sparkH", "sparkH", {}), ("sparkV", "sparkV", {})]
        if self.streak:
            plan += [("stkBright", "stkBright", {}), ("stkMid", "stkMid", {}), ("stkLong", "stkLong", {})]
        if self.vign:
            plan += [("vign", "vign", {})]
        if self.acute:
            plan += [("acute", "acute", {})]
        if self.grain:
            plan += [("grain", "grain", {})]
        if self.matte:
            plan += [("matte", "matte", {})]
        # bake in memory and check every value lands somewhere BEFORE anything on disk is touched
        used = set()
        self.baked = {key: bake(open(os.path.join(HERE, NODES[node]), encoding="utf-8").read(),
                                dict(self.values, **force), used)
                      for key, node, force in plan}
        excused = set()
        if not self.bloom:
            excused |= {k for k in self.values if k.startswith("bloom")}
        elif not self.spark:
            excused |= {"bloomSpr", "bloomSpark", "bloomVeil"} & set(self.values)
        if not self.grain:
            excused |= {k for k in self.values if k.startswith("film")}
        if not self.vign:
            excused |= {k for k in self.values if k.startswith("lv")}
        if not self.acute:
            excused |= {k for k in self.values if k.startswith("acu")}
        if not self.matte:
            excused |= {k for k in self.values if k.startswith("mat")}
        if not self.print:
            excused |= {k for k in self.values if k.startswith("pr")}
        if not self.night:
            excused |= {k for k in self.values if k.startswith("nt")}
        if not self.orton:
            excused |= {k for k in self.values if k.startswith("ort")}
        if not self.streak:
            excused |= {k for k in self.values if k.startswith("stk")}
        unknown = set(self.values) - used - excused
        if unknown:
            raise LookError("no node declares: " + ", ".join(sorted(unknown)))
        self.live = live
        absent = self.live - set(self.baked)
        if absent:
            raise LookError("--live names nodes this look does not build: " + ", ".join(sorted(absent))
                            + " (it builds " + ", ".join(self.baked) + ")")
        self.sliders = {key: sliders(self.baked[key]) for key in self.live}
        self.files = {key: f"{name}_{key}.dctl" for key in self.baked}
        self.folder = self._free_folder()

    def _free_folder(self):
        """The look's folder in the LUT folder. A DCTL rewritten at the same path changes every clip that uses it, so a
        folder holding other text or other nodes is never touched: the look moves to "<name> 2", then 3. Running the
        same look again finds its own folder and writes nothing new."""
        mine = {self.files[k]: self.baked[k] for k in self.baked}
        n = 1
        while True:
            folder = self.name if n == 1 else f"{self.name} {n}"
            dest = os.path.join(self.opts["lut-root"], self.opts["lut-dir"], folder)
            if not os.path.isdir(dest):
                return folder
            conflict = False
            for f in os.listdir(dest):
                if not f.endswith(".dctl"):
                    continue
                if f not in mine or open(os.path.join(dest, f), encoding="utf-8", newline="").read() != mine[f]:
                    conflict = True
                    break
            if not conflict:
                return folder
            n += 1

    def lut(self, key):
        return f"{self.opts['lut-dir']}\\{self.folder}\\{self.files[key]}"

    def node_count(self):
        """Nodes in the whole grade: one per node file, one per effect, plus the Layer Mixer when Bloom is on."""
        return len(self.baked) + len(self.effects) + (1 if self.bloom else 0)

    def shot_vars(self):
        """Slider names a shot may set: those that only live nodes declare."""
        on_live = {v for key in self.live for v, _ in self.sliders[key]}
        on_baked = {m.group(2) for key in set(self.baked) - self.live for m in PAT.finditer(self.baked[key])}
        return on_live - on_baked

    def write_nodes(self, outdir):
        folder = os.path.join(outdir, self.name)
        os.makedirs(folder, exist_ok=True)
        for f in os.listdir(folder):              # a rebuilt look never keeps nodes from an earlier build
            if f.startswith(self.name + "_") and f.endswith(".dctl") or f == self.name + ".drx":
                os.remove(os.path.join(folder, f))
        for key, text in self.baked.items():
            open(os.path.join(folder, self.files[key]), "w", encoding="utf-8", newline="\n").write(text)
        return folder

    def install(self, folder):
        """Copy the nodes into the look's own folder (_free_folder). Nothing there is ever replaced or removed: clips
        may be using it."""
        dest = os.path.join(self.opts["lut-root"], self.opts["lut-dir"], self.folder)
        os.makedirs(dest, exist_ok=True)
        mine = set(self.files.values())
        written = 0
        for f in mine:
            src, dst = os.path.join(folder, f), os.path.join(dest, f)
            if os.path.exists(dst) and open(src, "rb").read() == open(dst, "rb").read():
                continue
            shutil.copy2(src, dest)
            written += 1
        self.installed = written
        return dest

    def grade(self, path, shot=None, look_only=False):
        """Write a grade. shot: slider values for this shot, allowed only on sliders that live nodes alone declare."""
        shot = dict(shot or {})
        stray = set(shot) - self.shot_vars()
        if stray:
            raise LookError("a shot can only set sliders on live nodes (and on no baked node): "
                            + ", ".join(sorted(stray)))
        bloom, spark, grain = (False, False, False) if look_only else (self.bloom, self.spark, self.grain)
        vign, acute, matte = (False, False, False) if look_only else (self.vign, self.acute, self.matte)
        prnt = False if look_only else self.print
        night = self.night                       # part of the look stage: a look-only grade carries it too
        g = Grade(self.opts["base"])

        def node(key, num, x, y):
            if key not in self.live:
                return g.corrector(num, x, y, self.lut(key))
            params = [("DCTLs", "str", self.lut(key))]
            params += [(f"sliderFloatParam{n}", "f64", float(shot.get(var, val)))
                       for n, (var, val) in enumerate(self.sliders[key])]
            return g.dctl_plugin(num, x, y, params)

        if self.split:
            # Develop 1 Light then Develop 2 Color: together Develop.dctl's picture
            light = node("light", 1, 190, 180)
            g.feed(light)
            look = node("color", 25, 190, 320)
            g.link(light, look)
        else:
            look = node("look", 1, 190, 180)
            g.feed(look)
        if night:
            nn = node("night", 20, 310, 180)
            g.link(look, nn)
            look = nn                            # everything after the look stage takes the night picture
        if self.orton:                           # part of the look stage too: a look-only grade carries it
            on = node("orton", 21, 310, 320)
            g.link(look, on)
            look = on
        if bloom:
            lin = node("linear", 2, 430, 60)
            bri = node("bright", 3, 430, 320)
            lv = [node(f"L{k}", 4 + k, 660 + 220 * k, 320) for k in range(7)]
            mx = g.layer_mixer(11, 2240, 180, "add")
            if prnt:
                pn = node("print", 19, 2480, 180)
                enc = node("encode", 12, 2720, 180)
            else:
                enc = node("encode", 12, 2480, 180)
            g.link(look, lin)
            g.link(look, bri)
            g.link(bri, lv[0])
            for a, b in zip(lv, lv[1:]):
                g.link(a, b)
            g.link(lin, mx, 0)
            first = 1
            if spark:
                sh = node("sparkH", 13, 430, 190)
                sv = node("sparkV", 14, 660, 190)
                g.link(look, sh)
                g.link(sh, sv)
                g.link(sv, mx, 1)
                first = 2
            for k, n in enumerate(lv):
                g.link(n, mx, first + k)
            if self.streak:                      # the anamorphic streak: three passes along the row, into the mixer
                sb = node("stkBright", 22, 430, 450)
                sm = node("stkMid", 23, 660, 450)
                sl = node("stkLong", 24, 890, 450)
                g.link(look, sb)
                g.link(sb, sm)
                g.link(sm, sl)
                g.link(sl, mx, first + len(lv))
            if prnt:
                g.link(mx, pn)
                g.link(pn, enc)
            else:
                g.link(mx, enc)
            last = enc
            x = 2960 if prnt else 2720
        elif prnt:
            lin = node("linear", 2, 430, 180)
            pn = node("print", 19, 670, 180)
            enc = node("encode", 12, 910, 180)
            g.link(look, lin)
            g.link(lin, pn)
            g.link(pn, enc)
            last, x = enc, 1150
        else:
            last, x = look, 2720
        if vign:
            vn = node("vign", 18, x, 180)
            g.link(last, vn)
            last, x = vn, x + 240
        if acute:
            an = node("acute", 16, x, 180)
            g.link(last, an)
            last, x = an, x + 240
        if not look_only:                        # the effects the look carries, after the grade, under the grain and bars
            for k, fx in enumerate(self.effects):
                fn = g.dctl_plugin(30 + k, x, 180, fx.params())
                g.link(last, fn)
                last, x = fn, x + 240
        if grain:
            # a DCTL plugin node, so TIMELINE_FRAME_INDEX is live and the grain moves; its sliders start at the
            # baked defaults. DCTLs names a file that validated (a plugin node without one can stop the API).
            if "grain" in self.live:
                gn = node("grain", 15, x, 180)
            else:
                gn = g.dctl_plugin(15, x, 180, [("DCTLs", "str", self.lut("grain"))])
            g.link(last, gn)
            last, x = gn, x + 240
        if matte:
            # last of all, after grain, so the bars stay a clean level
            mn = node("matte", 17, x, 180)
            g.link(last, mn)
            last = mn
        g.out(last)
        return g.write(path)


def main():
    outdir, name, opts, values = args()
    if values.get("bloomThr") == "auto":
        # shot judge, first rule: keep the base threshold, raised until at most 30% of the frame blooms
        if "frame" not in opts:
            sys.exit("bloomThr=auto needs --frame <still exported from Resolve, or a .rgb48 frame>")
        from judge import auto_threshold
        thr, share = auto_threshold(opts["frame"], float(opts.get("judge-base", 45)))
        values["bloomThr"] = str(thr)
        print(f"judged Bloom Threshold {thr:.1f} ({share * 100:.1f}% of the frame was above {opts.get('judge-base', 45)})")
    live = [k for k in opts.get("live", "").split(",") if k]
    from drxlib import check_node
    check_node()                                 # the grade file needs it
    try:
        look = Look(name, values, live, {k: opts[k] for k in ("base", "lut-dir", "lut-root")})
    except (LookError, ValueError) as e:
        sys.exit(str(e))
    folder = look.write_nodes(outdir)
    drx = look.grade(os.path.join(folder, f"{name}.drx"))
    print(f"wrote {len(look.files)} node DCTLs and {drx}")
    if opts["install"]:
        dest = look.install(folder)
        print(f"installed into {dest}; in Resolve run Project.RefreshLUTList() twice, then ApplyGradeFromDRX")


if __name__ == "__main__":
    main()
