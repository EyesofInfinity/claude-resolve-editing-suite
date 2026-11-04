import { compile } from "../../tests/cpu/dctl.mjs";

const B = "build/", PR = "Develop Process.dctl", FS = "Develop Film Stock.dctl";
let s = 5;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function image(W, H, fill) {
  const n = W * H, A = { W, H, n, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let i = 0; i < n; i++) { const c = fill(i); A.r[i] = c[0]; A.g[i] = c[1]; A.b[i] = c[2]; }
  return A;
}
function run(file, P, frame, A) {
  const T = compile(B + file, P, { frame }).transform;
  const o = { r: new Float32Array(A.n), g: new Float32Array(A.n), b: new Float32Array(A.n) };
  const R = { d: A.r, w: A.W }, G = { d: A.g, w: A.W }, Bt = { d: A.b, w: A.W };
  for (let y = 0; y < A.H; y++) for (let x = 0; x < A.W; x++) {
    const c = T(A.W, A.H, x, y, R, G, Bt), i = y * A.W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z;
  }
  return o;
}
function one(file, P, c) {
  const A = image(1, 1, () => c), o = run(file, P, 1, A);
  return [o.r[0], o.g[0], o.b[0]];
}
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const f3 = c => c.map(v => v.toFixed(3)).join(" ");
const W = 240, H = 135;
let t = 7;
const trnd = () => ((t = (t * 1664525 + 1013904223) >>> 0) / 4294967296);
const A = image(W, H, () => { const v = trnd(); return [v, 0.9 * v, 0.7 * v + 0.2 * trnd()]; });
const clean = { pr: { pcHal: 0, pcGrain: 0 }, fs: { fsHal: 0, fsGrain: 0 } };

for (const [f, kind, n, off, cl] of [[PR, "pcKind", 7, { pcAmount: 0 }, clean.pr], [FS, "fsStock", 8, { fsAmount: 0 }, clean.fs]]) {
  const offAll = { ...off };
  for (const [nm, v] of Object.entries(compile(B + f, {}, { frame: 1 }).sliders)) if (!(nm in off)) offAll[nm] = v.hi;
  const o = run(f, offAll, 10, A);
  let d = 0;
  for (const k of ["r", "g", "b"]) for (let i = 0; i < A.n; i++) if (Math.abs(o[k][i] - A[k][i]) > 1e-9) d++;
  ok(`${f} off is identity`, d === 0, `differ ${d}`);
  for (let k = 0; k < n; k++) {
    const P = { [kind]: k };
    const a1 = run(f, P, 236, A), a2 = run(f, P, 236, A), b1 = run(f, P, 237, A);
    let rep = 0, mov = 0;
    for (let i = 0; i < A.n; i++) { if (a1.g[i] !== a2.g[i]) rep++; if (a1.g[i] !== b1.g[i]) mov++; }
    ok(`${f} ${kind} ${k}: repeat identical, grain moves the next frame`, rep === 0 && mov > A.n * 0.3, `repeat ${rep}, moved ${mov}`);
    const T = compile(B + f, { ...cl, [kind]: k }, { frame: 1 }).transform;
    let falls = 0, prev = -1;
    for (let i = 0; i < 256; i++) {
      const v = i / 255, c = T(1, 1, 0, 0, { d: [v], w: 1 }, { d: [v], w: 1 }, { d: [v], w: 1 });
      const L = 0.2126 * c.x + 0.7152 * c.y + 0.0722 * c.z; if (L < prev - 1e-7) falls++; prev = L;
    }
    ok(`${f} ${kind} ${k}: grey ramp never falls`, falls === 0, `falls ${falls}, ends ${prev.toFixed(3)}`);
  }
  const { sliders } = compile(B + f, {}, { frame: 1 });
  let bad = 0;
  for (let k = 0; k < 25; k++) {
    const P = {};
    for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd();
    P[kind] = Math.round(P[kind]);
    const o2 = run(f, P, Math.floor(rnd() * 999), A);
    for (const c of ["r", "g", "b"]) for (const v of o2[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; }
  }
  ok(`${f} range over 25 slider sets`, bad === 0, `bad ${bad}`);
}

const P = k => ({ ...clean.pr, pcKind: k }), S = k => ({ ...clean.fs, fsStock: k });
const split = c => Math.max(...c) - Math.min(...c);
const sat = c => (Math.max(...c) - Math.min(...c)) / Math.max(Math.max(...c), 1e-6);
let worst = 0;
for (const k of [1, 2, 6]) { worst = 0; for (let i = 0; i <= 20; i++) worst = Math.max(worst, split(one(PR, P(k), [i / 20, i / 20, i / 20]))); ok(`Process ${k}: greys stay grey`, worst < 1e-6, `split ${worst.toExponential(1)}`); }
const rndImg = image(64, 32, () => [trnd(), trnd(), trnd()]);
{ const o = run(PR, P(3), 1, rndImg); let d = 0; for (let i = 0; i < rndImg.n; i++) d = Math.max(d, Math.abs(o.r[i] - o.g[i]), Math.abs(o.g[i] - o.b[i])); ok("Process 3 Infrared Mono is grey", d < 1e-9, `split ${d}`); }
{ const o = run(FS, S(7), 1, rndImg); let d = 0; for (let i = 0; i < rndImg.n; i++) d = Math.max(d, Math.abs(o.r[i] - o.g[i]), Math.abs(o.g[i] - o.b[i])); ok("Stock 7 Silver Mono is grey", d < 1e-9, `split ${d}`); }
const SKY = [0.45, 0.65, 0.95], LEAF = [0.25, 0.55, 0.2], BLUE = [0.05, 0.1, 0.95], SKIN = [0.85, 0.62, 0.5];
{ const c = one(PR, P(0), SKY); ok("Two Strip: a blue sky turns teal (green at or over blue)", c[1] >= c[2] - 0.02, f3(c)); }
{ // no blue record: a deep blue loses its blue (blue no longer leads green) and keeps about its light (linear luminance)
  const c = one(PR, P(0), BLUE), lin = v => Math.pow(v, 2.4), Y = q => 0.2126 * lin(q[0]) + 0.7152 * lin(q[1]) + 0.0722 * lin(q[2]);
  ok("Two Strip: deep blue loses its blue, keeps its light", c[2] <= c[1] && Math.abs(Y(c) / Y(BLUE) - 1) < 0.35, `${f3(c)} luminance ${Y(BLUE).toFixed(3)} to ${Y(c).toFixed(3)}`); }
{ const c = one(PR, P(0), SKIN); ok("Two Strip: skin stays peach (red over green over blue)", c[0] > c[1] && c[1] > c[2], f3(c)); }
{ const c = one(PR, P(2), LEAF); ok("Infrared Colour: foliage turns red", c[0] > c[1] && c[0] > c[2], f3(c)); }
{ const c = one(PR, P(2), SKY); ok("Infrared Colour: the sky stays blue", c[2] > c[0] && c[2] > c[1], f3(c)); }
{ const l = one(PR, P(3), LEAF)[0], k = one(PR, P(3), SKY)[0]; ok("Infrared Mono: foliage brighter than the sky", l > k + 0.2, `leaf ${l.toFixed(3)} sky ${k.toFixed(3)}`); }
{ const c = one(PR, P(1), LEAF), i = LEAF; ok("Three Strip: richer colour than the input", sat(c) > sat(i), `${sat(i).toFixed(3)} to ${sat(c).toFixed(3)}`); }
{ const lo = one(PR, P(4), [0.15, 0.15, 0.15]), hi = one(PR, P(4), [0.85, 0.85, 0.85]);
  ok("Cross Slide: blue shadows, yellow highlights", lo[2] > lo[0] && hi[0] > hi[2] && hi[1] > hi[2], `${f3(lo)} / ${f3(hi)}`); }
{ const lo = one(PR, P(5), [0.1, 0.1, 0.1]), hi = one(PR, P(5), [0.9, 0.9, 0.9]); const sp = (hi[1] - lo[1]);
  ok("Cross Negative: flatter than the input", sp < 0.8 * 0.8, `0.1..0.9 spans ${sp.toFixed(3)} in green`); }
{ const c = one(PR, P(6), LEAF), i = LEAF; ok("Bleach Bypass: less colour than the input", sat(c) < sat(i), `${sat(i).toFixed(3)} to ${sat(c).toFixed(3)}`); }
{ const c = one(FS, S(4), [0.5, 0.5, 0.5]); ok("Faded Print: red over green in the mids (cyan dye faded)", c[0] > c[1] + 0.03, f3(c)); }
{ const lo = one(FS, S(1), [0.15, 0.15, 0.15]), hi = one(FS, S(1), [0.85, 0.85, 0.85]);
  ok("Tungsten Night: teal shadows, warm highlights", lo[2] > lo[0] && hi[0] > hi[2], `${f3(lo)} / ${f3(hi)}`); }
{ const v = sat(one(FS, S(2), LEAF)), p = sat(one(FS, S(3), LEAF)); ok("Vivid Slide more colour than Portrait Negative", v > p + 0.1, `${v.toFixed(3)} / ${p.toFixed(3)}`); }
{ const G = image(160, 90, () => [0.6, 0.6, 0.6]), o = run(FS, S(5), 1, G);
  const c = o.g[45 * 160 + 80], k = o.g[0]; ok("Home Movie: the gate's corners darker than the centre", k < 0.7 * c, `corner ${k.toFixed(3)} centre ${c.toFixed(3)}`); }
{ // Wear 0 moves nothing but grain; Wear 100 shifts the frame (gate weave) between frames. At 1080 rows, since the
  const N = image(64, 1080, () => [trnd(), trnd(), trnd()]);
  const Wn = { ...clean.fs, fsWear: 100 }, a = run(FS, Wn, 300, N), b = run(FS, Wn, 301, N), c0 = run(FS, clean.fs, 300, N), c1 = run(FS, clean.fs, 301, N);
  let dw = 0, d0 = 0; for (let i = 0; i < N.n; i++) { if (Math.abs(a.g[i] - b.g[i]) > 0.02) dw++; if (c0.g[i] !== c1.g[i]) d0++; }
  ok("Film Stock: Wear moves the frame, no Wear holds it", dw > N.n * 0.2 && d0 === 0, `wear moved ${dw} of ${N.n}, clean moved ${d0}`); }
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
