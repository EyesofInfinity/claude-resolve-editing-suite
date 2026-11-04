import { compile } from "../../tests/cpu/dctl.mjs";

const F = "build/Develop Psych.dctl";
let s = 13;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function image(W, H, fill) {
  const n = W * H, A = { W, H, n, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let i = 0; i < n; i++) { const c = fill(i, i % W, (i / W) | 0); A.r[i] = c[0]; A.g[i] = c[1]; A.b[i] = c[2]; }
  return A;
}
function run(P, frame, A) {
  const T = compile(F, P, { frame }).transform;
  const o = { r: new Float32Array(A.n), g: new Float32Array(A.n), b: new Float32Array(A.n) };
  const R = { d: A.r, w: A.W }, G = { d: A.g, w: A.W }, Bt = { d: A.b, w: A.W };
  for (let y = 0; y < A.H; y++) for (let x = 0; x < A.W; x++) { const c = T(A.W, A.H, x, y, R, G, Bt), i = y * A.W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z; }
  return o;
}
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const NAMES = ["Blobs", "Stripes", "Zebra", "Solarize", "Pseudo Colour", "Band Pass", "Prism", "Dog Vision", "Colour Shadow"];
const W = 240, H = 135;
const A = image(W, H, (i, x, y) => { const d = Math.hypot(x - 80, y - 60), e = Math.hypot(x - 170, y - 80);
  const v = 0.15 + 0.5 * x / W + 0.3 * Math.exp(-d * d / 600) - 0.2 * Math.exp(-e * e / 400) + 0.03 * rnd();
  return [Math.min(1, v * 1.05), v, Math.max(0, v * 0.8)]; });
const L = (o, i) => 0.2126 * o.r[i] + 0.7152 * o.g[i] + 0.0722 * o.b[i];
{ const P = { psAmount: 0 }; for (const [nm, v] of Object.entries(compile(F, {}, { frame: 1 }).sliders)) if (nm !== "psAmount") P[nm] = v.hi;
  const o = run(P, 10, A); let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < A.n; i++) if (o[k][i] !== A[k][i]) d++;
  ok("off is identity", d === 0, `differ ${d}`); }
for (let m = 0; m < 9; m++) {
  const a1 = run({ psMode: m }, 236, A), a2 = run({ psMode: m }, 236, A), b1 = run({ psMode: m }, 260, A);
  const z1 = run({ psMode: m, psSpeed: 0 }, 236, A), z2 = run({ psMode: m, psSpeed: 0 }, 500, A);
  let rep = 0, mov = 0, still = 0;
  for (let i = 0; i < A.n; i++) { if (a1.g[i] !== a2.g[i]) rep++; if (Math.abs(a1.g[i] - b1.g[i]) > 1e-4) mov++; if (z1.g[i] !== z2.g[i]) still++; }
  const moves = [0, 1, 2, 3, 4, 8].includes(m);
  ok(`${NAMES[m]}: repeat identical, Speed 0 holds, ${moves ? "a second on it cycles" : "holds without time"}`,
     rep === 0 && still === 0 && (moves ? mov > A.n * 0.3 : mov === 0), `repeat ${rep}, Speed 0 moved ${still}, a second moved ${mov}`);
}
const corr = (o) => { let sa = 0, sb = 0, sab = 0, saa = 0, sbb = 0; for (let i = 0; i < A.n; i++) { const a = L(o, i), b = L(A, i); sa += a; sb += b; sab += a * b; saa += a * a; sbb += b * b; }
  const n = A.n, ma = sa / n, mb = sb / n; return (sab / n - ma * mb) / Math.sqrt((saa / n - ma * ma) * (sbb / n - mb * mb)); };
for (const m of [0, 1, 8]) { const c = corr(run({ psMode: m }, 236, A)); ok(`${NAMES[m]} keeps the picture's shapes (luma correlation)`, c > 0.6, c.toFixed(3)); }
{ const o = run({ psMode: 2, psColour: 0 }, 236, A); let mid = 0, grey = 0;
  for (let i = 0; i < A.n; i++) { if (o.g[i] > 0.1 && o.g[i] < 0.9) mid++; grey = Math.max(grey, Math.abs(o.r[i] - o.g[i]), Math.abs(o.g[i] - o.b[i])); }
  ok("Zebra at Colour 0 is black and white stripes", mid < 0.12 * A.n && grey < 1e-9, `between ${mid} of ${A.n}, split ${grey}`); }
const ramp = image(256, 1, i => [i / 255, i / 255, i / 255]);
{ // red: at Speed 0 its fold sits on Level (green and blue drift a third of a cycle either side by design)
  const o = run({ psMode: 3, psSpeed: 0, psLevel: 50 }, 1, ramp); let pk = 0; for (let i = 0; i < 256; i++) if (o.r[i] > o.r[pk]) pk = i;
  ok("Solarize folds the ramp: red rises to Level (0.5), falls after, peak at white", Math.abs(pk - 127.5) < 2 && o.r[255] < 0.05 && o.r[pk] > 0.95, `peak at ${pk} (${o.r[pk].toFixed(3)}), end ${o.r[255].toFixed(3)}`); }
{ const o = run({ psMode: 4, psSpeed: 0 }, 1, ramp); const hues = new Set();
  for (let i = 0; i < 256; i += 4) { const r = o.r[i], g = o.g[i], b = o.b[i]; hues.add(r >= g && r >= b ? "r" : g >= b ? "g" : "b"); }
  ok("Pseudo Colour runs the ramp through red, green and blue", hues.size === 3, [...hues].join("")); }
{ const flat = image(64, 36, () => [0.4, 0.5, 0.6]), o = run({ psMode: 5 }, 1, flat); let d = 0; for (let i = 0; i < flat.n; i++) d = Math.max(d, Math.abs(o.r[i] - 0.5), Math.abs(o.g[i] - 0.5), Math.abs(o.b[i] - 0.5));
  ok("Band Pass of a flat picture is mid grey", d < 1e-6, `off by ${d}`); }
{ const wh = image(64, 36, () => [1, 1, 1]), o = run({ psMode: 6, psLevel: 100 }, 1, wh); let d = 0; for (let i = 0; i < wh.n; i++) d = Math.max(d, 1 - o.r[i], 1 - o.g[i], 1 - o.b[i]);
  ok("Prism keeps white white", d < 1e-6, `off by ${d}`);
  const sq = image(W, H, (i, x, y) => (x > 150 && x < 210 && y > 30 && y < 100 ? [1, 1, 1] : [0, 0, 0]));
  const o2 = run({ psMode: 6, psLevel: 100 }, 1, sq); let fr = 0; for (let i = 0; i < sq.n; i++) if (Math.abs(o2.r[i] - o2.b[i]) > 0.1) fr++;
  ok("Prism fringes a white shape's edges into colour", fr > 150, `${fr} coloured pixels`); }
{ const o = run({ psMode: 7 }, 1, A); let d = 0; for (let i = 0; i < A.n; i++) d = Math.max(d, Math.abs(o.r[i] - o.g[i]));
  ok("Dog Vision merges red and green", d < 1e-9, `split ${d}`); }
{ const blk = image(64, 36, () => [0, 0, 0]), o = run({ psMode: 8 }, 236, blk); let d = 0; for (let i = 0; i < blk.n; i++) d = Math.max(d, o.r[i], o.g[i], o.b[i]);
  const o2 = run({ psMode: 8 }, 236, A); let dark = 0; for (let i = 0; i < A.n; i++) if (o2.r[i] < A.r[i] - 1e-9 || o2.g[i] < A.g[i] - 1e-9 || o2.b[i] < A.b[i] - 1e-9) dark++;
  ok("Colour Shadow casts nothing from black and never darkens", d === 0 && dark === 0, `black ${d}, darkened ${dark}`); }
{ const { sliders } = compile(F, {}, { frame: 1 }); let bad = 0;
  for (let k = 0; k < 30; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd(); P.psMode = Math.round(P.psMode);
    const o = run(P, Math.floor(rnd() * 999), A); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok("range over 30 slider sets", bad === 0, `bad ${bad}`); }
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
