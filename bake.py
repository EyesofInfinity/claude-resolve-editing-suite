"""Write a copy of Develop.dctl whose slider defaults are set to given values: applied as a LUT, it is a fixed look.
usage: python bake.py <out.dctl> name=value [name=value ...]      (names are the variable names in Develop.dctl)
"""
import os, re, sys

here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "Develop.dctl"), encoding="utf-8").read()
out, pairs = sys.argv[1], dict(a.split("=", 1) for a in sys.argv[2:])
done = set()


def repl(m):
    var = m.group(2)
    if var not in pairs:
        return m.group(0)
    done.add(var)
    return f"{m.group(1)}{float(pairs[var])}{m.group(4)}"


# DEFINE_UI_PARAMS(var, Label, DCTLUI_SLIDER_FLOAT, default, min, max, step)
pat = re.compile(r"(DEFINE_UI_PARAMS\(\s*(\w+)\s*,[^,]+,\s*DCTLUI_SLIDER_FLOAT\s*,\s*)([-0-9.]+)(\s*,)")
baked = pat.sub(repl, src)
missing = set(pairs) - done
if missing:
    sys.exit("unknown slider(s): " + ", ".join(sorted(missing)))
open(out, "w", encoding="utf-8").write(baked)
print("baked", out, {k: pairs[k] for k in sorted(pairs)})
