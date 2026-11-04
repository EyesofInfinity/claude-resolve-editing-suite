import { compile, runTransition } from "../../tests/cpu/dctl.mjs";

const F = "build/Develop Push.dctl", W = 240, H = 135, n = W * H;
let s = 11;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function img(fn) {
  const o = { w: W, h: H, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const c = fn(x, y), i = y * W + x; o.r[i] = c[0]; o.g[i] = c[1]; o.b[i] = c[2]; }
  return o;
}
const A = img((x, y) => { const v = 0.5 + 0.4 * Math.sin(x / 6) * Math.cos(y / 9); return [v, 0.7 * v, 0.3 * v + 0.05 * rnd()]; });
const B = img((x, y) => { const r = Math.hypot(x - W / 2, y - H / 2), v = 0.5 + 0.4 * Math.sin(r / 5); return [0.2 * v, 0.6 * v, v * 0.9 + 0.05 * rnd()]; });
const diff = (o, q) => { let d = 0, m = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < n; i++) { const e = Math.abs(o[k][i] - q[k][i]); if (e > 1e-9) d++; m += e; } return { n: d, mean: +(m / (3 * n)).toFixed(4) }; };
const corr = (o, q) => { let sa = 0, sb = 0, sab = 0, saa = 0, sbb = 0; for (let i = 0; i < n; i++) { const a = o.g[i], b = q.g[i]; sa += a; sb += b; sab += a * b; saa += a * a; sbb += b * b; }
  const ma = sa / n, mb = sb / n; return (sab / n - ma * mb) / Math.sqrt((saa / n - ma * ma) * (sbb / n - mb * mb) + 1e-12); };
const detail = o => { let d = 0; for (let y = 1; y < H; y++) for (let x = 1; x < W; x++) { const i = y * W + x; d += Math.abs(o.g[i] - o.g[i - 1]) + Math.abs(o.g[i] - o.g[i - W]); } return d / ((H - 1) * (W - 1)); };
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const NAMES = ["Swish", "Film Whip", "Hyper Push", "Hyper Pull", "Flutter Cut"];
for (let st = 0; st < 5; st++) {
  const P = { puStyle: st }, at = p => runTransition(F, P, { progress: p, frame: 1 }, A, B);
  const o0 = at(0), o1 = at(1);
  ok(`${NAMES[st]} starts exactly on the outgoing shot`, diff(o0, A).n === 0, JSON.stringify(diff(o0, A)));
  ok(`${NAMES[st]} ends exactly on the incoming shot`, diff(o1, B).n === 0, JSON.stringify(diff(o1, B)));
  const e0 = at(0.02), e1 = at(0.98);
  ok(`${NAMES[st]} eases out of the outgoing and into the incoming (p 0.02 and 0.98 within 0.01)`,
     diff(e0, A).mean < 0.01 && diff(e1, B).mean < 0.01, `${diff(e0, A).mean} ${diff(e1, B).mean}`);
  if (st === 0 || st === 2 || st === 3) {
    const K = img(() => [0, 0, 0]);
    const a = diff(at(0.4), runTransition(F, P, { progress: 0.4, frame: 1 }, A, K)).n, b = diff(at(0.6), runTransition(F, P, { progress: 0.6, frame: 1 }, K, B)).n;
    ok(`${NAMES[st]} cuts on the middle (0.4 reads the outgoing only, 0.6 the incoming only)`, a === 0 && b === 0, `changed ${a}, ${b}`);
  }
}
const NA = img(() => [rnd(), rnd(), rnd()]), NB = img(() => [rnd(), rnd(), rnd()]);
for (const st of [0, 1, 2, 3]) {
  const at = (p, bl) => runTransition(F, { puStyle: st, puBlur: bl, puGlow: 0 }, { progress: p, frame: 1 }, NA, NB);
  const rm = detail(at(0.48, 70)) / detail(at(0.48, 0)), r1 = detail(at(0.1, 70)) / detail(at(0.1, 0));
  ok(`${NAMES[st]} blurs hardest near the cut`, rm < 0.5 && rm <= r1 + 0.01, `detail against Blur 0: 0.1 ${r1.toFixed(3)}, 0.48 ${rm.toFixed(3)}`);
}
{ const o = runTransition(F, { puStyle: 0, puBlur: 0, puGlow: 0 }, { progress: 0.3 }, A, B), d = detail(o), dA = detail(A);
  ok("Swish at Blur 0 stays sharp", Math.abs(d - dA) < 0.15 * dA, `${dA.toFixed(4)} vs ${d.toFixed(4)}`); }
{ const o = runTransition(F, { puStyle: 1, puBlur: 0, puGlow: 0 }, { progress: 0.5 }, A, B);
  let dark = 0, red = 0; for (let i = 0; i < n; i++) { if (o.g[i] < 0.06 && o.b[i] < 0.06) dark++; if (o.r[i] > 0.35 && o.g[i] < 0.25) red++; }
  ok("Film Whip's frame line and red edge cross the frame mid-way", dark > 0.02 * n && red > 0.002 * n, `dark ${dark}, red ${red}`); }
{ const o = runTransition(F, { puStyle: 2, puBlur: 0, puGlow: 0 }, { progress: 0.3 }, A, B), c = (H / 2 | 0) * W + (W / 2 | 0);
  ok("Hyper Push zooms about the centre", Math.abs(o.g[c] - A.g[c]) < 0.03, `${o.g[c].toFixed(3)} vs ${A.g[c].toFixed(3)}`); }
{ let sa = 0, sb = 0; const seen = [];
  for (let k = 1; k < 7; k++) { const o = runTransition(F, { puStyle: 4, puGlow: 0, puBlur: 0, puTravel: 0 }, { progress: (k + 0.5) / 8 }, A, B);
    const w = corr(o, A) > corr(o, B) ? "A" : "B"; seen.push(w); if (w === "A") sa++; else sb++; }
  const seen2 = []; for (let k = 1; k < 7; k++) { const o = runTransition(F, { puStyle: 4, puGlow: 0, puBlur: 0, puTravel: 0, puSeed: 37 }, { progress: (k + 0.5) / 8 }, A, B); seen2.push(corr(o, A) > corr(o, B) ? "A" : "B"); }
  const sw = q => q.slice(1).filter((v, i) => v !== q[i]).length;
  ok("Flutter Cut stutters between both shots (at least 3 switches in beats 1 to 6, any seed)", sa >= 2 && sb >= 2 && sw(seen) >= 3 && sw(seen2) >= 3,
     `beats 1 to 6: ${seen.join("")}, seed 37: ${seen2.join("")}`); }
{ const NA = img(() => [rnd(), rnd(), rnd()]), NB = img(() => [rnd(), rnd(), rnd()]);
  const o = runTransition(F, { puStyle: 3, puTravel: 100, puBlur: 0, puGlow: 0 }, { progress: 0.499 }, NA, NB); let same = 0, tot = 0;
  const col0 = new Set(); for (let y = 0; y < H; y++) col0.add(NA.g[y * W]);
  for (let y = 0; y < H; y++) for (let x = W - 24; x < W; x++) { tot++; if (col0.has(o.g[y * W + x])) same++; }
  const o2 = runTransition(F, { puStyle: 0, puTravel: 100, puBlur: 0, puGlow: 0 }, { progress: 0.49 }, NA, NB); let flat = 0;
  for (let i = 0; i < n; i++) if (col0.has(o2.g[i])) flat++;
  ok("far samples mirror instead of clamping", same < 0.1 * tot && flat < 20, `Pull right columns from column 0: ${same} of ${tot}; Swish pixels from column 0: ${flat} of ${n}`); }
{ const { sliders } = compile(F, {}, { frame: 1 }); let bad = 0;
  for (let k = 0; k < 30; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd(); P.puStyle = Math.round(P.puStyle);
    const o = runTransition(F, P, { progress: rnd(), frame: 1 }, A, B);
    for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok("range over 30 slider sets", bad === 0, `bad ${bad}`); }
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
