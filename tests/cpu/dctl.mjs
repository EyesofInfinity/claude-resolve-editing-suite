import fs from "node:fs";

export function transpile(path) {
  let src = fs.readFileSync(path, "utf8");
  let uiEnd = 0;
  for (const m of src.matchAll(/DEFINE_UI_\w+\([^\n]*\n/g)) uiEnd = m.index + m[0].length;
  const mainFn = src.search(/__DEVICE__\s+\w+\s+(transform|transition)\s*\(/);
  for (const m of src.matchAll(/\/\*[\s\S]*?\*\/|\/\/[^\n]*/g))
    if (m.index >= uiEnd && m.index < mainFn && /\b(transform|transition)\b/i.test(m[0].replace(/\b(transform|transition)\s+DCTLs?\b/gi, "")))
      throw new Error(`a comment among the functions names the main function, which ValidateDCTL can misread: ${m[0].trim().slice(0, 80)}`);
  src = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  src = src.replace(/__CONSTANT__\s+float\s+(\w+)\s*\[[^\]]*\]\s*=\s*\{([\s\S]*?)\};/g, "const $1 = [$2];");
  if (/__CONSTANT__/.test(src)) throw new Error("unparsed __CONSTANT__");
  const sliders = {};
  src = src.replace(
    /DEFINE_UI_PARAMS\(\s*(\w+)\s*,([^,]+),\s*DCTLUI_SLIDER_FLOAT\s*,\s*([-0-9.]+)\s*,\s*([-0-9.]+)\s*,\s*([-0-9.]+)\s*,\s*([-0-9.]+)\s*\)/g,
    (m, n, label, d, lo, hi) => {
      sliders[n] = { label: label.trim(), def: parseFloat(d), lo: parseFloat(lo), hi: parseFloat(hi) };
      return `const ${n} = (P.${n} !== undefined ? P.${n} : ${d});`;
    });
  if (/DEFINE_UI_PARAMS/.test(src)) throw new Error("unparsed DEFINE_UI_PARAMS");
  const defs = [...src.matchAll(/__DEVICE__\s+\w+\s+(\w+)\s*\(([^)]*)\)\s*\{/g)];
  const at = new Map(defs.map(d => [d[1], d.index]));
  for (const m of defs) {
    let i = m.index + m[0].length, depth = 1;
    while (depth > 0 && i < src.length) { if (src[i] === "{") depth++; else if (src[i] === "}") depth--; i++; }
    const body = src.slice(m.index + m[0].length, i);
    for (const c of body.matchAll(/\b(\w+)\s*\(/g))
      if (at.has(c[1]) && at.get(c[1]) >= m.index) throw new Error(`${m[1]}() calls ${c[1]}() before it is defined: Resolve refuses a helper defined further down`);
    if (m[1] === "transform" || m[1] === "transition") continue;
    const own = new Set(m[2].split(",").map(p => p.trim().split(/\s+/).pop()));
    for (const n of Object.keys(sliders))
      if (!own.has(n) && new RegExp(`\\b${n}\\b`).test(body)) throw new Error(`slider ${n} read in ${m[1]}(): Resolve sees sliders only inside the main function`);
  }
  {
    const opnd = "(\\b[A-Za-z_]\\w*\\b|\\b\\d+\\b(?![.\\w]))";
    const fnDefs = [...src.matchAll(/__DEVICE__\s+\w+\s+\w+\s*\([^)]*\)\s*\{/g)];
    let rebuilt = "", last = 0;
    for (const m of fnDefs) {
      let i = m.index + m[0].length, depth = 1;
      while (depth > 0 && i < src.length) { if (src[i] === "{") depth++; else if (src[i] === "}") depth--; i++; }
      const fn = src.slice(m.index, i), ints = new Set(), others = new Set();
      for (const d of fn.matchAll(/\bint\s+([A-Za-z_]\w*)/g)) ints.add(d[1]);
      for (const d of fn.matchAll(/\b(?:float[234]?|uint)\s+([A-Za-z_]\w*)/g)) others.add(d[1]);
      for (const d of fn.matchAll(/\b(int|float[234]?|uint)\s+([^;{}]*);/g)) {
        let dp = 0, cur = "";
        const parts = [];
        for (const ch of d[2]) { if (ch === "(") dp++; else if (ch === ")") dp--; if (ch === "," && dp === 0) { parts.push(cur); cur = ""; } else cur += ch; }
        parts.push(cur);
        for (const p of parts.slice(1)) { const nm = p.trim().match(/^([A-Za-z_]\w*)\s*(=|$)/); if (nm) (d[1] === "int" ? ints : others).add(nm[1]); }
      }
      const out = fn.replace(new RegExp(`${opnd}\\s*/\\s*${opnd}`, "g"), (all, a, b, at, whole) => {
        const isInt = t => /^\d+$/.test(t) || ints.has(t);
        const before = whole.slice(0, at), after = whole.slice(at + all.length);
        if (/\.\s*$/.test(before)) return all;
        if (!isInt(a) || !isInt(b) || (/^\d+$/.test(a) && /^\d+$/.test(b))) return all;
        if (/\(int\)\s*\(\s*$/.test(before) && /^\s*\)/.test(after)) return all;
        if (others.has(a) || others.has(b)) throw new Error(`int division ${a} / ${b} in a function that also declares one of them another type: write it out`);
        if (/(?:[*\/%]|\(\s*(?:int|uint|float)\s*\))\s*$/.test(before) || /^\s*[\[(]/.test(after) || /^\s*\//.test(after))
          throw new Error(`int division ${a} / ${b} inside a longer product or after a cast: parenthesise the division you mean`);
        return `Math.trunc(${a} / ${b})`;
      });
      rebuilt += src.slice(last, m.index) + out;
      last = i;
    }
    src = rebuilt + src.slice(last);
  }
  src = src.replace(/DEFINE_UI_TOOLTIP\([^"]*"[^"]*"\)/g, "");
  src = src.replace(/__DEVICE__\s+\w+\s+(\w+)\s*\(([^)]*)\)/g, (m, name, params) =>
    `function ${name}(${params.split(",").map(p => p.trim().split(/\s+/).pop()).filter(Boolean).join(", ")})`);
  src = src.replace(/\(int\)\s*_round\(/g, "_round(").replace(/\(int\)\s*\(/g, "Math.trunc(").replace(/\(uint\)\s*\(/g, "__u32(").replace(/\(float\)\s*/g, "");
  if (/\((int|uint|float)\)/.test(src)) throw new Error("cast without parentheses");
  src = src.replace(/\b(?:const\s+)?(?:float[234]?|int|uint)\s+(?=[A-Za-z_])/g, "let ");
  src = src.replace(/\b(\d+\.\d*(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)f\b/g, "$1").replace(/\b(\d+)u\b/g, "$1");
  src = src.replace(/function hash01\(/, "function __dctl_hash01(").replace(/function RAND\(/, "function __dctl_RAND(");
  return { js: src, sliders };
}

const prelude = `
"use strict";
const _powf = Math.pow, _expf = Math.exp, _exp2f = x => Math.pow(2, x), _exp10f = x => Math.pow(10, x);
const _logf = Math.log, _log2f = Math.log2, _log10f = Math.log10, _sqrtf = Math.sqrt, _fabs = Math.abs;
const _cosf = x => Math.fround(Math.cos(x)), _sinf = x => Math.fround(Math.sin(x)), _atan2f = Math.atan2, _tanhf = Math.tanh;
const _acosf = x => Math.fround(Math.acos(x));
const _fmaxf = (a, b) => (a > b ? a : b), _fminf = (a, b) => (a < b ? a : b);
const _saturatef = x => (x < 0 ? 0 : x > 1 ? 1 : x), _clampf = (x, a, b) => (x < a ? a : x > b ? b : x);
const _round = x => Math.sign(x) * Math.round(Math.abs(x)), _fmod = (x, y) => x % y;
const _copysignf = (x, y) => (y < 0 || Object.is(y, -0) ? -Math.abs(x) : Math.abs(x));
const make_float3 = (x, y, z) => ({ x, y, z }), make_float2 = (x, y) => ({ x, y });
const make_float4 = (x, y, z, w) => ({ x, y, z, w }), _floorf = Math.floor;
const _tex2D = (t, x, y) => t.d[y * t.w + x];
const __u32 = x => x >>> 0;
const TIMELINE_FRAME_INDEX = ENV.frame;
const TRANSITION_PROGRESS = ENV.progress === undefined ? 0 : ENV.progress;
function hash01(x, y, z) {
  const M = Math.imul;
  x = (M(x, 1664525) + 1013904223) >>> 0; y = (M(y, 1664525) + 1013904223) >>> 0; z = (M(z, 1664525) + 1013904223) >>> 0;
  x = (x + M(y, z)) >>> 0; y = (y + M(z, x)) >>> 0; z = (z + M(x, y)) >>> 0;
  x = (x ^ (x >>> 16)) >>> 0; y = (y ^ (y >>> 16)) >>> 0; z = (z ^ (z >>> 16)) >>> 0;
  x = (x + M(y, z)) >>> 0; y = (y + M(z, x)) >>> 0; z = (z + M(x, y)) >>> 0;
  return (x >>> 8) / 16777216;
}
function RAND(seed) { return hash01(seed >>> 0, 0, 0); }
`;

export function compile(path, params = {}, env = { frame: 1 }) {
  const { js, sliders } = transpile(path);
  for (const k of Object.keys(params)) if (!(k in sliders)) throw new Error("unknown slider " + k);
  const fn = new Function("P", "ENV", prelude + js + "\nreturn typeof transition === 'function' ? transition : transform;");
  return { transform: fn(params, env), sliders };
}

export function runTransition(path, params, env, from, to) {
  const T = compile(path, params, env).transform;
  const { w, h } = from, n = w * h;
  const out = { w, h, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  const F = [{ d: from.r, w }, { d: from.g, w }, { d: from.b, w }], O = [{ d: to.r, w }, { d: to.g, w }, { d: to.b, w }];
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const c = T(w, h, x, y, F[0], F[1], F[2], null, O[0], O[1], O[2], null), i = y * w + x;
    out.r[i] = c.x; out.g[i] = c.y; out.b[i] = c.z;
  }
  return out;
}

export function run(transform, img, region) {
  const { w, h } = img;
  const R = { d: img.r, w }, G = { d: img.g, w }, B = { d: img.b, w };
  const x0 = region ? region.x0 : 0, y0 = region ? region.y0 : 0, x1 = region ? region.x1 : w, y1 = region ? region.y1 : h;
  const ow = x1 - x0, oh = y1 - y0;
  const out = { w: ow, h: oh, r: new Float32Array(ow * oh), g: new Float32Array(ow * oh), b: new Float32Array(ow * oh) };
  for (let y = y0; y < y1; y++)
    for (let x = x0; x < x1; x++) {
      const c = transform(w, h, x, y, R, G, B);
      const i = (y - y0) * ow + (x - x0);
      out.r[i] = c.x; out.g[i] = c.y; out.b[i] = c.z;
    }
  return out;
}

export function readRGB48(path, w, h) {
  const buf = fs.readFileSync(path);
  const n = w * h, img = { w, h, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let i = 0; i < n; i++) {
    img.r[i] = buf.readUInt16LE(i * 6) / 65535;
    img.g[i] = buf.readUInt16LE(i * 6 + 2) / 65535;
    img.b[i] = buf.readUInt16LE(i * 6 + 4) / 65535;
  }
  return img;
}

export function writeRGB48(path, img) {
  const n = img.w * img.h, buf = Buffer.alloc(n * 6);
  const q = v => Math.max(0, Math.min(65535, Math.round(v * 65535)));
  for (let i = 0; i < n; i++) {
    buf.writeUInt16LE(q(img.r[i]), i * 6); buf.writeUInt16LE(q(img.g[i]), i * 6 + 2); buf.writeUInt16LE(q(img.b[i]), i * 6 + 4);
  }
  fs.writeFileSync(path, buf);
}

export function crop(img, x0, y0, x1, y1) {
  const w = x1 - x0, h = y1 - y0, o = { w, h, r: new Float32Array(w * h), g: new Float32Array(w * h), b: new Float32Array(w * h) };
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const s = (y + y0) * img.w + x + x0, d = y * w + x;
    o.r[d] = img.r[s]; o.g[d] = img.g[s]; o.b[d] = img.b[s];
  }
  return o;
}
