import { compile } from "../../tests/cpu/dctl.mjs";

const F = "build/Develop Art.dctl";
let s = 17;
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
const NAMES = ["Halftone", "Colour Halftone", "Halftone Rings", "Crosshatch", "Etching", "Sketch", "Cartoon", "Mosaic", "Scatter", "Posterize"];
const W = 240, H = 135;
const A = image(W, H, (i, x, y) => { const d = Math.hypot(x - 80, y - 60); const v = 0.1 + 0.6 * x / W + 0.3 * Math.exp(-d * d / 500) + 0.04 * rnd(); return [Math.min(1, v), 0.9 * v, 0.7 * v]; });
const flat = v => image(160, 90, () => [v, v, v]);
const mean = o => { let m = 0; for (let i = 0; i < o.g.length; i++) m += 0.2126 * o.r[i] + 0.7152 * o.g[i] + 0.0722 * o.b[i]; return m / o.g.length; };
{ const P = { arAmount: 0 }; for (const [nm, v] of Object.entries(compile(F, {}, { frame: 1 }).sliders)) if (nm !== "arAmount") P[nm] = v.hi;
  const o = run(P, 10, A); let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < A.n; i++) if (o[k][i] !== A[k][i]) d++;
  ok("off is identity", d === 0, `differ ${d}`); }
for (let m = 0; m < 10; m++) {
  const a1 = run({ arMode: m }, 240, A), a2 = run({ arMode: m }, 240, A), b1 = run({ arMode: m }, 252, A);
  const z1 = run({ arMode: m, arBoil: 0 }, 240, A), z2 = run({ arMode: m, arBoil: 0 }, 600, A);
  let rep = 0, mov = 0, still = 0;
  for (let i = 0; i < A.n; i++) { if (a1.g[i] !== a2.g[i]) rep++; if (a1.g[i] !== b1.g[i]) mov++; if (z1.g[i] !== z2.g[i]) still++; }
  const boils = [3, 5, 8].includes(m);
  ok(`${NAMES[m]}: repeat identical, Boil 0 holds, ${boils ? "boils" : "holds without time"}`, rep === 0 && still === 0 && (boils ? mov > A.n * 0.05 : mov === 0),
     `repeat ${rep}, Boil 0 moved ${still}, 12 frames on moved ${mov}`);
}
for (const m of [0, 1, 2, 3, 4]) {
  const ms = [0, 0.25, 0.5, 0.75, 1].map(v => mean(run({ arMode: m, arColour: 0, arBoil: 0 }, 1, flat(v))));
  const up = ms.every((v, i) => i === 0 || v > ms[i - 1] - 1e-6);
  ok(`${NAMES[m]}: lighter grey, lighter print; white is bare paper`, up && ms[4] > 0.9 && ms[0] < 0.35, ms.map(v => v.toFixed(3)).join(" "));
}
{ const o = run({ arMode: 0, arColour: 0, arLevel: 50 }, 1, flat(0.5)); let ink = 0; for (let i = 0; i < o.g.length; i++) if (o.g[i] < 0.5) ink++;
  ok("Halftone: mid grey prints about half ink", Math.abs(ink / o.g.length - 0.5) < 0.12, `${(100 * ink / o.g.length).toFixed(1)}% ink`); }
{ const o = run({ arMode: 1 }, 1, image(160, 90, () => [0.85, 0.15, 0.1])), mr = o.r.reduce((a, b) => a + b) / o.r.length, mg = o.g.reduce((a, b) => a + b) / o.g.length, mb = o.b.reduce((a, b) => a + b) / o.b.length;
  ok("Colour Halftone: red prints red", mr > mg + 0.25 && mr > mb + 0.25, `${mr.toFixed(3)} ${mg.toFixed(3)} ${mb.toFixed(3)}`); }
{ const G = flat(0.4), o = run({ arMode: 2, arPaper: 0 }, 1, G); let d = 0; for (let y = 0; y < 90; y++) for (let k = 1; k < 80; k++) d = Math.max(d, Math.abs(o.g[y * 160 + 80 - k] - o.g[y * 160 + 79 + k]));
  ok("Halftone Rings: symmetric about the centre", d < 0.02, `largest left-right difference ${d.toFixed(4)}`); }
{ for (const m of [5, 6]) { const o = run({ arMode: m, arBoil: 0, arColour: 0 }, 1, flat(0.7)), st = run({ arMode: m, arBoil: 0, arColour: 0 }, 1, image(160, 90, (i, x) => (x < 80 ? [0.85, 0.85, 0.85] : [0.15, 0.15, 0.15])));
  let mn = 1, line = 1; for (let i = 0; i < o.g.length; i++) mn = Math.min(mn, o.g[i]); for (let y = 10; y < 80; y++) line = Math.min(line, st.g[y * 160 + 80]);
  ok(`${NAMES[m]}: no line on a flat picture, a dark line on a step`, mn > 0.45 && line < 0.35, `flat min ${mn.toFixed(3)}, step line ${line.toFixed(3)}`); } }
{ const o = run({ arMode: 6, arLevel: 50 }, 1, image(256, 8, (i, x) => [x / 255, x / 255, x / 255])); const lv = new Set(); for (let x = 20; x < 236; x++) lv.add(o.g[4 * 256 + x].toFixed(3));
  ok("Cartoon: the ramp cut to 5 to 7 steps", lv.size >= 5 && lv.size <= 7, `${lv.size} levels`); }
{ const o = run({ arMode: 7 }, 1, flat(0.6)); let gr = 0; for (let i = 0; i < o.g.length; i++) if (o.g[i] < 0.5) gr++;
  ok("Mosaic: grout lines between tiles", gr > 0.03 * o.g.length && gr < 0.4 * o.g.length, `${(100 * gr / o.g.length).toFixed(1)}% grout`); }
{ const N = image(W, H, () => [rnd(), rnd(), rnd()]), o = run({ arMode: 8 }, 1, N); const m1 = mean(N), m2 = mean(o); let d = 0; for (let i = 0; i < N.n; i++) if (o.g[i] !== N.g[i]) d++;
  ok("Scatter: pixels thrown, colour kept", Math.abs(m1 - m2) < 0.01 && d > 0.8 * N.n, `mean ${m1.toFixed(4)} to ${m2.toFixed(4)}, moved ${d}`); }
{ const R = image(256, 16, (i, x) => [x / 255, x / 255, x / 255]), o = run({ arMode: 9, arLevel: 50 }, 1, R); const lv = new Set(); for (let i = 0; i < R.n; i++) lv.add(o.g[i].toFixed(4));
  ok("Posterize: exactly 4 levels a channel at Level 50 on a full ramp", lv.size === 4, `${lv.size} levels`); }
{ const { sliders } = compile(F, {}, { frame: 1 }); let bad = 0;
  for (let k = 0; k < 30; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd(); P.arMode = Math.round(P.arMode);
    const o = run(P, Math.floor(rnd() * 999), A); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok("range over 30 slider sets", bad === 0, `bad ${bad}`); }
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
