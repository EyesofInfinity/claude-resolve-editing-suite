import { compile, runTransition } from "../../tests/cpu/dctl.mjs";

const B = "build/";
const W = 240, H = 135;
function chart(seed) {
  const n = W * H, img = { w: W, h: H, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  let s = seed;
  const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = y * W + x, v = rnd();
    img.r[i] = v; img.g[i] = v * 0.9 + 0.05 * rnd(); img.b[i] = v * 0.8 + 0.1 * rnd();
  }
  return img;
}
function runT(file, params, env, img) {
  const T = compile(B + file, params, env).transform;
  const o = { r: new Float32Array(W * H), g: new Float32Array(W * H), b: new Float32Array(W * H) };
  const R = { d: img.r, w: W }, G = { d: img.g, w: W }, Bt = { d: img.b, w: W };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const c = T(W, H, x, y, R, G, Bt), i = y * W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z;
  }
  return o;
}
const q = v => Math.round(Math.max(0, Math.min(1, v)) * 1023);
function diffCount(a, b) {
  let n = 0, mx = 0;
  for (const k of ["r", "g", "b"]) for (let i = 0; i < a[k].length; i++) {
    const d = Math.abs(q(a[k][i]) - q(b[k][i])); if (d) n++; if (d > mx) mx = d;
  }
  return { n, mx };
}
function hash01(x, y, z) {                       // the harness's exact uint hash (tests/cpu/dctl.mjs)
  const M = Math.imul;
  x = (M(x, 1664525) + 1013904223) >>> 0; y = (M(y, 1664525) + 1013904223) >>> 0; z = (M(z, 1664525) + 1013904223) >>> 0;
  x = (x + M(y, z)) >>> 0; y = (y + M(z, x)) >>> 0; z = (z + M(x, y)) >>> 0;
  x = (x ^ (x >>> 16)) >>> 0; y = (y ^ (y >>> 16)) >>> 0; z = (z ^ (z >>> 16)) >>> 0;
  x = (x + M(y, z)) >>> 0; y = (y + M(z, x)) >>> 0; z = (z + M(x, y)) >>> 0;
  return (x >>> 8) / 16777216;
}
const luma = (o, i) => 0.2126 * o.r[i] + 0.7152 * o.g[i] + 0.0722 * o.b[i];
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };

const A = chart(1), Bm = chart(2);
let d = diffCount(runT("Develop Pixel Sort.dctl", { psAmount: 0 }, { frame: 1 }, A), A);
ok("pixel sort off is identity", d.n === 0, JSON.stringify(d));

const ps = runT("Develop Pixel Sort.dctl", { psLength: 30, psGrit: 0, psDither: 0 }, { frame: 1 }, A);
let outside = 0, falls = 0, moved = 0, sumIn = 0, sumOut = 0;
const L = Math.trunc(Math.pow(2, 2 + 7 * (30 - 1) / 99) * H / 1080) + 2;     // the DCTL's run grid
for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
  const i = y * W + x, l = luma(A, i);
  if (l < 0.45) { if (Math.abs(ps.g[i] - A.g[i]) > 1e-6) outside++; continue; }
  sumIn += l; sumOut += luma(ps, i);
  if (Math.abs(ps.g[i] - A.g[i]) > 1e-6) moved++;
  const off = Math.trunc(hash01(y + 1, 17, 3) * L);                    // the DCTL's per-row grid offset
  if ((x + off) % L !== 0 && x > 0 && luma(A, i - 1) >= 0.45 && luma(ps, i) < luma(ps, i - 1) - 1e-9) falls++;
}
ok("pixel sort leaves pixels outside the band", outside === 0, `changed ${outside}`);
ok("pixel sort moves pixels inside the band", moved > 100, `moved ${moved}`);
ok("pixel sort runs rise along the direction", falls === 0, `falls inside a run ${falls} (run grid ${L} px)`);
ok("pixel sort keeps the light of the band", Math.abs(sumIn - sumOut) / sumIn < 0.02, `in ${sumIn.toFixed(1)} out ${sumOut.toFixed(1)}`);

for (const st of [0, 1, 2, 3, 4, 5]) {
  const o1 = runTransition(B + "Develop Glitch.dctl", { gtStyle: st }, { progress: 1 }, A, Bm);
  ok(`glitch style ${st} ends on the incoming shot`, diffCount(o1, Bm).n === 0, JSON.stringify(diffCount(o1, Bm)));
  if (st) {
    const o0 = runTransition(B + "Develop Glitch.dctl", { gtStyle: st }, { progress: 0 }, A, Bm);
    ok(`glitch style ${st} starts on the outgoing shot`, diffCount(o0, A).n === 0, JSON.stringify(diffCount(o0, A)));
  }
}
for (const [k, p] of [[0, 0.1], [1, 0.3], [2, 0.5], [3, 0.7], [4, 0.9]]) {
  const o = runTransition(B + "Develop Glitch.dctl", { gtStyle: 0 }, { progress: p }, A, Bm);
  const dd = diffCount(o, Bm);
  ok(`snap step ${k} ${k % 2 === 0 && k ? "clean" : "glitched"}`, (k === 2 || k === 4) ? dd.n === 0 : dd.n > 1000, JSON.stringify(dd));
}

{
  const o = runTransition(B + "Develop Glitch.dctl", { gtStyle: 4, gtDither: 0, gtGrit: 0 }, { progress: 0.01 }, A, Bm);
  let d = 0;
  for (let i = 0; i < A.g.length; i++) d += Math.abs(o.g[i] - A.g[i]) / A.g.length;
  let base = 0;                                    // two unrelated frames: the scale of a full jump
  for (let i = 0; i < A.g.length; i++) base += Math.abs(Bm.g[i] - A.g[i]) / A.g.length;
  ok("channel change starts with a small roll", d < 0.25 * base, `mean change ${d.toFixed(3)} against two unrelated frames ${base.toFixed(3)}`);
}

let s = 7;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
for (const f of ["Develop Glitch.dctl", "Develop Pixel Sort.dctl"]) {
  const { sliders } = compile(B + f, {}, { frame: 1 });
  let bad = 0;
  for (let k = 0; k < 30; k++) {
    const P = {};
    for (const [n, v] of Object.entries(sliders)) P[n] = v.lo + (v.hi - v.lo) * rnd();
    for (const n of ["gtStyle", "psDir"]) if (n in P) P[n] = Math.round(P[n]);
    const o = f.includes("Glitch") ? runTransition(B + f, P, { progress: rnd(), frame: 5 }, A, Bm) : runT(f, P, { frame: Math.floor(rnd() * 999) }, A);
    for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; }
  }
  ok(`${f} range over 30 slider sets`, bad === 0, `bad ${bad}`);
}
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
