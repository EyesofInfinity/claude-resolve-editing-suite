"""Fusion Fuses from Develop's built DCTLs.

A Fuse runs a DCTL-dialect kernel on the GPU through DVIPComputeNode. This generator carries a built
transform or Transition DCTL into a Fuse: the DCTL's text becomes the kernel's source under a fixed, invertible
mapping (README, section 2), every DEFINE_UI_PARAMS control becomes a Fusion input with the same id, name, default
and range, and a __KERNEL__ entry calls the DCTL's main function for every pixel. A Transition DCTL gets two image
inputs (Outgoing, Incoming) and a Progress input.

usage: python -I fusegen.py [--out DIR] [file.dctl ...]
With no files it generates every effects/*/build/*.dctl. Writes <out>/<DCTL name>.fuse (default effects/fusegen/out).
"""
import glob
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EFFECTS = os.path.dirname(HERE)

RENAMES = [
    ("_tex2D", "dvTex2D"),
    ("__TEXTURE__", "__TEXTURE2D__"),
    ("TIMELINE_FRAME_INDEX", "dvFrame"),
    ("TRANSITION_PROGRESS", "dvProgress"),
    ("half", "dvHalf"),
]
PROBES = []
MAIN = "dvMain"
EXTRA_PARAMS = "int dvFrame, float dvProgress"
RESERVED = ["dvTex2D", "__TEXTURE2D__", "dvFrame", "dvProgress", "dvMain", "dvSize", "dvFlipY", "dvSrc", "dvDst",
            "DvParams", "DevelopKernel"]
ENTRY_MARK = "// fusegen: the kernel entry"
UI_MARK = "// fusegen ui: "
TIP_MARK = "// fusegen tip: "

FUSION_IDS = {"Blend", "ProcessWhenBlendIs00", "ProcessRed", "ProcessGreen", "ProcessBlue", "ProcessAlpha",
              "ApplyMaskInverted", "MultiplyByMask", "FitMask", "MaskChannel", "MaskLow", "MaskHigh",
              "MaskClipBlack", "MaskClipWhite", "UseObject", "UseMaterial", "CorrectEdges", "ObjectID",
              "MaterialID", "Comments", "FrameRenderScript", "StartRenderScript", "EndRenderScript", "EffectMask",
              "Input", "Output", "Outgoing", "Incoming", "Progress", "FrameOffset", "HoldFrame", "FlipY",
              "Background", "Foreground", "MotionBlur", "Quality", "ShutterAngle", "CenterBias", "SampleSpread"}

NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?f?"
UI_RE = re.compile(r"^[ \t]*DEFINE_UI_PARAMS\((.*)\)[ \t]*$")
TIP_RE = re.compile(r'^[ \t]*DEFINE_UI_TOOLTIP\(\s*([^,]+?)\s*,\s*"((?:[^"\\]|\\.)*)"\s*\)[ \t]*$')
MAIN_RE = re.compile(r"__DEVICE__\s+(float[34])\s+(transform|transition)\s*\(([^)]*)\)")

class FuseGenError(Exception):
    pass

def split_top(s, sep=","):
    """Split on sep outside braces and brackets."""
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [x.strip() for x in out]

def num_text(t):
    """A DCTL number token as plain text for Lua and back (a trailing f dropped)."""
    t = t.strip()
    if not re.fullmatch(NUM, t):
        raise FuseGenError(f"not a number: {t!r}")
    return t[:-1] if t.endswith("f") else t

def parse_control(args):
    """One DEFINE_UI_PARAMS argument list: the six kinds of the DCTL README."""
    a = split_top(args)
    var, label, kind = a[0], a[1], a[2]
    if not re.fullmatch(r"[A-Za-z_]\w*", var):
        raise FuseGenError(f"bad control name {var!r}")
    c = {"var": var, "label": label, "kind": kind}
    if kind in ("DCTLUI_SLIDER_FLOAT", "DCTLUI_SLIDER_INT"):
        if len(a) != 7:
            raise FuseGenError(f"{var}: a slider takes default, min, max, step")
        c["default"], c["lo"], c["hi"], c["step"] = (num_text(x) for x in a[3:7])
        if not float(c["lo"]) <= float(c["default"]) <= float(c["hi"]):
            raise FuseGenError(f"{var}: default outside its range")
    elif kind in ("DCTLUI_VALUE_BOX", "DCTLUI_CHECK_BOX"):
        if len(a) != 4:
            raise FuseGenError(f"{var}: {kind} takes one default")
        c["default"] = num_text(a[3])
    elif kind == "DCTLUI_COMBO_BOX":
        if len(a) != 6 or not (a[4].startswith("{") and a[5].startswith("{")):
            raise FuseGenError(f"{var}: a combo takes a default, an enum list and a label list")
        c["default"] = num_text(a[3])
        c["enums"] = [x for x in split_top(a[4][1:-1]) if x]
        c["labels"] = [x for x in split_top(a[5][1:-1]) if x]
        if len(c["enums"]) != len(c["labels"]) or not c["enums"]:
            raise FuseGenError(f"{var}: enum and label lists differ in length")
        if not 0 <= int(float(c["default"])) < len(c["enums"]):
            raise FuseGenError(f"{var}: combo default outside its list")
    elif kind == "DCTLUI_COLOR_PICKER":
        if len(a) != 6:
            raise FuseGenError(f"{var}: a colour picker takes three defaults")
        c["rgb"] = [num_text(x) for x in a[3:6]]
    else:
        raise FuseGenError(f"{var}: unknown control kind {kind}")
    return c

def ctype(c):
    """The C type the DCTL gives the control inside its main function."""
    return {"DCTLUI_SLIDER_FLOAT": "float", "DCTLUI_VALUE_BOX": "float", "DCTLUI_SLIDER_INT": "int",
            "DCTLUI_CHECK_BOX": "int", "DCTLUI_COMBO_BOX": "int", "DCTLUI_COLOR_PICKER": "float3"}[c["kind"]]

def strip_comments(t):
    return re.sub(r"/\*[\s\S]*?\*/|//[^\n]*", "", t)

def parse_dctl(path):
    text = open(path, encoding="utf-8").read()
    if "\r" in text:
        raise FuseGenError("carriage returns in the file")
    lines = text.split("\n")
    controls, tips = [], []
    for i, ln in enumerate(lines):
        if "DEFINE_UI" not in ln:
            continue
        m, t = UI_RE.match(ln), TIP_RE.match(ln)
        if m and not ln.lstrip().startswith("//"):
            c = parse_control(m.group(1))
            c["line"] = i
            controls.append(c)
        elif t:
            tips.append({"label": t.group(1).strip(), "text": t.group(2), "line": i})
        elif ln.lstrip().startswith("//"):
            continue
        else:
            raise FuseGenError(f"line {i + 1}: a DEFINE_UI line this generator cannot read: {ln.strip()[:80]}")
    names = [c["var"] for c in controls]
    if len(set(names)) != len(names):
        raise FuseGenError("two controls share a name")
    for c in controls:
        if c["var"] in FUSION_IDS:
            raise FuseGenError(f"control {c['var']} takes a Fusion input id")
    labels = {c["label"] for c in controls}
    for tp in tips:
        if tp["label"] not in labels:
            raise FuseGenError(f"tooltip for an unknown control label {tp['label']!r}")
    mains = list(MAIN_RE.finditer(text))
    if len(mains) != 1:
        raise FuseGenError(f"{len(mains)} main functions found")
    m = mains[0]
    ret, kind, params = m.group(1), m.group(2), m.group(3)
    plist = []
    for p in split_top(params):
        mm = re.fullmatch(r"(int|__TEXTURE__|float)\s+(\w+)", p)
        if not mm:
            raise FuseGenError(f"main parameter {p!r}")
        plist.append((mm.group(1), mm.group(2)))
    want_t = ["p_Width", "p_Height", "p_X", "p_Y", "p_TexR", "p_TexG", "p_TexB"]
    want_x = ["p_Width", "p_Height", "p_X", "p_Y", "p_FromTexR", "p_FromTexG", "p_FromTexB", "p_FromTexA",
              "p_ToTexR", "p_ToTexG", "p_ToTexB", "p_ToTexA"]
    got = [n for _, n in plist]
    if kind == "transform" and (ret != "float3" or got != want_t):
        raise FuseGenError("the transform main must be the float3 texture form: " + ", ".join(got))
    if kind == "transition" and (ret != "float4" or got != want_x):
        raise FuseGenError("the transition main must be the README's float4 form: " + ", ".join(got))
    for r in RESERVED + [b for _, b in RENAMES]:
        if re.search(r"\b" + re.escape(r) + r"\b", text):
            raise FuseGenError(f"the DCTL already uses the name {r}")
    for mark in (UI_MARK, TIP_MARK, ENTRY_MARK):
        if mark.strip() in text:
            raise FuseGenError(f"the DCTL already holds the marker {mark.strip()!r}")
    helpers = strip_comments(text[:m.start()])
    for name in ("TIMELINE_FRAME_INDEX", "TRANSITION_PROGRESS"):
        if re.search(r"\b" + name + r"\b", helpers):
            raise FuseGenError(f"{name} is read outside the main function")
    body = text[m.end():]
    used_planes = [n for _, n in plist[4:] if re.search(r"\b" + n + r"\b", strip_comments(body))]
    return {"path": path, "text": text, "lines": lines, "controls": controls, "tips": tips, "kind": kind,
            "ret": ret, "params": plist, "main_span": (m.start(), m.end()), "main_params_text": params,
            "used_planes": used_planes}

def rename(text, pairs):
    for a, b in pairs:
        text = re.sub(r"(?<![A-Za-z0-9_])" + re.escape(a) + r"(?![A-Za-z0-9_])", b, text)
    return text

def carried_text(d):
    """The DCTL's text as the kernel carries it: DEFINE_UI lines become marker comments, the main function is
    renamed with the frame, the progress and every control appended to its parameters, and the four renames."""
    lines = list(d["lines"])
    for c in d["controls"]:
        lines[c["line"]] = UI_MARK + c["var"]
    for tp in d["tips"]:
        lines[tp["line"]] = TIP_MARK + tp["label"]
    text = "\n".join(lines)
    m = MAIN_RE.search(text)
    extra = EXTRA_PARAMS + "".join(f", {ctype(c)} {c['var']}" for c in d["controls"])
    sig = f"__DEVICE__ {d['ret']} {MAIN}({m.group(3)}, {extra})"
    text = text[:m.start()] + sig + text[m.end():]
    return rename(text, RENAMES)

def param_block(d):
    """The kernel's parameter struct (Lua string DvParams), laid out as: the values first, the size
    array last."""
    rows = []
    for c in d["controls"]:
        t = ctype(c)
        rows.append(f"float {c['var']}[3];" if t == "float3" else f"{t} {c['var']};")
    rows += ["float dvProgress;", "int dvFrame;", "int dvFlipY;", "int dvSize[2];"]
    return "\n".join("\t" + r for r in rows) + "\n"

def c_names(cid, tag):
    """The C names of one Fuse's kernels and parameter structs. The first build
    gave all 40 Fuses DevelopKernel and DvParams with 40 different layouts, and Fusion caches a compute node's
    kernel and its parameter struct by name for the session (DVIPComputeNode has ForceRebuild; the struct text
    becomes a LuaJIT "typedef struct { ... } Name"). The tag is a hash of everything the kernels are built from, so
    a regenerated Fuse never meets a kernel cached from an older one."""
    return {"kernel": f"{cid}K{tag}", "params": f"{cid}P{tag}", "split": f"{cid}S{tag}",
            "split_params": f"{cid}SP{tag}"}

def entry(d, names):
    """The __KERNEL__ function: every pixel calls dvMain with the DCTL's own arguments."""
    planes = [n for _, n in d["params"][4:]]
    texs = "".join(f"__TEXTURE2D__ {n}, " for n in planes)
    if d["kind"] == "transform":
        texs += "__TEXTURE2D__ dvSrc, "
    args = ["params->dvSize[0]", "params->dvSize[1]", "x", "py"] + planes + ["params->dvFrame", "params->dvProgress"]
    for c in d["controls"]:
        if ctype(c) == "float3":
            v = c["var"]
            args.append(f"to_float3(params->{v}[0], params->{v}[1], params->{v}[2])")
        else:
            args.append(f"params->{c['var']}")
    call = f"{MAIN}(" + ", ".join(args) + ")"
    if d["kind"] == "transform":
        write = (f"        float3 c = {call};\n"
                 "        float4 s = _tex2DVec4(dvSrc, x, y);\n"
                 "        _tex2DVec4Write(dvDst, x, y, to_float4(c.x, c.y, c.z, s.w));\n")
    else:
        write = (f"        float4 c = {call};\n"
                 "        _tex2DVec4Write(dvDst, x, y, c);\n")
    return (f"\n{ENTRY_MARK} (Fusion's rows run bottom up; py is the DCTL's top-down row)\n"
            f"__KERNEL__ void {names['kernel']}(__CONSTANTREF__ {names['params']} *params, {texs}__TEXTURE2D_WRITE__ dvDst)\n"
            "{\n"
            "    DEFINE_KERNEL_ITERATORS_XY(x, y)\n"
            "    if (x < params->dvSize[0] && y < params->dvSize[1])\n"
            "    {\n"
            "        int py = params->dvFlipY != 0 ? params->dvSize[1] - 1 - y : y;\n"
            f"{write}"
            "    }\n"
            "}\n")

SPLIT_PARAMS = "\tint ch;\n\tint flipY;\n\tint size[2];\n"
SPLIT_SOURCE = """// one channel of an image as its own texture (the channel in every component), rows turned top-down when
// flipY is set, so a DCTL's _tex2D(plane, x, y) reads what Resolve hands it
__KERNEL__ void @SPLIT@(__CONSTANTREF__ @SPLITPARAMS@ *params, __TEXTURE2D__ src, __TEXTURE2D_WRITE__ dst)
{
    DEFINE_KERNEL_ITERATORS_XY(x, y)
    if (x < params->size[0] && y < params->size[1])
    {
        int sy = params->flipY != 0 ? params->size[1] - 1 - y : y;
        float4 c = _tex2DVec4(src, x, sy);
        float v = params->ch == 0 ? c.x : (params->ch == 1 ? c.y : (params->ch == 2 ? c.z : c.w));
        _tex2DVec4Write(dst, x, y, to_float4(v, v, v, v));
    }
}
"""
MAPPING = """// fusegen mapping (effects/fusegen/README.md section 2): a DCTL reads one channel with _tex2D(plane, x, y);
// here each plane is a texture holding that channel, read at whole-pixel coordinates by the default sampler
#define dvTex2D(dv_t, dv_x, dv_y) (_tex2DVec4((dv_t), (dv_x), (dv_y)).x)
"""
COMPAT = """// fusegen compatibility, used only when the plain source does not build: Resolve's DCTL names for the vector
// constructors, over Fusion's own
#ifndef make_float2
#define make_float2(a, b) to_float2((a), (b))
#endif
#ifndef make_float3
#define make_float3(a, b, c) to_float3((a), (b), (c))
#endif
#ifndef make_float4
#define make_float4(a, b, c, d) to_float4((a), (b), (c), (d))
#endif
"""

DCTL_MATH = {
    "_fabs": (1, "fabs", "fabs"), "_powf": (2, "native_powr", "pow"), "_logf": (1, "native_log", "log"),
    "_log2f": (1, "native_log2", "log2"), "_log10f": (1, "native_log10", "log10"), "_expf": (1, "native_exp", "exp"),
    "_exp2f": (1, "native_exp2", "exp2"), "_exp10f": (1, "native_exp10", "exp10"),
    "_copysignf": (2, "copysign", "copysign"), "_fmaxf": (2, "fmax", "fmax"), "_fminf": (2, "fmin", "fmin"),
    "_clampf": (3, "clamp", "clamp"), "_sqrtf": (1, "native_sqrt", "sqrt"), "_ceilf": (1, "ceil", "ceil"),
    "_floorf": (1, "floor", "floor"), "_fmod": (2, "fmod", "fmod"), "_round": (1, "round", "round"),
    "_atan2f": (2, "atan2", "atan2"), "_sinf": (1, "native_sin", "sin"), "_cosf": (1, "native_cos", "cos"),
    "_tanf": (1, "native_tan", "tan"), "_acosf": (1, "acos", "acos"), "_asinf": (1, "asin", "asin"),
    "_sinpif": (1, "sinpi", "sinpi"), "_cospif": (1, "cospi", "cospi"), "_acoshf": (1, "acosh", "acosh"),
    "_asinhf": (1, "asinh", "asinh"), "_atanhf": (1, "atanh", "atanh"), "_coshf": (1, "cosh", "cosh"),
    "_sinhf": (1, "sinh", "sinh"), "_tanhf": (1, "tanh", "tanh"), "_truncf": (1, "trunc", "trunc"),
    "_fdimf": (2, "fdim", "fdim"), "_fmaf": (3, "fma", "fma"), "_rsqrtf": (1, "rsqrt", "rsqrt"),
}

def math_block():
    def rows(col):
        out = []
        for name, (n, ocl, mtl) in DCTL_MATH.items():
            fn = ocl if col == 1 else mtl
            args = ", ".join("_" + "ABC"[i] for i in range(n))
            cast = ", ".join(f"(float)(_{'ABC'[i]})" for i in range(n))
            out.append(f"#undef {name}\n#define {name}({args}) {fn}({cast})")
        sat = "clamp((float)(_A), 0.0f, 1.0f)" if col == 1 else "saturate((float)(_A))"
        out.append(f"#undef _saturatef\n#define _saturatef(_A) {sat}")
        hyp = ("hypot((float)(_A), (float)(_B))" if col == 1
               else "sqrt((float)(_A) * (float)(_A) + (float)(_B) * (float)(_B))")
        out.append(f"#undef _hypotf\n#define _hypotf(_A, _B) {hyp}")
        return "\n".join(out)
    return ("// fusegen dctl math (README section 2): the argument casts Resolve gives a DCTL on OpenCL and Metal\n"
            "#if !defined(KERNEL_TYPE_IS_DCTL) && defined(DEVICE_IS_OPENCL)\n" + rows(1) + "\n"
            "#elif !defined(KERNEL_TYPE_IS_DCTL) && defined(DEVICE_IS_METAL)\n" + rows(2) + "\n"
            "#endif\n")

MATH = math_block()

RUNTIME = r'''-- the last status of each tool, so a change is reported once
DvLast = {}

-- the compute node's error log (DVIPComputeNode:GetErrorLog, a name in fusionsystem.dll), or a note that it has none
function DvNodeLog(node)
	local log = nil
	if node then
		pcall(function()
			log = node:GetErrorLog()
		end)
	end
	if log == nil or log == "" then
		return "(the node gave no error log; see the Fusion console)"
	end
	return tostring(log)
end

-- report a status: the console, the tool's data and the log file, each once per change
function DvNote(tool, failed, msg)
	local key = DvName
	pcall(function()
		key = tool.Name
	end)
	key = tostring(key)
	local text = msg
	if failed then
		text = "FAILED: " .. msg
	end
	if DvLast[key] == text then
		return
	end
	DvLast[key] = text
	print(DvName .. " [" .. key .. "] " .. text)
	pcall(function()
		tool:SetData("DevelopFuse.Status", text)
	end)
	pcall(function()
		local dir = os.getenv("TEMP") or os.getenv("TMP") or "."
		local f = io.open(dir .. "/DevelopFuse.log", "a")
		if f then
			local line = (text:gsub("[\r\n]+", " | "))
			f:write(os.date("%Y-%m-%d %H:%M:%S") .. "\t" .. key .. "\t" .. DvName .. "\t" .. line .. "\n")
			f:close()
		end
	end)
end

-- a Lua error's message with its traceback when the debug library is there
function DvTrace(e)
	if debug and debug.traceback then
		return debug.traceback(tostring(e), 2)
	end
	return tostring(e)
end

-- the visible error: a solid magenta frame the size of ref (nil when there is no picture to size it by)
function DvFailImage(ref)
	local bad = nil
	if ref then
		pcall(function()
			bad = Image({IMG_Like = ref})
			bad:Fill(Pixel({R = 1.0, G = 0.0, B = 1.0, A = 1.0}))
		end)
	end
	return bad
end
'''

def lua_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'

def long_bracket(s):
    n = 0
    while "]" + "=" * n + "]" in s:
        n += 1
    eq = "=" * n
    return f"[{eq}[\n{s}]{eq}]"

def class_id(name):
    return re.sub(r"[^A-Za-z0-9]", "", name)

def lua_var(var):
    return "In" + var[0].upper() + var[1:]

def input_block(c, tip, idx):
    """The Create() lines for one DCTL control."""
    v, lab, k = c["var"], c["label"], c["kind"]
    st = f"\t\tINPS_StatusText = {lua_str(tip)},\n" if tip else ""
    if k in ("DCTLUI_SLIDER_FLOAT", "DCTLUI_SLIDER_INT"):
        integ = "\t\tINP_Integer = true,\n" if k == "DCTLUI_SLIDER_INT" else ""
        return (f"\t{lua_var(v)} = self:AddInput({lua_str(lab)}, {lua_str(v)}, {{\n"
                "\t\tLINKID_DataType = \"Number\",\n"
                "\t\tINPID_InputControl = \"SliderControl\",\n"
                f"\t\tINP_Default = {c['default']},\n"
                f"\t\tINP_MinScale = {c['lo']},\n"
                f"\t\tINP_MaxScale = {c['hi']},\n"
                f"\t\tINP_MinAllowed = {c['lo']},\n"
                f"\t\tINP_MaxAllowed = {c['hi']},\n"
                f"{integ}{st}\t\t}})\n")
    if k == "DCTLUI_VALUE_BOX":
        return (f"\t{lua_var(v)} = self:AddInput({lua_str(lab)}, {lua_str(v)}, {{\n"
                "\t\tLINKID_DataType = \"Number\",\n"
                "\t\tINPID_InputControl = \"ScrewControl\",\n"
                f"\t\tINP_Default = {c['default']},\n"
                f"{st}\t\t}})\n")
    if k == "DCTLUI_CHECK_BOX":
        return (f"\t{lua_var(v)} = self:AddInput({lua_str(lab)}, {lua_str(v)}, {{\n"
                "\t\tLINKID_DataType = \"Number\",\n"
                "\t\tINPID_InputControl = \"CheckboxControl\",\n"
                "\t\tINP_Integer = true,\n"
                f"\t\tINP_Default = {c['default']},\n"
                f"{st}\t\t}})\n")
    if k == "DCTLUI_COMBO_BOX":
        items = "".join(f"\t\t{{ CCS_AddString = {lua_str(x)}, }},\n" for x in c["labels"])
        return (f"\t{lua_var(v)} = self:AddInput({lua_str(lab)}, {lua_str(v)}, {{\n"
                "\t\tLINKID_DataType = \"Number\",\n"
                "\t\tINPID_InputControl = \"ComboControl\",\n"
                "\t\tINP_Integer = true,\n"
                f"\t\tINP_Default = {c['default']},\n"
                f"{st}{items}\t\t}})\n")
    if k == "DCTLUI_COLOR_PICKER":
        out = ""
        for i, (ch, nm) in enumerate(zip("RGB", ("Red", "Green", "Blue"))):
            head = f"\t\tICS_Name = {lua_str(lab)},\n" if i == 0 else ""
            out += (f"\t{lua_var(v)}{ch} = self:AddInput({lua_str(lab + ' ' + nm)}, {lua_str(v + nm)}, {{\n"
                    f"{head}"
                    "\t\tLINKID_DataType = \"Number\",\n"
                    "\t\tINPID_InputControl = \"ColorControl\",\n"
                    f"\t\tINP_Default = {c['rgb'][i]},\n"
                    f"\t\tIC_ControlGroup = {100 + idx},\n"
                    f"\t\tIC_ControlID = {i},\n"
                    f"{st if i == 0 else ''}\t\t}})\n")
        return out
    raise FuseGenError(k)

def set_block(c):
    """The Process() lines that copy one control into the parameter block."""
    v, k = c["var"], c["kind"]
    if k in ("DCTLUI_SLIDER_FLOAT", "DCTLUI_VALUE_BOX"):
        return f"\tp.{v} = {lua_var(v)}:GetValue(req).Value\n"
    if k in ("DCTLUI_SLIDER_INT", "DCTLUI_CHECK_BOX", "DCTLUI_COMBO_BOX"):
        return f"\tp.{v} = math.floor({lua_var(v)}:GetValue(req).Value + 0.5)\n"
    if k == "DCTLUI_COLOR_PICKER":
        return "".join(f"\tp.{v}[{i}] = {lua_var(v)}{ch}:GetValue(req).Value\n" for i, ch in enumerate("RGB"))
    raise FuseGenError(k)

def combo_enums(d):
    """C constants for DCTL combo enum names (Resolve declares them; the Fuse source has to)."""
    rows = []
    for c in d["controls"]:
        if c["kind"] == "DCTLUI_COMBO_BOX":
            rows.append("enum { " + ", ".join(f"{e} = {i}" for i, e in enumerate(c["enums"])) + " };")
    return ("// fusegen: the combo constants Resolve declares for a DCTL\n" + "\n".join(rows) + "\n") if rows else ""

def generate(path):
    d = parse_dctl(path)
    name = os.path.splitext(os.path.basename(path))[0]
    rel = os.path.relpath(path, EFFECTS).replace("\\", "/")
    cid = class_id(name)
    words = [w for w in name.split() if w != "Develop"]
    icon = "D" + "".join(w[0] for w in words)[:3]
    carried = carried_text(d)
    pblock = param_block(d)
    tag = hashlib.sha1("\n".join([carried, pblock, SPLIT_PARAMS, SPLIT_SOURCE, MATH, MAPPING, combo_enums(d), COMPAT,
                                  RUNTIME]).encode("utf-8")).hexdigest()[:8]
    names = c_names(cid, tag)
    for n in names.values():
        if re.search(r"\b" + re.escape(n) + r"\b", d["text"]):
            raise FuseGenError(f"the DCTL already uses the name {n}")
    kernel = carried + entry(d, names)
    split_source = SPLIT_SOURCE.replace("@SPLITPARAMS@", names["split_params"]).replace("@SPLIT@", names["split"])
    tipmap = {t["label"]: t["text"] for t in d["tips"]}
    trans = d["kind"] == "transition"
    out = []
    out.append(
        f"--[[ {name} as a Fusion Fuse: the {d['kind']} DCTL effects/{rel} run on the GPU through DVIPComputeNode,\n"
        "every pixel calling the DCTL's own main function with the DCTL's own controls. Written by\n"
        "effects/fusegen/fusegen.py; regenerate it, never edit it. The picture is read and written in the values\n"
        "the DCTL sees in Resolve (Rec.709 gamma 2.4 display values in Develop), with no conversion.\n"
        + ("Outgoing and Incoming are the two shots; animate Progress from 0 to 1 over the overlap.\n" if trans else "")
        + "Frame Offset adds to the comp frame for the DCTL's frame value; Hold Frame uses Frame Offset alone.\n"
        "If the kernel cannot run, the output is solid magenta and the reason is in the Fusion console, in the\n"
        "tool's data DevelopFuse.Status and in %TEMP%\\DevelopFuse.log. MIT License. ]]\n")
    out.append(
        f'FuRegisterClass({lua_str(cid)}, CT_Tool, {{\n'
        '\tREGS_Category = "Fuses\\\\Develop",\n'
        f'\tREGS_OpIconString = {lua_str(icon)},\n'
        f'\tREGS_OpDescription = {lua_str(name + " (Develop DCTL in a Fuse)")},\n'
        '\tREG_NoObjMatCtrls = true,\n'
        '\tREG_NoMotionBlurCtrls = true,\n'
        '\t})\n')
    out.append(f"DvName = {lua_str(name)}\nDvKind = {lua_str(d['kind'])}\nDvDctl = {lua_str(rel)}\n")
    steps = ", ".join(f"{c['var']} = {c['step']}" for c in d["controls"] if "step" in c)
    out.append("-- the DCTL slider steps, for the record and the inverse mapping (Fusion sliders have no step)\n"
               f"DvSteps = {{ {steps} }}\n")
    out.append("-- this Fuse's own C names for its kernels and parameter structs (never shared with another Fuse)\n"
               f"DvKernelName = {lua_str(names['kernel'])}\nDvParamsName = {lua_str(names['params'])}\n"
               f"DvSplitName = {lua_str(names['split'])}\nDvSplitParamsName = {lua_str(names['split_params'])}\n")
    out.append(f"DvParams = [[\n{pblock}]]\n")
    out.append(f"DvSplitParams = [[\n{SPLIT_PARAMS}]]\n")
    out.append(f"DvSplitSource = {long_bracket(split_source)}\n")
    out.append(f"DvMath = {long_bracket(MATH)}\n")
    out.append(f"DvMapping = {long_bracket(MAPPING + combo_enums(d))}\n")
    out.append(f"DvCompat = {long_bracket(COMPAT)}\n")
    out.append(f"DvKernelText = {long_bracket(kernel)}\n")
    out.append("-- the plain source first; the compatibility source only if the plain one does not build\n"
               "DvSources = { DvMath .. DvMapping .. DvKernelText, DvCompat .. DvMath .. DvMapping .. DvKernelText }\n"
               "DvWorking = nil\n")
    out.append(RUNTIME)
    cr = ["function Create()\n"]
    if trans:
        cr.append('\tInProgress = self:AddInput("Progress", "Progress", {\n'
                  '\t\tLINKID_DataType = "Number",\n'
                  '\t\tINPID_InputControl = "SliderControl",\n'
                  '\t\tINP_Default = 0.0,\n'
                  '\t\tINP_MinScale = 0.0,\n'
                  '\t\tINP_MaxScale = 1.0,\n'
                  '\t\tINP_MinAllowed = 0.0,\n'
                  '\t\tINP_MaxAllowed = 1.0,\n'
                  '\t\tINPS_StatusText = "The transition from Outgoing (0) to Incoming (1): the DCTL\'s TRANSITION_PROGRESS",\n'
                  '\t\t})\n')
    for i, c in enumerate(d["controls"]):
        cr.append(input_block(c, tipmap.get(c["label"], ""), i))
    cr.append('\tInFrameOffset = self:AddInput("Frame Offset", "FrameOffset", {\n'
              '\t\tLINKID_DataType = "Number",\n'
              '\t\tINPID_InputControl = "SliderControl",\n'
              '\t\tINP_Integer = true,\n'
              '\t\tINP_Default = 0,\n'
              '\t\tINP_MinScale = 0,\n'
              '\t\tINP_MaxScale = 1000,\n'
              '\t\tINPS_StatusText = "Added to the comp frame to make the DCTL\'s frame value (Resolve\'s TIMELINE_FRAME_INDEX)",\n'
              '\t\t})\n'
              '\tInHoldFrame = self:AddInput("Hold Frame", "HoldFrame", {\n'
              '\t\tLINKID_DataType = "Number",\n'
              '\t\tINPID_InputControl = "CheckboxControl",\n'
              '\t\tINP_Integer = true,\n'
              '\t\tINP_Default = 0,\n'
              '\t\tINPS_StatusText = "The frame value is Frame Offset alone, so a moving effect holds still",\n'
              '\t\t})\n'
              '\tInFlipY = self:AddInput("Rows Top Down", "FlipY", {\n'
              '\t\tLINKID_DataType = "Number",\n'
              '\t\tINPID_InputControl = "CheckboxControl",\n'
              '\t\tINP_Integer = true,\n'
              '\t\tINP_Default = 1,\n'
              '\t\tIC_Visible = false,\n'
              '\t\t})\n')
    if trans:
        cr.append('\tInOutgoing = self:AddInput("Outgoing", "Outgoing", {\n'
                  '\t\tLINKID_DataType = "Image",\n'
                  '\t\tLINK_Main = 1,\n'
                  '\t\t})\n'
                  '\tInIncoming = self:AddInput("Incoming", "Incoming", {\n'
                  '\t\tLINKID_DataType = "Image",\n'
                  '\t\tLINK_Main = 2,\n'
                  '\t\tINP_Required = false,\n'
                  '\t\t})\n')
    else:
        cr.append('\tInInput = self:AddInput("Input", "Input", {\n'
                  '\t\tLINKID_DataType = "Image",\n'
                  '\t\tLINK_Main = 1,\n'
                  '\t\t})\n')
    cr.append('\tOutImage = self:AddOutput("Output", "Output", {\n'
              '\t\tLINKID_DataType = "Image",\n'
              '\t\tLINK_Main = 1,\n'
              '\t\t})\n'
              'end\n')
    out.append("".join(cr))
    out.append(
        "-- one channel of img as its own texture, rows top-down (DvSplitSource); returns the plane, or nil and why\n"
        "function DvPlane(req, img, ch, flip)\n"
        "\tlocal plane = Image({IMG_Like = img})\n"
        "\tlocal node = DVIPComputeNode(req, DvSplitName, DvSplitSource, DvSplitParamsName, DvSplitParams)\n"
        "\tif not node then\n"
        "\t\treturn nil, \"the split kernel's compute node was not created (DVIPComputeNode gave nil)\"\n"
        "\tend\n"
        "\tlocal p = node:GetParamBlock(DvSplitParams)\n"
        "\tp.ch = ch\n"
        "\tp.flipY = flip\n"
        "\tp.size[0] = img.DataWindow:Width()\n"
        "\tp.size[1] = img.DataWindow:Height()\n"
        "\tnode:SetParamBlock(p)\n"
        "\tnode:AddInput(\"src\", img)\n"
        "\tnode:AddOutput(\"dst\", plane)\n"
        "\tif node:RunSession(req) then\n"
        "\t\treturn plane\n"
        "\tend\n"
        "\treturn nil, \"the split kernel did not run: \" .. DvNodeLog(node)\n"
        "end\n")
    planes = [n for _, n in d["params"][4:]]
    src_of = {}
    for n in planes:
        shot = "inc" if n.startswith("p_To") else "src"
        ch = n[-1]
        src_of[n] = (shot, ch)
    runl = ["-- the kernel over every pixel with source k; returns true when it ran, or false and why\n",
            "function DvRun(req, k, src, inc, planes, out, frame, flip, progress)\n",
            "\tlocal node = DVIPComputeNode(req, DvKernelName, DvSources[k], DvParamsName, DvParams)\n",
            "\tif not node then\n"
            "\t\treturn false, \"source \" .. k .. \": the compute node was not created (DVIPComputeNode gave nil)\"\n"
            "\tend\n",
            "\tlocal p = node:GetParamBlock(DvParams)\n"]
    for c in d["controls"]:
        runl.append(set_block(c))
    runl += ["\tp.dvProgress = progress\n",
             "\tp.dvFrame = frame\n",
             "\tp.dvFlipY = flip\n",
             "\tp.dvSize[0] = src.DataWindow:Width()\n",
             "\tp.dvSize[1] = src.DataWindow:Height()\n"]
    runl.append("\tnode:SetParamBlock(p)\n")
    for n in planes:
        runl.append(f"\tnode:AddInput({lua_str(n)}, planes.{n})\n")
    if not trans:
        runl.append("\tnode:AddInput(\"dvSrc\", src)\n")
    runl.append("\tnode:AddOutput(\"dvDst\", out)\n"
                "\tif node:RunSession(req) then\n"
                "\t\treturn true\n"
                "\tend\n"
                "\treturn false, \"source \" .. k .. \": RunSession failed: \" .. DvNodeLog(node)\n"
                "end\n")
    out.append("".join(runl))
    pr = ["function DvProcess(req)\n"]
    if trans:
        pr.append("\tlocal src = InOutgoing:GetValue(req)\n"
                  "\tif not src then\n"
                  "\t\treturn nil, \"no Outgoing image\", true, nil\n"
                  "\tend\n"
                  "\tif req:IsPreCalc() then\n"
                  "\t\treturn Image({IMG_Like = src, IMG_NoData = true}), nil, false, src\n"
                  "\tend\n"
                  "\tlocal inc = InIncoming:GetValue(req)\n"
                  "\tif not inc then\n"
                  "\t\treturn src, \"Incoming is not connected, so Outgoing passes through\", false, src\n"
                  "\tend\n"
                  "\tlocal progress = InProgress:GetValue(req).Value\n")
    else:
        pr.append("\tlocal src = InInput:GetValue(req)\n"
                  "\tif not src then\n"
                  "\t\treturn nil, \"no input image\", true, nil\n"
                  "\tend\n"
                  "\tif req:IsPreCalc() then\n"
                  "\t\treturn Image({IMG_Like = src, IMG_NoData = true}), nil, false, src\n"
                  "\tend\n"
                  "\tlocal inc = nil\n"
                  "\tlocal progress = 0.0\n")
    pr.append("\tlocal out = Image({IMG_Like = src})\n"
              "\tlocal flip = math.floor(InFlipY:GetValue(req).Value + 0.5)\n"
              "\tlocal frame = math.floor(InFrameOffset:GetValue(req).Value + 0.5)\n"
              "\tif InHoldFrame:GetValue(req).Value < 0.5 then\n"
              "\t\tframe = frame + math.floor(req.Time + 0.5)\n"
              "\tend\n"
              "\tlocal planes = {}\n"
              "\tlocal why = nil\n")
    for n in planes:
        shot, ch = src_of[n]
        if n in d["used_planes"]:
            idx = "RGBA".index(ch)
            pr.append(f"\tplanes.{n}, why = DvPlane(req, {shot}, {idx}, flip)\n"
                      f"\tif not planes.{n} then\n"
                      f"\t\treturn nil, \"{n}: \" .. tostring(why), true, src\n"
                      "\tend\n")
        else:
            pr.append(f"\tplanes.{n} = {shot} -- the DCTL never reads this plane\n")
    pr.append("\tlocal order = {}\n"
              "\tif DvWorking then\n"
              "\t\torder[1] = DvWorking\n"
              "\tend\n"
              "\tfor k = 1, #DvSources do\n"
              "\t\tif k ~= DvWorking then\n"
              "\t\t\torder[#order + 1] = k\n"
              "\t\tend\n"
              "\tend\n"
              "\tlocal errs = {}\n"
              "\tfor i = 1, #order do\n"
              "\t\tlocal ok, err = DvRun(req, order[i], src, inc, planes, out, frame, flip, progress)\n"
              "\t\tif ok then\n"
              "\t\t\tDvWorking = order[i]\n"
              "\t\t\treturn out, \"ok, the kernel runs from source \" .. order[i], false, src\n"
              "\t\tend\n"
              "\t\terrs[#errs + 1] = tostring(err)\n"
              "\tend\n"
              "\treturn nil, \"the kernel ran from no source: \" .. table.concat(errs, \" || \"), true, src\n"
              "end\n")
    out.append("".join(pr))
    main_in = "InOutgoing" if trans else "InInput"
    out.append("-- every failure is reported and shows as magenta; the input never passes through quietly\n"
               "function Process(req)\n"
               "\tlocal res, msg, failed, ref = nil, nil, true, nil\n"
               "\tlocal called, err = xpcall(function()\n"
               "\t\tres, msg, failed, ref = DvProcess(req)\n"
               "\tend, DvTrace)\n"
               "\tif not called then\n"
               "\t\tres, msg, failed = nil, \"Lua error in Process: \" .. tostring(err), true\n"
               "\t\tif not ref then\n"
               "\t\t\tpcall(function()\n"
               f"\t\t\t\tref = {main_in}:GetValue(req)\n"
               "\t\t\tend)\n"
               "\t\tend\n"
               "\tend\n"
               "\tif msg then\n"
               "\t\tDvNote(self, failed, msg)\n"
               "\tend\n"
               "\tif failed then\n"
               "\t\tres = DvFailImage(ref)\n"
               "\tend\n"
               "\tOutImage:Set(req, res)\n"
               "end\n")
    return name, "\n".join(out), d

def sources(args):
    if args:
        return [os.path.abspath(a) for a in args]
    no_fuse = {"Develop Beat", "Develop Grain Match", "Develop Particles", "Develop Particles Depth"}
    return sorted(p for p in glob.glob(os.path.join(EFFECTS, "*", "build", "*.dctl"))
                  if os.path.splitext(os.path.basename(p))[0] not in no_fuse) + PROBES

def main():
    a = sys.argv[1:]
    out = os.path.join(HERE, "out")
    if "--out" in a:
        i = a.index("--out")
        out = os.path.abspath(a[i + 1])
        del a[i:i + 2]
    os.makedirs(out, exist_ok=True)
    bad = 0
    for path in sources(a):
        try:
            name, lua, d = generate(path)
        except FuseGenError as e:
            bad += 1
            print(f"REFUSED {path}: {e}")
            continue
        dst = os.path.join(out, name + ".fuse")
        open(dst, "w", encoding="utf-8", newline="\n").write(lua)
        print(f"{d['kind']:10s} {len(d['controls']):2d} controls  {dst}")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
