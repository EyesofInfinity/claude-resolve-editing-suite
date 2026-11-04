import { compile } from "../../tests/cpu/dctl.mjs";

const F = "build/Develop Sky.dctl";
let s = 19;
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
const NAMES = ["Aurora", "Night Sky", "Moon", "Rain", "Snow", "Dust", "Sparkles", "Caustics", "Fog"];
const W = 320, H = 1080;
const night = image(W, H, (i, x, y) => [0.03, 0.05, 0.12 + 0.05 * y / H]);
const bright = image(W, H, (i, x, y) => { const v = 0.55 + 0.4 * Math.sin(x / 9) * Math.sin(y / 13); return [v, 0.95 * v, 0.8 * v]; });
const busy = image(W, H, () => { const v = rnd() * 0.3; return [v, v, v]; });
const diffN = (o, A, th) => { let d = 0; for (let i = 0; i < A.n; i++) if (Math.abs(o.g[i] - A.g[i]) > th || Math.abs(o.r[i] - A.r[i]) > th || Math.abs(o.b[i] - A.b[i]) > th) d++; return d; };
{ const P = { skAmount: 0 }; for (const [nm, v] of Object.entries(compile(F, {}, { frame: 1 }).sliders)) if (nm !== "skAmount") P[nm] = v.hi;
  const o = run(P, 10, bright); let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < bright.n; i++) if (o[k][i] !== bright[k][i]) d++;
  ok("off is identity", d === 0, `differ ${d}`); }
for (let m = 0; m < 9; m++) {
  const A = [0, 1, 2].includes(m) ? night : bright;
  const a1 = run({ skMode: m }, 236, A), a2 = run({ skMode: m }, 236, A), b1 = run({ skMode: m }, 242, A);
  let rep = 0, mov = 0; for (let i = 0; i < A.n; i++) { if (a1.g[i] !== a2.g[i]) rep++; if (Math.abs(a1.g[i] - b1.g[i]) > 1e-4) mov++; }
  const moves = m !== 2;
  ok(`${NAMES[m]}: repeat identical, ${moves ? "moves 6 frames on" : "holds (the moon does not move)"}`, rep === 0 && (moves ? mov > 50 : mov === 0), `repeat ${rep}, moved ${mov}`);
}
{ const o = run({ skMode: 1 }, 236, busy), o2 = run({ skMode: 1 }, 236, night);
  ok("Night Sky: at most 2 visible pixels on busy texture, stars in a flat dark sky", diffN(o, busy, 0.02) <= 2 && diffN(o2, night, 0.03) > 300,
     `on texture ${diffN(o, busy, 0.02)} over 0.02 (${diffN(o, busy, 0.004)} over 0.004), in sky ${diffN(o2, night, 0.03)}`);
  const o3 = run({ skMode: 1, skMask: 0 }, 236, busy); ok("Night Sky at Sky Mask 0 lays stars everywhere", diffN(o3, busy, 0.03) > 300, `${diffN(o3, busy, 0.03)}`); }
{ const o = run({ skMode: 0, skY: 55 }, 236, night); let above = 0, below = 0;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const i = y * W + x, d = o.g[i] - night.g[i]; if (y < 0.3 * H && d > 0.02) above++; if (y > 0.7 * H && d > 0.002) below++; }
  ok("Aurora above its edge, none well below", above > 0.2 * W * 0.3 * H && below === 0, `lit above ${above}, below ${below}`); }
{ const mean = (o, A) => { let m = 0; for (let i = 0; i < A.n; i++) m += o.g[i] - A.g[i]; return m / A.n; };
  const full = mean(run({ skMode: 2, skDensity: 100, skX: 50 }, 1, night), night), cres = mean(run({ skMode: 2, skDensity: 5, skX: 50 }, 1, night), night);
  ok("Moon: full brighter than a crescent", full > 2 * cres && cres > 0, `full ${full.toFixed(4)}, crescent ${cres.toFixed(4)}`); }
{ const flat = image(W, H, () => [0.6, 0.35, 0.25]), o = run({ skMode: 3 }, 236, flat); let lo = 0, hi = 0;
  for (let i = 0; i < flat.n; i++) { if (o.r[i] < 0.6 - 1e-3) lo++; if (o.g[i] > 0.36) hi++; }
  ok("Rain: the scene dulled, streaks across it", lo > 0.8 * flat.n && hi > 100, `dulled ${lo}, streak pixels ${hi}`); }
{ const o = run({ skMode: 4 }, 236, night); ok("Snow: flakes on a dark picture", diffN(o, night, 0.2) > 200, `${diffN(o, night, 0.2)} flake pixels`); }
for (const m of [5, 6]) { const dk = image(W, H, () => [0.08, 0.08, 0.08]), o = run({ skMode: m }, 236, dk), o2 = run({ skMode: m }, 236, bright);
  ok(`${NAMES[m]}: none in the dark, some in the light`, diffN(o, dk, 1e-5) === 0 && diffN(o2, bright, 0.03) > 50, `dark ${diffN(o, dk, 1e-5)}, light ${diffN(o2, bright, 0.03)}`); }
{ const o = run({ skMode: 7 }, 236, bright); let dk = 0; for (let i = 0; i < bright.n; i++) if (o.g[i] < bright.g[i] - 1e-5) dk++;
  ok("Caustics only add light", dk === 0 && diffN(o, bright, 0.02) > 0.05 * bright.n, `darkened ${dk}, lit ${diffN(o, bright, 0.02)}`); }
{ const o = run({ skMode: 8 }, 236, bright); let top = 0, bot = 0;
  for (let y = 0; y < 100; y++) for (let x = 0; x < W; x++) { top += Math.abs(o.g[y * W + x] - bright.g[y * W + x]); bot += Math.abs(o.g[(H - 1 - y) * W + x] - bright.g[(H - 1 - y) * W + x]); }
  ok("Fog lies low (more at the bottom than the top)", bot > 4 * top, `top ${top.toFixed(1)}, bottom ${bot.toFixed(1)}`); }
{ const { sliders } = compile(F, {}, { frame: 1 }); let bad = 0; const small = image(160, 270, () => [rnd(), rnd(), rnd()]);
  for (let k = 0; k < 30; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd(); P.skMode = Math.round(P.skMode);
    const o = run(P, Math.floor(rnd() * 999), small); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok("range over 30 slider sets", bad === 0, `bad ${bad}`); }
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
