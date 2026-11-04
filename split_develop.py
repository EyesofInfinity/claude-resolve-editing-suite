"""Write Develop.dctl as two DCTL plugin nodes, Develop 1 Light.dctl and Develop 2 Color.dctl, cut from it.

A ResolveFX DCTL plugin node takes at most 64 sliders (tests/cpu/slider_limit.mjs) and Develop.dctl has 67, so
as plugin nodes Develop runs as two nodes in a row. Develop.dctl stays the one source and the one file for LUT use
(bake.py); the two node files are cut from it here and are never edited by hand.

The cut follows Develop's own processing order. Everything that reads neighbouring pixels (deband, highlight recovery,
the clip-edge feather, texture, clarity, structure, mist, veil, sparkle, halation) works on the input picture, so it
all stays in node 1, together with white balance and exposure (their matrix also acts on every tap) and the tone
sliders. Node 1 ends where Develop has turned back to display values and applied the tone (Contrast to Blacks).
From there on Develop works pixel by pixel on display values, so node 2 takes up the same r, g, b and runs the rest:
split toning, colour contrast, the colour mixer, density, vibrance, saturation, vignette, the highlight shoulder,
path to white, gamut compression, black floor, grain and the deband dither. The signal between the two is Rec.709
gamma 2.4 display values, unclipped: no working space is encoded at the cut.

Develop.dctl clips its output to 0 to 1 once any slider moves and hands the input back untouched when none does.
Node 2 cannot see node 1's sliders, so it clips always, also at neutral: a look made on node 1 alone then reaches the next node clipped as Develop.dctl's would, and the only difference left is with all 67 sliders
at neutral, where the pair clips values outside 0 to 1 that Develop.dctl hands back.

Two sliders act on both sides of the cut: Highlight Rolloff (the clip-edge feather in node 1, the shoulder in node 2)
and Deband (the smoothing in node 1, the dither in node 2). Both nodes declare them; set the same value on each.
develop_template.py does that by itself, as it sends every value to every node that declares it.

usage: python -I split_develop.py            write the two files next to Develop.dctl
       python -I split_develop.py --check    exit 1 when the files on disk differ from a fresh cut (drift)
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "Develop.dctl")
NODE1 = "Develop 1 Light.dctl"
NODE2 = "Develop 2 Color.dctl"
LIMIT = 64
HELPERS = "// ------------------------------------------------------------------ helpers"
MAIN = "// ------------------------------------------------------------------ main"
CUT = "    // ---- split toning and color contrast, in Oklab"
CARRY = ("aRoll", "dbT")      # values node 2 needs from before the cut; each is a slider over a constant
PARAM = re.compile(r"^DEFINE_UI_PARAMS\(\s*(\w+)\s*,\s*([^,]+?)\s*,")
TIP = re.compile(r'^DEFINE_UI_TOOLTIP\(\s*([^,]+?)\s*,\s*"([^"]*)"\)')
WORD = re.compile(r"\b[A-Za-z_]\w*\b")
DECL = re.compile(r"\b(?:const\s+)?(?:float[234]?|int|uint)\s+([^;{}]*?)(?:;|\)\s*\{)")
BOTH = {
    "Highlight Rolloff": "Also on Develop {other}: set the same value on both. Here it {here}",
    "Deband": "Also on Develop {other}: set the same value on both. Here it {here}",
}
HERE_DOES = {
    ("Highlight Rolloff", 1): "softens the rim of sources that were already clipped",
    ("Highlight Rolloff", 2): "eases highlights into white instead of a hard clip",
    ("Deband", 1): "smooths contour steps in gradients such as night skies",
    ("Deband", 2): "dithers the output",
}
KEYWORDS = {"if", "else", "for", "return", "float", "float2", "float3", "float4", "int", "uint", "const", "while"}


class SplitError(Exception):
    pass


def strip_comments(t):
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*[\s\S]*?\*/", "", t))


def words(t):
    return set(WORD.findall(re.sub(r"\.\s*[A-Za-z_]\w*", "", strip_comments(t))))


def declared(t):
    names = set()
    for m in DECL.finditer(strip_comments(t)):
        depth, cur, parts = 0, "", []
        for ch in m.group(1):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        parts.append(cur)
        for p in parts:
            nm = re.match(r"\s*([A-Za-z_]\w*)", p)
            if nm:
                names.add(nm.group(1))
    return names


def helper_items(text):
    """The helpers section as items in file order: (name or None, text with the comments above it)."""
    items, pending, lines, i = [], [], text.split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"__(DEVICE|CONSTANT)__\s+\w+\s+(\w+)\s*[(\[]", ln)
        if not m:
            pending.append(ln)
            i += 1
            continue
        block, depth, opened = [], 0, False
        while True:
            cur = lines[i]
            block.append(cur)
            depth += cur.count("{") - cur.count("}")
            opened = opened or "{" in cur
            i += 1
            if opened and depth == 0:
                break
            if i >= len(lines):
                raise SplitError(f"helper {m.group(2)} never closes")
        items.append((m.group(2), "\n".join(pending + block)))
        pending = []
    if pending:
        items.append((None, "\n".join(pending)))
    return items


def prune(items, main_text):
    """Keep the helpers the main function reaches, directly or through other helpers, in file order."""
    names = {n for n, _ in items if n}
    body = {n: t for n, t in items if n}
    need, todo = set(), list(words(main_text) & names)
    while todo:
        n = todo.pop()
        if n in need:
            continue
        need.add(n)
        todo += list((words(body[n]) & names) - need - {n})
    out = [t for n, t in items if n in need]
    return "\n".join(out).strip("\n")


def split(src):
    lines = src.split("\n")
    version = re.match(r"// (Develop [0-9.]+):", lines[0])
    if not version:
        raise SplitError("Develop.dctl's first line no longer names its version")
    version = version.group(1)
    for marker in (HELPERS, MAIN, CUT):
        if src.count(marker) != 1:
            raise SplitError(f"marker found {src.count(marker)} times (wants 1): {marker.strip()}")
    h0, m0 = src.index(HELPERS), src.index(MAIN)
    ui_text, helpers, main = src[:h0], src[h0 + len(HELPERS):m0].strip("\n"), src[m0 + len(MAIN):].strip("\n")
    if not main.endswith("}"):
        raise SplitError("the main function is not the last thing in Develop.dctl")
    sig_end = main.index("{") + 1
    sig, body = main[:sig_end], main[sig_end:main.rindex("}")]
    am = re.search(r"\n    float active = [^;]*;\n", body)
    if not am:
        raise SplitError("the 'every effect at neutral' sum was not found")
    active_names = words(am.group(0)) - KEYWORDS - {"active", "_fabs"}
    first, second = body.split(CUT)
    first_used = first[:am.start()] + first[am.end():]

    # the sliders, with their lines, labels and tooltips
    params, tips, sections = [], {}, []
    for ln in ui_text.split("\n"):
        m, t = PARAM.match(ln), TIP.match(ln)
        if m:
            params.append((m.group(1), m.group(2), ln))
            sections[-1][1].append(m.group(1))
        elif t:
            tips[t.group(1)] = (ln, t.group(2))
        elif ln.startswith("// ----"):
            sections.append((ln, []))
    sliders = [p[0] for p in params]
    label = {v: lb for v, lb, _ in params}
    # what node 2 needs from before the cut: r, g, b, and the CARRY values, nothing else
    helper_names = {n for n, _ in helper_items(helpers) if n}
    params_main = {"p_Width", "p_Height", "p_X", "p_Y", "p_TexR", "p_TexG", "p_TexB"}
    free = {w for w in words(second) - declared(second) - KEYWORDS - set(sliders) - helper_names - params_main
            if not w.startswith("_") and not w.startswith("make_") and w != "TIMELINE_FRAME_INDEX"}
    extra = free - {"r", "g", "b"} - set(CARRY)
    if extra:
        raise SplitError("node 2 would read values made before the cut that are not carried: " + ", ".join(sorted(extra)))
    carry_lines = []
    for v in CARRY:
        if v not in free:
            continue
        cm = re.search(rf"\n(    float {v}\s*=\s*([^;,]*);)[^\n]*\n", first)
        if not cm or (words(cm.group(2)) - set(sliders)):
            raise SplitError(f"{v} is no longer one line made from sliders alone, so node 2 cannot remake it")
        carry_lines.append(cm.group(1))

    in1 = [v for v in sliders if re.search(rf"\b{v}\b", strip_comments(first_used))]
    in2 = [v for v in sliders if re.search(rf"\b{v}\b", strip_comments(second + "\n".join(carry_lines)))]
    lost = [v for v in sliders if v not in in1 and v not in in2]
    if lost:
        raise SplitError("sliders neither node reads: " + ", ".join(lost))
    for name, used in ((NODE1, in1), (NODE2, in2)):
        if len(used) > LIMIT:
            raise SplitError(f"{name} would declare {len(used)} sliders; a DCTL plugin node takes {LIMIT}")
    shared = [v for v in in1 if v in in2]

    def ui_for(used, node, other):
        out = []
        for head, vs in sections:
            mine = [v for v in vs if v in used]
            if not mine:
                continue
            if out:
                out.append("")
            out.append(head)
            out += [ln for v, _, ln in params if v in mine]
        out.append("")
        for v in used:
            lb = label[v]
            if v in shared:
                say = BOTH[lb].format(other=other, here=HERE_DOES[(lb, node)])
                out.append(f'DEFINE_UI_TOOLTIP({lb}, "{say}")')
            elif lb in tips:
                out.append(tips[lb][0])
        return "\n".join(out)

    def active_for(used):
        names = [v for v in sliders if v in active_names and v in used]
        rows, cur = [], "    float active = " + f"_fabs({names[0]})"
        for v in names[1:]:
            t = f"_fabs({v})"
            if len(cur) + 3 + len(t) > 118:
                rows.append(cur)
                cur = "                 + " + t
            else:
                cur += " + " + t
        rows.append(cur + ";")
        return "\n".join(rows) + "\n"

    shared_txt = " and ".join(label[v] for v in shared)
    head_common = (
        f"// Signal between the two nodes: Rec.709 gamma 2.4 display values, unclipped (values above 1 keep their headroom).\n"
        f"// Develop 2 Color always clips its output to 0 to 1, as Develop.dctl does once any slider moves; with every\n"
        f"// slider of both nodes at neutral the pair returns values inside 0 to 1 exactly and clips the rest.\n"
        f"// {shared_txt} act on both sides of the cut: both nodes declare them; set the same value on each.\n"
        f"// Generated by split_develop.py from Develop.dctl: edit Develop.dctl and run python -I split_develop.py, never\n"
        f"// this file. Applied as a LUT, use Develop.dctl itself. MIT License.\n"
        f"//\n")
    head1 = (
        f"// {version}, node 1 of 2 for DCTL plugin nodes: white balance, exposure, tone, detail, highlight recovery,\n"
        f"// mist, veil, sparkle, halation and deband. Follow it with Develop 2 Color; together they give Develop.dctl's\n"
        f"// picture. A ResolveFX DCTL plugin node takes at most 64 sliders and Develop.dctl has {len(sliders)}, so as plugin\n"
        f"// nodes it runs as these two, cut where Develop's own processing turns from neighbourhood work to single pixels.\n"
        + head_common +
        "// Sampling: highlight recovery, deband, mist, sparkle, halation and the three detail bands share one fixed pattern\n"
        "// of 144 taps in five rings out to 4.1% of the frame height, plus the centre pixel (see Develop.dctl).\n"
        "// White balance adapts in the CAT16 cone space of CIECAM16, with the Planckian locus from Krystek's approximation\n"
        "// (1985).\n")
    head2 = (
        f"// {version}, node 2 of 2 for DCTL plugin nodes: split toning, colour contrast, the colour mixer and skin, density,\n"
        f"// vibrance, saturation, vignette, highlight shoulder, path to white, gamut compression, black floor and grain.\n"
        f"// It follows Develop 1 Light and takes its picture; together they give Develop.dctl's picture. A ResolveFX DCTL\n"
        f"// plugin node takes at most 64 sliders and Develop.dctl has {len(sliders)}, so as plugin nodes it runs as these two.\n"
        + head_common +
        "// Gamut compression follows the ACES Reference Gamut Compression specification (CC BY 4.0). The Oklab matrices\n"
        "// are the published Oklab reference values. Grain and the deband dither are hashed from the frame index, so they\n"
        "// move in the plugin.\n")

    body1 = first.replace(am.group(0), "\n" + active_for(in1), 1).rstrip() + "\n\n" \
        + "    // the picture handed to Develop 2 Color: display values, unclipped\n" \
        + "    return make_float3(r, g, b);\n"
    read = re.match(r"\n(    float R = [^\n]*\n)", body)
    if not read:
        raise SplitError("the main function no longer opens by reading R, G and B")
    body2 = ("\n" + read.group(1) + "\n"
             + "    // every effect of this node at neutral: give back the input, clipped to 0 to 1. Develop.dctl clips its\n"
             + "    // output whenever any slider is moved, and this node cannot see Develop 1 Light's sliders, so it always\n"
             + "    // clips: a look made on Develop 1 Light alone then hands the next node what Develop.dctl would\n"
             + active_for(in2)
             + "    if (active == 0.0f) return make_float3(_saturatef(R), _saturatef(G), _saturatef(B));\n\n"
             + "    // the picture from Develop 1 Light: display values after the tone, unclipped\n"
             + "    float r = R, g = G, b = B;\n"
             + "".join(ln + "\n" for ln in carry_lines) + "\n"
             + CUT + second)

    def assemble(head, ui, main_body):
        main_text = sig + main_body + "}"
        return (head + "\n" + ui + "\n\n" + HELPERS + "\n\n" + prune(helper_items(helpers), main_text) + "\n\n"
                + MAIN + "\n\n" + main_text + "\n")

    out1 = assemble(head1, ui_for(in1, 1, "2 Color"), body1)
    out2 = assemble(head2, ui_for(in2, 2, "1 Light"), body2)
    info = {"sliders": len(sliders), NODE1: in1, NODE2: in2, "shared": shared, "carry": [v for v in CARRY if v in free]}
    return out1, out2, info


def main():
    src = open(SRC, encoding="utf-8").read()
    try:
        out1, out2, info = split(src)
    except SplitError as e:
        sys.exit(f"split_develop: {e}")
    files = {os.path.join(HERE, NODE1): out1, os.path.join(HERE, NODE2): out2}
    if "--check" in sys.argv[1:]:
        stale = [p for p, t in files.items()
                 if not os.path.exists(p) or open(p, encoding="utf-8").read() != t]   # a checkout may turn LF to CRLF
        for p in stale:
            print("out of date with Develop.dctl:", os.path.basename(p))
        if stale:
            sys.exit("run python -I split_develop.py")
        print("both node files match a fresh cut of Develop.dctl")
        return
    for p, t in files.items():
        open(p, "w", encoding="utf-8", newline="\n").write(t)
    print(f"Develop.dctl: {info['sliders']} sliders")
    print(f"{NODE1}: {len(info[NODE1])} sliders")
    print(f"{NODE2}: {len(info[NODE2])} sliders")
    print("on both:", ", ".join(info["shared"]), "| carried across the cut:", ", ".join(info["carry"]))


if __name__ == "__main__":
    main()
