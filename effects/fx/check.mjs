import { compile } from "../../tests/cpu/dctl.mjs";

const B = "build/", W = 240, H = 135;
let s = 3;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
const n = W * H, A = { r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
for (let i = 0; i < n; i++) { const v = rnd(); A.r[i] = v; A.g[i] = 0.9 * v; A.b[i] = 0.7 * v + 0.2 * rnd(); }
function run(file, P, frame) {
  const T = compile(B + file, P, { frame }).transform;
  const o = { r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  const R = { d: A.r, w: W }, G = { d: A.g, w: W }, Bt = { d: A.b, w: W };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const c = T(W, H, x, y, R, G, Bt), i = y * W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z; }
  return o;
}
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
for (const [f, off] of [["Develop Glow FX.dctl", { gfAmount: 0 }], ["Develop Glint.dctl", { gnAmount: 0 }], ["Develop Zap.dctl", { zpAmount: 0 }], ["Develop Rays.dctl", { ryAmount: 0 }], ["Develop Kaleido.dctl", { kdMix: 0 }]]) {
  const o = run(f, off, 10);
  let d = 0;
  for (const k of ["r", "g", "b"]) for (let i = 0; i < n; i++) if (Math.abs(o[k][i] - A[k][i]) > 1e-9) d++;
  ok(`${f} off is identity`, d === 0, `differ ${d}`);
  const mv = f.includes("Glow") ? { gfMode: 4 } : f.includes("Rays") ? { ryMode: 2, ryPeriod: 0.5 } : f.includes("Kaleido") ? { kdSpin: 90 } : {};
  const a1 = run(f, mv, 236), a2 = run(f, mv, 236), b1 = run(f, mv, 237);
  let rep = 0, mov = 0;
  for (let i = 0; i < n; i++) { if (a1.g[i] !== a2.g[i]) rep++; if (a1.g[i] !== b1.g[i]) mov++; }
  ok(`${f} repeat identical, next frame moves`, rep === 0 && mov > n * 0.05, `repeat ${rep}, moved ${mov}`);
  const { sliders } = compile(B + f, {}, { frame: 1 });
  let bad = 0;
  for (let k = 0; k < 25; k++) {
    const P = {};
    for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd();
    const o2 = run(f, P, Math.floor(rnd() * 999));
    for (const c of ["r", "g", "b"]) for (const v of o2[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; }
  }
  ok(`${f} range over 25 slider sets`, bad === 0, `bad ${bad}`);
}
{
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const i = y * W + x; A.r[i] = A.g[i] = A.b[i] = (x + y) / (W + H); }
  const jumps = fr => { const o = run("Develop Kaleido.dctl", { kdMode: 0, kdSpin: -90 }, fr); let j = 0;
    for (let y = 0; y < H; y++) for (let x = 1; x < W; x++) if (Math.abs(o.g[y * W + x] - o.g[y * W + x - 1]) > 0.15) j++; return j; };
  const early = jumps(720), late = jumps(1440);
  ok("kaleido radial keeps its mirror at negative spin, late", late <= early + 5, `jumps early ${early}, late ${late}`);
}
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
