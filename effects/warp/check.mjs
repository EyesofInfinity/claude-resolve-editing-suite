import { compile, runTransition } from "../../tests/cpu/dctl.mjs";

const F = "build/Develop Warp.dctl", W = 240, H = 135, n = W * H;
let s = 23;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function img(fn) {
  const o = { w: W, h: H, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const c = fn(x, y), i = y * W + x; o.r[i] = c[0]; o.g[i] = c[1]; o.b[i] = c[2]; }
  return o;
}
const A = img((x, y) => { const v = 0.5 + 0.4 * Math.sin(x / 6) * Math.cos(y / 9); return [v, 0.7 * v, 0.3 * v + 0.05 * rnd()]; });
const B = img((x, y) => { const r = Math.hypot(x - W / 2, y - H / 2), v = 0.5 + 0.4 * Math.sin(r / 5); return [0.2 * v, 0.6 * v, v * 0.9 + 0.05 * rnd()]; });
const K = img(() => [0, 0, 0]);
const diff = (o, q) => { let d = 0, m = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < n; i++) { const e = Math.abs(o[k][i] - q[k][i]); if (e > 1e-9) d++; m += e; } return { n: d, mean: +(m / (3 * n)).toFixed(4) }; };
const detail = o => { let d = 0; for (let y = 1; y < H; y++) for (let x = 1; x < W; x++) { const i = y * W + x; d += Math.abs(o.g[i] - o.g[i - 1]) + Math.abs(o.g[i] - o.g[i - W]); } return d / ((H - 1) * (W - 1)); };
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const NAMES = ["Defocus", "Prism", "Melt", "Smoke", "Vortex", "Ripple"];
for (let st = 0; st < 6; st++) {
  const at = (p, a = A, b = B, P = {}) => runTransition(F, { wpStyle: st, ...P }, { progress: p, frame: 1 }, a, b);
  ok(`${NAMES[st]} starts exactly on the outgoing shot`, diff(at(0), A).n === 0, JSON.stringify(diff(at(0), A)));
  ok(`${NAMES[st]} ends exactly on the incoming shot`, diff(at(1), B).n === 0, JSON.stringify(diff(at(1), B)));
  const e0 = diff(at(0.02), A).mean, e1 = diff(at(0.98), B).mean;
  ok(`${NAMES[st]} eases out and in (within 0.005 at progress 0.02 and 0.98)`, e0 < 0.005 && e1 < 0.005, `${e0} ${e1}`);
}
for (const [st, p0, p1] of [[0, 0.3, 0.7], [1, 0.33, 0.67], [4, 0.4, 0.6], [5, 0.36, 0.64]]) {
  const P = { wpStyle: st }, a = diff(runTransition(F, P, { progress: p0 }, A, B), runTransition(F, P, { progress: p0 }, A, K)).n;
  const b = diff(runTransition(F, P, { progress: p1 }, A, B), runTransition(F, P, { progress: p1 }, K, B)).n;
  ok(`${NAMES[st]} crosses in the middle (${p0} the outgoing only, ${p1} the incoming only)`, a === 0 && b === 0, `changed ${a}, ${b}`);
}
{ const NA = img(() => [rnd(), rnd(), rnd()]), NB = img(() => [rnd(), rnd(), rnd()]), at = p => runTransition(F, { wpStyle: 0 }, { progress: p }, NA, NB);
  const dm = detail(at(0.5)) / detail(NA), d1 = detail(at(0.03)) / detail(NA);
  ok("Defocus is softest on the cut", dm < 0.2 && d1 > dm * 2, `detail at 0.03 ${d1.toFixed(3)}, at 0.5 ${dm.toFixed(3)}`); }
{ const pt = img((x, y) => (Math.hypot(x - 120, y - 67) < 2 ? [1, 1, 1] : [0.1, 0.1, 0.1]));
  const g0 = runTransition(F, { wpStyle: 0, wpGlow: 0 }, { progress: 0.2 }, pt, pt), g1 = runTransition(F, { wpStyle: 0, wpGlow: 100 }, { progress: 0.2 }, pt, pt);
  let s0 = 0, s1 = 0; for (let y = 55; y < 80; y++) for (let x = 108; x < 133; x++) { s0 += g0.g[y * W + x]; s1 += g1.g[y * W + x]; }
  ok("Defocus: Glow opens a highlight into a brighter disc", s1 > 1.15 * s0, `${s0.toFixed(1)} to ${s1.toFixed(1)}`); }
const WH = img(() => [1, 1, 1]);
for (const st of [2, 3]) {
  const sh = [0.1, 0.3, 0.5, 0.7, 0.9].map(p => { const o = runTransition(F, { wpStyle: st, wpGlow: 0 }, { progress: p }, K, WH); let m = 0; for (let i = 0; i < n; i++) m += o.g[i]; return m / n; });
  ok(`${NAMES[st]}: the incoming shot's share grows`, sh.every((v, i) => i === 0 || v > sh[i - 1]), sh.map(v => v.toFixed(3)).join(" "));
}
{ const o = runTransition(F, { wpStyle: 2, wpGlow: 0 }, { progress: 0.4 }, K, WH); let t = 0, b = 0; for (let x = 0; x < W; x++) { t += o.g[5 * W + x]; b += o.g[(H - 5) * W + x]; }
  ok("Melt drips from the top", t > b + 0.3 * W, `top ${(t / W).toFixed(3)}, bottom ${(b / W).toFixed(3)}`); }
{ const o = runTransition(F, { wpStyle: 3, wpGlow: 0 }, { progress: 0.4 }, K, WH); let t = 0, b = 0; for (let y = 0; y < 20; y++) for (let x = 0; x < W; x++) { t += o.g[y * W + x]; b += o.g[(H - 1 - y) * W + x]; }
  ok("Smoke rises from the bottom", b > t, `top ${(t / (20 * W)).toFixed(3)}, bottom ${(b / (20 * W)).toFixed(3)}`); }
{ const o = runTransition(F, { wpStyle: 4 }, { progress: 0.3 }, A, B), c = (H / 2 | 0) * W + (W / 2 | 0);
  ok("Vortex turns about the centre", Math.abs(o.g[c] - A.g[c]) < 0.03, `${o.g[c].toFixed(3)} vs ${A.g[c].toFixed(3)}`); }
{ const o0 = runTransition(F, { wpStyle: 5, wpAmount: 0, wpGlow: 0 }, { progress: 0.3 }, A, B), o1 = runTransition(F, { wpStyle: 5, wpAmount: 100, wpGlow: 0 }, { progress: 0.3 }, A, B);
  let d0 = 0; for (let i = 0; i < n; i++) d0 = Math.max(d0, Math.abs(o0.g[i] - A.g[i]));
  ok("Ripple: Amount 0 leaves the picture, Amount 100 bends it", d0 < 1e-5 && diff(o1, A).mean > 0.005, `Amount 0 off by ${d0.toExponential(1)}, Amount 100 mean ${diff(o1, A).mean}`); }
{ const VS = img((x) => { const v = (x >> 3) & 1 ? 0.9 : 0.1; return [v, v, v]; }), HS = img((x, y) => { const v = (y >> 3) & 1 ? 0.9 : 0.1; return [v, v, v]; });
  const a = runTransition(F, { wpStyle: 4 }, { progress: 0.4999 }, VS, HS), b = runTransition(F, { wpStyle: 4 }, { progress: 0.5001 }, VS, HS);
  ok("Vortex is continuous through the cut", diff(a, b).mean < 0.02, `mean change across 0.5: ${diff(a, b).mean}`); }
{ const SW = 64, SH = 1080, BL = { w: SW, h: SH, r: new Float32Array(SW * SH), g: new Float32Array(SW * SH), b: new Float32Array(SW * SH) };
  const o = runTransition(F, { wpStyle: 2 }, { progress: 0.3 }, BL, BL); let jump = 0;
  for (let x = 0; x < SW; x += 4) for (let y = 1; y < SH; y++) jump = Math.max(jump, Math.abs(o.g[y * SW + x] - o.g[(y - 1) * SW + x]));
  ok("Melt's wet lip has no hard edge", jump < 0.15, `largest step between neighbouring rows ${jump.toFixed(3)}`); }
{ const { sliders } = compile(F, {}, { frame: 1 }); let bad = 0;
  for (let k = 0; k < 30; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd(); P.wpStyle = Math.round(P.wpStyle);
    const o = runTransition(F, P, { progress: rnd(), frame: 1 }, A, B); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok("range over 30 slider sets", bad === 0, `bad ${bad}`); }
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
