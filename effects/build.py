"""Build Develop effects: every <name>.src.dctl in an effect folder with each #include "<path>" written in
(the path relative to the source), so every installed .dctl stands alone (Resolve's DCTL list shows .dctl files
only, and a moved file keeps working).

usage: python -I build.py <folder> [--install]
writes <folder>/build/<name>.dctl; --install also copies them to the LUT folder's Develop\\<Folder> (refresh the
LUT list in Resolve after).
"""
import glob, os, re, shutil, sys

LUT = r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT\Develop"

def inline(path, seen):
    t = open(path, encoding="utf-8").read()

    def sub(m):
        inc = os.path.normpath(os.path.join(os.path.dirname(path), m.group(1)))
        if inc in seen:
            return ""
        seen.add(inc)
        return inline(inc, seen)
    return re.sub(r'#include "([^"]+)"\n', sub, t)

def build(folder):
    out = os.path.join(folder, "build")
    os.makedirs(out, exist_ok=True)
    made = []
    for src in sorted(glob.glob(os.path.join(glob.escape(folder), "*.src.dctl"))):
        t = inline(src, set())
        if "#include" in t:
            sys.exit(f"{src}: an #include was left unresolved")
        dst = os.path.join(out, os.path.basename(src).replace(".src.dctl", ".dctl"))
        open(dst, "w", encoding="utf-8", newline="\n").write(t)
        made.append(dst)
    return made

if __name__ == "__main__":
    folder = os.path.abspath(sys.argv[1])
    made = build(folder)
    for m in made:
        print(m)
    if "--install" in sys.argv:
        dest = os.path.join(LUT, os.path.basename(folder).capitalize())
        os.makedirs(dest, exist_ok=True)
        for m in made:
            shutil.copy2(m, dest)
        print("installed to", dest)
