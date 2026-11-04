import { compile, runTransition } from "../../tests/cpu/dctl.mjs";

const F = "build/Develop Glow Dissolve.dctl", W = 320, H = 180, n = W * H;
let s = 31;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function img(fn) {
  const o = { w: W, h: H, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const c = fn(x, y), i = y * W + x; o.r[i] = c[0]; o.g[i] = c[1]; o.b[i] = c[2]; }
  return o;
}
const A = img((x, y) => { const v = 0.35 + 0.25 * Math.sin(x / 7) * Math.cos(y / 11) + (y < 40 ? 0.45 : 0) + (rnd() < 0.004 ? 0.6 : 0); return [Math.min(v, 1), Math.min(0.9 * v, 1), Math.min(0.7 * v + 0.05 * rnd(), 1)]; });
const B = img((x, y) => { const r = Math.hypot(x - W / 2, y - H / 3), v = 0.3 + 0.3 * Math.sin(r / 6) + (r < 25 ? 0.5 : 0); return [Math.min(0.5 * v, 1), Math.min(0.8 * v, 1), Math.min(v, 1)]; });
const K = img(() => [0, 0, 0]);
const diff = (o, q) => { let d = 0, m = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < n; i++) { const e = Math.abs(o[k][i] - q[k][i]); if (e > 1e-9) d++; m += e; } return { n: d, mean: +(m / (3 * n)).toFixed(4) }; };
const mean = o => { let m = 0; for (let i = 0; i < n; i++) m += 0.2126 * o.r[i] + 0.7152 * o.g[i] + 0.0722 * o.b[i]; return m / n; };
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const NAMES = ["Glow", "Rays", "Edge Rays", "Glint", "Flashbulbs", "Zap", "Orbs", "Lens Flare", "Light Wipe"];
const at = (st, p, a = A, b = B, P = {}) => runTransition(F, { gdStyle: st, ...P }, { progress: p, frame: 1 }, a, b);

for (let st = 0; st < 9; st++) {
  const N = NAMES[st];
  ok(`${N} starts exactly on the outgoing shot`, diff(at(st, 0), A).n === 0, JSON.stringify(diff(at(st, 0), A)));
  ok(`${N} ends exactly on the incoming shot`, diff(at(st, 1), B).n === 0, JSON.stringify(diff(at(st, 1), B)));
  const e0 = diff(at(st, 0.02), A).mean, e1 = diff(at(st, 0.98), B).mean;
  ok(`${N} eases out and in (within 0.005 at progress 0.02 and 0.98)`, e0 < 0.005 && e1 < 0.005, `${e0} ${e1}`);
  const lit = mean(at(st, st === 8 ? 0.45 : 0.5)), plain = mean(at(st, st === 8 ? 0.45 : 0.5, A, B, { gdLight: 0, gdWash: 0 }));
  ok(`${N} brightens the hand-over`, lit > plain + 0.03, `mean luma ${lit.toFixed(3)} against ${plain.toFixed(3)}`);
}
for (const st of [0, 1, 2, 3, 6]) {
  const a = diff(at(st, 0.4), at(st, 0.4, A, K)).n, b = diff(at(st, 0.6), at(st, 0.6, K, B)).n;
  ok(`${NAMES[st]} hands over in the middle (0.4 the outgoing only, 0.6 the incoming only)`, a === 0 && b === 0, `changed ${a}, ${b}`);
}
{
  const o = at(0, 0.5, A, B, { gdLight: 0, gdWash: 0 }), q = { r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (const k of ["r", "g", "b"]) for (let i = 0; i < n; i++) q[k][i] = 0.5 * A[k][i] + 0.5 * B[k][i];
  let m = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < n; i++) m = Math.max(m, Math.abs(o[k][i] - q[k][i]));
  ok("Light 0 is a plain dissolve", m < 1e-6, `max ${m.toExponential(2)}`);
}
for (const st of [0, 1, 2, 3, 6]) {
  const o = at(st, 0.5, K, K, { gdWash: 0 });
  ok(`${NAMES[st]} throws no light from a black picture`, mean(o) === 0, `mean ${mean(o)}`);
}
for (const st of [4, 5, 7, 8]) {
  const o = at(st, st === 8 ? 0.45 : 0.5, K, K, { gdWash: 0 });
  ok(`${NAMES[st]} brings its own light`, mean(o) > 0.004, `mean ${mean(o).toFixed(4)}`);
}
{
  const pt = img((x, y) => (x === 160 && y === 90 ? [1, 1, 1] : [0.05, 0.05, 0.05]));
  const o = at(3, 0.5, pt, pt, { gdPoints: 4, gdAngle: 0, gdWash: 0, gdThresh: 50, gdBlend: 0 });
  const a0 = 0.35, d = 8, v = (a) => o.g[Math.round(90 + d * Math.sin(a)) * W + Math.round(160 + d * Math.cos(a))];
  ok("Glint draws arms, dark between them", v(a0) > v(a0 + Math.PI / 4) + 0.05, `arm ${v(a0).toFixed(3)}, between ${v(a0 + Math.PI / 4).toFixed(3)}`);
}
{
  const pt = img((x, y) => (Math.hypot(x - 160, y - 110) < 5 ? [1, 1, 1] : [0.05, 0.05, 0.05]));
  const o = at(1, 0.5, pt, pt, { gdCX: 50, gdCY: 10, gdWash: 0, gdBlend: 0 });
  const far = o.g[140 * W + 160], near = o.g[80 * W + 160];
  ok("Rays stream away from the centre", far > near + 0.05, `beyond the dot ${far.toFixed(3)}, between it and the centre ${near.toFixed(3)}`);
}
{
  const z1 = at(5, 0.40, K, K, { gdWash: 0 }), z2 = at(5, 0.45, K, K, { gdWash: 0 });
  ok("Zap strikes again in a new place", diff(z1, z2).n > n * 0.05, `changed ${diff(z1, z2).n}`);
}
{
  const peakX = o => { let m = -1, mx = 0; for (let i = 0; i < n; i++) if (o.g[i] > m) { m = o.g[i]; mx = i % W; } return mx; };
  const x1 = peakX(at(7, 0.4, K, K, { gdAngle: 0, gdWash: 0 })), x2 = peakX(at(7, 0.6, K, K, { gdAngle: 0, gdWash: 0 }));
  ok("Lens Flare crosses along Angle", x2 > x1 + 20, `brightest at x ${x1}, then ${x2}`);
}
{
  const m2 = mean(at(4, 0.2, K, K, { gdWash: 0 })), m5 = mean(at(4, 0.5, K, K, { gdWash: 0 }));
  ok("Flashbulbs crowd around the cut", m5 > 1.5 * m2, `light at 0.2 ${m2.toFixed(4)}, at 0.5 ${m5.toFixed(4)}`);
}
{
  const o = at(8, 0.5, A, B, { gdAngle: 0, gdLight: 0 });
  let l = 0, r = 0;
  for (let y = 0; y < H; y++) { for (let x = 0; x < 30; x++) l += Math.abs(o.g[y * W + x] - B.g[y * W + x]); for (let x = W - 30; x < W; x++) r += Math.abs(o.g[y * W + x] - A.g[y * W + x]); }
  ok("Light Wipe leaves the incoming shot behind its band", l / (30 * H) < 0.002 && r / (30 * H) < 0.002, `left off B ${(l / (30 * H)).toFixed(4)}, right off A ${(r / (30 * H)).toFixed(4)}`);
}
{
  const { sliders } = compile(F, {}, { progress: 0.5 });
  let bad = 0;
  for (let k = 0; k < 30; k++) {
    const P = {};
    for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd();
    const o = runTransition(F, P, { progress: rnd(), frame: 1 }, A, B);
    for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; }
  }
  ok("range over 30 slider sets", bad === 0, `bad ${bad}`);
}
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
