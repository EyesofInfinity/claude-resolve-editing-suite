import { compile, runTransition } from "../../tests/cpu/dctl.mjs";

const MV = "build/Develop Strip Move.dctl", LK = "build/Develop Strip Look.dctl", W = 320, H = 180, n = W * H;
let s = 31;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function img(fn) {
  const o = { w: W, h: H, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const c = fn(x, y), i = y * W + x; o.r[i] = c[0]; o.g[i] = c[1]; o.b[i] = c[2]; }
  return o;
}
const A = img((x, y) => { const v = 0.35 + 0.25 * Math.sin(x / 7) * Math.cos(y / 11) + (y < 40 ? 0.35 : 0) + (rnd() < 0.004 ? 0.4 : 0); return [Math.min(v, 1), Math.min(0.9 * v, 1), Math.min(0.7 * v + 0.05 * rnd(), 1)]; });
const B = img((x, y) => { const r = Math.hypot(x - W / 2, y - H / 3), v = 0.3 + 0.3 * Math.sin(r / 6) + (r < 25 ? 0.4 : 0); return [Math.min(0.5 * v, 1), Math.min(0.8 * v, 1), Math.min(v, 1)]; });
const flat = v => img(() => [v, v, v]);
const diff = (o, q) => { let d = 0, m = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < n; i++) { const e = Math.abs(o[k][i] - q[k][i]); if (e > 1e-9) d++; m += e; } return { n: d, mean: +(m / (3 * n)).toFixed(4) }; };
const Y = (o, i) => 0.2126 * o.r[i] + 0.7152 * o.g[i] + 0.0722 * o.b[i];
const mean = o => { let m = 0; for (let i = 0; i < n; i++) m += Y(o, i); return m / n; };
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const NAMES = ["Card Flip", "Parallax Strips", "Strip Slide", "Swish Prism", "Swish Warp", "Smoke Wipe", "Texture Wipe", "Cells Wipe", "Bubble Wipe", "Lens Wipe", "Stretch Wipe"];
const at = (st, p, a = A, b = B, P = {}) => runTransition(MV, { smStyle: st, ...P }, { progress: p, frame: 1 }, a, b);
function look(P, a, frame = 236) {
  const T = compile(LK, P, { frame }).transform;
  const o = { w: W, h: H, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  const R = { d: a.r, w: W }, G = { d: a.g, w: W }, Bt = { d: a.b, w: W };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const c = T(W, H, x, y, R, G, Bt), i = y * W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z; }
  return o;
}

for (let st = 0; st < 11; st++) {
  const N = NAMES[st];
  ok(`${N} starts exactly on the outgoing shot`, diff(at(st, 0), A).n === 0, JSON.stringify(diff(at(st, 0), A)));
  ok(`${N} ends exactly on the incoming shot`, diff(at(st, 1), B).n === 0, JSON.stringify(diff(at(st, 1), B)));
  const e0 = diff(at(st, 0.02), A).mean, e1 = diff(at(st, 0.98), B).mean;
  ok(`${N} eases out and in (within 0.005 at progress 0.02 and 0.98)`, e0 < 0.005 && e1 < 0.005, `${e0} ${e1}`);
}
{
  const lo = mean(at(0, 0.5, A, B, { smStagger: 0, smLight: 0 }));
  ok("Card Flip: the cards stand edge-on at the middle", lo < 0.3 * Math.min(mean(A), mean(B)), `mean luma ${lo.toFixed(3)}`);
  const ramp = img(x => [x / W, x / W, x / W]);
  const o = at(0, 0.8, A, ramp, { smStagger: 0, smLight: 0, smAmount: 0 });
  let up = 0, dn = 0;
  for (let y = 60; y < 120; y++) for (let x = 5; x < 35; x++) { const d = o.g[y * W + x + 1] - o.g[y * W + x]; if (d > 0) up++; else if (d < 0) dn++; }
  ok("Card Flip: the back shows the incoming shot the right way round", up > 4 * dn, `rising ${up}, falling ${dn}`);
}
{
  const g = flat(0.6), dark = o => { let c = 0; for (let i = 0; i < n; i++) if (Y(o, i) < 0.1) c++; return c; };
  const d1 = dark(at(1, 0.5, g, g, { smAmount: 100 })), d0 = dark(at(1, 0.5, g, g, { smAmount: 0 }));
  ok("Parallax Strips: far strips shrink to show the dark behind (none at Amount 0)", d1 > n * 0.01 && d0 === 0, `dark pixels ${d1}, at Amount 0 ${d0}`);
}
{
  const line = img(x => (Math.abs(x - 160) < 2 ? [1, 1, 1] : [0.2, 0.2, 0.2]));
  const o = at(2, 0.3, line, line, { smStagger: 0, smBlur: 0, smAngle: 0 });
  const peak = y => { let m = -1, mx = 0; for (let x = 0; x < W; x++) if (o.g[y * W + x] > m) { m = o.g[y * W + x]; mx = x; } return mx; };
  const x0 = peak(10), x1 = peak(33);
  ok("Strip Slide: neighbouring strips slide opposite ways", x0 > 165 && x1 < 155, `line at x ${x0} in one strip, ${x1} in the next`);
}
{
  const bar = img(x => (x >= 150 && x < 170 ? [1, 1, 1] : [0, 0, 0]));
  const o = at(3, 0.3, bar, bar, { smLight: 0, smAngle: 0 });
  let rx = 0, rw = 0, bx = 0, bw = 0;
  for (let i = 0; i < n; i++) { const x = i % W; rx += x * o.r[i]; rw += o.r[i]; bx += x * o.b[i]; bw += o.b[i]; }
  const d = rx / rw - bx / bw, P = at(3, 0.3, bar, bar, { smLight: 0, smAngle: 0 });
  ok("Swish Prism: red and blue part along the move", Math.abs(d) > 2, `red centre minus blue centre ${d.toFixed(2)} px`);
}
{
  const line = img(x => (Math.abs(x - 160) < 2 ? [1, 1, 1] : [0.2, 0.2, 0.2]));
  const bow = A2 => { const o = at(4, 0.2, line, line, { smBlur: 0, smAngle: 0, smAmount: A2, smLight: 0 });
    const peak = y => { let m = -1, mx = 0; for (let x = 0; x < W; x++) if (o.g[y * W + x] > m) { m = o.g[y * W + x]; mx = x; } return mx; };
    return peak(90) - peak(5); };
  const b1 = bow(100), b0 = bow(0);
  ok("Swish Warp: the middle leads, the edges lag", Math.abs(b1) > 4 && Math.abs(b0) <= 1, `bow ${b1} px, at Amount 0 ${b0}`);
}
for (const st of [5, 9]) {
  const o = at(st, 0.5, A, B, { smAngle: 0, smLight: 0 });
  let l = 0, r = 0;
  for (let y = 0; y < H; y++) { for (let x = 0; x < 20; x++) l += Math.abs(o.g[y * W + x] - B.g[y * W + x]); for (let x = W - 20; x < W; x++) r += Math.abs(o.g[y * W + x] - A.g[y * W + x]); }
  l /= 20 * H; r /= 20 * H;
  ok(`${NAMES[st]}: the incoming shot behind the front, the outgoing ahead`, l < 0.03 && r < 0.03, `left off B ${l.toFixed(4)}, right off A ${r.toFixed(4)}`);
}
{
  const g0 = flat(0.1), g1 = flat(0.9);
  const wander = a2 => { const o = at(6, 0.5, g0, g1, { smAmount: a2, smLight: 0, smAngle: 0 }); const f = [];
    for (let y = 0; y < H; y++) { let c = 0; for (let x = 0; x < W; x++) if (o.g[y * W + x] > 0.5) c++; f.push(c / W); }
    const m = f.reduce((a, b) => a + b) / H; return Math.sqrt(f.reduce((a, b) => a + (b - m) ** 2, 0) / H); };
  const w1 = wander(100), w0 = wander(0);
  ok("Texture Wipe: the texture leads the front", w1 > 0.05 && w0 < 0.03, `row-to-row spread ${w1.toFixed(3)}, straight ${w0.toFixed(3)}`);
}
{
  const g0 = flat(0.1), g1 = flat(0.9), o = at(7, 0.45, g0, g1, { smAngle: 0 });
  let open = 0; for (let i = 0; i < n; i++) if (o.g[i] > 0.5) open++;
  const f = open / n, os = at(7, 0.45, flat(0.6), flat(0.6), {});
  let seam = 0; for (let i = 0; i < n; i++) if (os.g[i] < 0.5) seam++;
  ok("Cells Wipe: cells part open, seams between them", f > 0.15 && f < 0.85 && seam > 100, `open ${f.toFixed(2)}, seam pixels ${seam}`);
}
{
  const o = at(8, 0.4, flat(0.2), flat(0.5), {});
  let hot = 0, inB = 0; for (let i = 0; i < n; i++) { if (o.g[i] > 0.85) hot++; if (Math.abs(o.g[i] - 0.5) < 0.05) inB++; }
  ok("Bubble Wipe: bubbles show the incoming shot and catch a highlight", hot > 5 && inB > 0.05 * n, `highlight pixels ${hot}, incoming ${inB}`);
}
{
  const ramp = img(x => [x / W, x / W, x / W]);
  const o = at(9, 0.5, ramp, ramp, { smAngle: 0, smLight: 0 }), row = 90 * W;
  const mid = (o.g[row + 161] - o.g[row + 158]) / 3, out = (o.g[row + 60] - o.g[row + 57]) / 3;
  ok("Lens Wipe: the rod magnifies the picture under it", mid > 0 && mid < out / 1.5, `slope under the rod ${mid.toExponential(2)}, outside ${out.toExponential(2)}`);
}
{
  const ramp = img(x => [x / W, x / W, x / W]);
  const o = at(10, 0.3, flat(0.5), ramp, { smStagger: 0, smBlur: 0, smAngle: 0, smLight: 0 }), row = 90 * W;
  const sl = (o.g[row + 45] - o.g[row + 5]) / 40, sB = 1 / W;
  ok("Stretch Wipe: the incoming strip is stretched along the move", sl > 0 && sl < sB / 1.5, `slope ${sl.toExponential(2)} against the shot's ${sB.toExponential(2)}`);
}
{
  const noise = img(() => [rnd(), rnd(), rnd()]), noise2 = img(() => [rnd(), rnd(), rnd()]);
  const sets = [{}, { smAmount: 100, smStagger: 0 }, { smAmount: 100, smStagger: 100, smCount: 2 }, { smCount: 40, smAmount: 100 },
                { smAngle: 90 }, { smAngle: 200, smAmount: 100 }, { smAngle: 315, smStagger: 30 }];
  let bad = 0, where = "";
  for (const P of sets) for (let i = 0; i <= 96; i++) {
    const o = at(0, i / 96, noise, noise2, P);
    for (const c of ["r", "g", "b"]) for (let q = 0; q < n; q++) if (!Number.isFinite(o[c][q])) { if (!bad) where = `${JSON.stringify(P)} at ${i}/96, pixel ${q}`; bad++; }
  }
  ok("Card Flip: finite on every pixel over progress 0 to 1 in 1/96 steps (7 slider sets)", bad === 0, bad ? `${bad} bad, first ${where}` : "none bad");
}
{
  const fs = await import("node:fs");
  const unset = [];
  for (const f of ["Develop Strip Move.src.dctl", "Develop Strip Look.src.dctl"]) {
    const src = fs.readFileSync(new URL(f, import.meta.url), "utf8").replace(/\/\/[^\n]*/g, "");
    for (const m of src.matchAll(/^[ \t]*(?:float[234]?|int|uint)\s+([^;{}]*);/gm)) {
      let dp = 0, cur = ""; const parts = [];
      for (const ch of m[1]) { if (ch === "(") dp++; else if (ch === ")") dp--; if (ch === "," && dp === 0) { parts.push(cur); cur = ""; } else cur += ch; }
      parts.push(cur);
      for (const p of parts) if (!p.includes("=")) unset.push(`${f}: ${p.trim()}`);
    }
  }
  ok("every local is given a value where it is declared", unset.length === 0, unset.length ? unset.slice(0, 6).join("; ") : "none unset");
}
{
  const { sliders } = compile(MV, {}, { progress: 0.5 });
  let bad = 0;
  for (let k = 0; k < 30; k++) {
    const P = {};
    for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd();
    const o = runTransition(MV, P, { progress: rnd(), frame: 1 }, A, B);
    for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; }
  }
  ok("Strip Move: range over 30 slider sets", bad === 0, `bad ${bad}`);
}

const LN = ["Borders", "Colour Choke", "Strip Slide", "Infinite Zoom", "Fluted Glass"];
for (let m = 0; m < 5; m++) {
  const P = { slAmount: 0 }; for (const [nm, v] of Object.entries(compile(LK, {}, { frame: 1 }).sliders)) if (nm !== "slAmount") P[nm] = v.hi;
  P.slMode = m;
  ok(`Strip Look ${LN[m]}: Look 0 is identity`, diff(look(P, A), A).n === 0, JSON.stringify(diff(look(P, A), A)));
}
{
  const o = look({ slMode: 0, slRough: 0 }, A), c = 90 * W + 160;
  ok("Borders: the mat of Tone at the corner, the picture untouched in the middle", Math.abs(o.g[2 * W + 2] - 0.92 * 0.985) < 0.03 && Math.abs(o.g[c] - A.g[c]) < 1e-4, `corner ${o.g[2 * W + 2].toFixed(3)}, middle off by ${Math.abs(o.g[c] - A.g[c]).toExponential(1)}`);
}
{
  const dot = img((x, y) => (x === 160 && y === 90 ? [1, 1, 1] : [0, 0, 0]));
  const sp = look({ slMode: 1, slSize: 100, slSpread: 100, slLevel: 0 }, dot), ch = look({ slMode: 1, slSize: 100, slSpread: -100, slLevel: 0 }, dot);
  let lit = 0; for (let i = 0; i < n; i++) if (sp.g[i] > 0.5) lit++;
  ok("Colour Choke: the light spreads (Spread 100), chokes back (-100)", lit > 4 && ch.g[90 * W + 160] < 0.2, `lit pixels ${lit}, choked centre ${ch.g[90 * W + 160].toFixed(3)}`);
}
{
  const line = img(x => (Math.abs(x - 160) < 2 ? [1, 1, 1] : [0.2, 0.2, 0.2]));
  const o = look({ slMode: 2, slAngle: 0, slSize: 0, slSpeed: 0, slRough: 100, slLevel: 50, slLight: 0 }, line);
  const xs = new Set(); for (let y = 2; y < H; y += 12) { let m = -1, mx = 0; for (let x = 0; x < W; x++) if (o.g[y * W + x] > m) { m = o.g[y * W + x]; mx = x; } xs.add(Math.round(mx / 4)); }
  const z = look({ slMode: 2, slLevel: 0, slLight: 0 }, A);
  let mz = 0; for (let i = 0; i < n; i++) mz = Math.max(mz, Math.abs(z.g[i] - A.g[i]));
  ok("Strip Slide: strips slid by their own offsets; Level 0 leaves them in place", xs.size >= 5 && mz < 1e-4, `${xs.size} line positions, Level 0 max off ${mz.toExponential(1)}`);
  const f1 = look({ slMode: 2 }, A, 236), f2 = look({ slMode: 2 }, A, 237);
  ok("Strip Slide: Speed moves the strips frame to frame", diff(f1, f2).n > 1000, `changed ${diff(f1, f2).n}`);
}
{
  const sm = img((x, y) => { const v = 0.5 + 0.3 * Math.sin(x / 25) * Math.cos(y / 19); return [v, v, v]; });
  const P = { slMode: 3, slSize: 50, slLevel: 0, slLight: 0, slPhase: 0, slSpeed: 0 }, R = 1.5 + 3.5 * 0.5;
  const o = look(P, sm), cx = 159.5, cy = 89.5;
  let e = 0, k = 0;
  for (let j = -60; j <= 60; j += 10) for (let i = -140; i <= 140; i += 20) {
    if (Math.max(Math.abs(i) / 160, Math.abs(j) / 90) < 0.5) continue;
    const a = o.g[Math.round(cy + j) * W + Math.round(cx + i)], b = o.g[Math.round(cy + j / R) * W + Math.round(cx + i / R)];
    e += Math.abs(a - b); k++;
  }
  const end = look({ ...P, slPhase: 99.99 }, sm), beg = look({ ...P, slPhase: 0 }, sm);
  ok("Infinite Zoom: the copy repeats the frame, and the loop closes on itself", e / k < 0.03 && diff(end, beg).mean < 0.01, `copy off by ${(e / k).toFixed(4)}, loop seam ${diff(end, beg).mean}`);
}
{
  const ramp = img(x => [x / W, x / W, x / W]);
  const o = look({ slMode: 4, slAngle: 90, slLight: 0, slLevel: 50, slSoft: 0 }, ramp);
  const wf = (8 + 60) * (H / 1080), c = Math.round(159.5 + 2 * wf), row = 90 * W;
  const z = look({ slMode: 4, slLevel: 0, slLight: 0, slSoft: 0 }, ramp);
  let mz = 0; for (let i = 0; i < n; i++) mz = Math.max(mz, Math.abs(z.g[i] - ramp.g[i]));
  ok("Fluted Glass: each flute turns the picture over; Level 0 is plain glass", o.g[row + c + 1] < o.g[row + c - 1] && mz < 1e-3, `across a flute's middle ${o.g[row + c - 1].toFixed(3)} to ${o.g[row + c + 1].toFixed(3)}, Level 0 max off ${mz.toExponential(1)}`);
}
{
  const { sliders } = compile(LK, {}, { frame: 1 });
  let bad = 0;
  for (let k = 0; k < 30; k++) {
    const P = {};
    for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd();
    const o = look(P, A, 1 + (k * 7) % 300);
    for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; }
  }
  ok("Strip Look: range over 30 slider sets", bad === 0, `bad ${bad}`);
}
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
