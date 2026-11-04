import { compile } from "../../tests/cpu/dctl.mjs";

const F = "build/Develop Paint.dctl";
let s = 23;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function image(W, H, fill) {
  const n = W * H, A = { W, H, n, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let i = 0; i < n; i++) { const c = fill(i, i % W, (i / W) | 0); A.r[i] = c[0]; A.g[i] = c[1]; A.b[i] = c[2]; }
  return A;
}
function run(P, frame, A) {
  const T = compile(F, P, { frame }).transform;
  const o = { W: A.W, H: A.H, n: A.n, r: new Float32Array(A.n), g: new Float32Array(A.n), b: new Float32Array(A.n) };
  const R = { d: A.r, w: A.W }, G = { d: A.g, w: A.W }, Bt = { d: A.b, w: A.W };
  for (let y = 0; y < A.H; y++) for (let x = 0; x < A.W; x++) { const c = T(A.W, A.H, x, y, R, G, Bt), i = y * A.W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z; }
  return o;
}
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const NAMES = ["Oil Paint", "Cartoon Paint", "Watercolour", "Tile Mosaic", "Spray Paint"];
const Y = (o, i) => 0.2126 * o.r[i] + 0.7152 * o.g[i] + 0.0722 * o.b[i];
const mean = o => { let m = 0; for (let i = 0; i < o.n; i++) m += Y(o, i); return m / o.n; };
const sdev = o => { const m = mean(o); let v = 0; for (let i = 0; i < o.n; i++) v += (Y(o, i) - m) ** 2; return Math.sqrt(v / o.n); };
const W = 640, H = 360;
const A = image(W, H, (i, x, y) => { const d = Math.hypot(x - 220, y - 160); const v = 0.1 + 0.55 * x / W + 0.3 * Math.exp(-d * d / 3000) + 0.05 * rnd(); return [Math.min(1, v), 0.85 * v, 0.6 * v]; });
const flat = (v, w = 320, h = 180) => image(w, h, () => [v, v, v]);
const step = (a, b) => image(320, 180, (i, x) => (x < 160 ? [a, a, a] : [b, b, b]));

{ const P = { ptAmount: 0 }; for (const [nm, v] of Object.entries(compile(F, {}, { frame: 1 }).sliders)) if (nm !== "ptAmount") P[nm] = v.hi;
  const o = run(P, 10, A); let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < A.n; i++) if (o[k][i] !== A[k][i]) d++;
  ok("off is identity", d === 0, `differ ${d}`); }
{ const S = image(240, 135, (i, x, y) => { const v = 0.2 + 0.6 * x / 240 + 0.1 * Math.sin(y / 7); return [v, 0.9 * v, 0.7 * v]; });
  for (let m = 0; m < 5; m++) {
    const a1 = run({ ptMode: m }, 240, S), a2 = run({ ptMode: m }, 240, S), b1 = run({ ptMode: m }, 252, S);
    const z1 = run({ ptMode: m, ptBoil: 0 }, 240, S), z2 = run({ ptMode: m, ptBoil: 0 }, 600, S);
    let rep = 0, mov = 0, still = 0;
    for (let i = 0; i < S.n; i++) { if (a1.g[i] !== a2.g[i]) rep++; if (a1.g[i] !== b1.g[i]) mov++; if (z1.g[i] !== z2.g[i]) still++; }
    const boils = [0, 1, 4].includes(m);
    ok(`${NAMES[m]}: repeat identical, Boil 0 holds, ${boils ? "boils" : "holds without time"}`, rep === 0 && still === 0 && (boils ? mov > S.n * 0.05 : mov === 0),
       `repeat ${rep}, Boil 0 moved ${still}, 12 frames on moved ${mov}`);
  } }
{ const th = 30 * Math.PI / 180, ca = Math.cos(th), sa = Math.sin(th);
  const St = image(W, H, (i, x, y) => { const u = -x * sa + y * ca; const v = 0.5 + 0.25 * Math.sin(u * 2 * Math.PI / 36); return [v, v, v]; });
  const orient = o => { let jxx = 0, jyy = 0, jxy = 0; const D = i => Y(o, i) - Y(St, i);
    for (let y = 20; y < H - 20; y++) for (let x = 20; x < W - 20; x++) { const i = y * W + x, gx = D(i + 1) - D(i - 1), gy = D(i + W) - D(i - W); jxx += gx * gx; jyy += gy * gy; jxy += gx * gy; }
    let a = 0.5 * Math.atan2(2 * jxy, jxx - jyy) * 180 / Math.PI; if (a < 0) a += 180; return [a, Math.hypot(jxx - jyy, 2 * jxy) / (jxx + jyy)]; };
  const [af, cf] = orient(run({ ptMode: 0, ptSize: 100, ptFlow: 100, ptBoil: 0 }, 1, St)), [ax, cx] = orient(run({ ptMode: 0, ptSize: 100, ptFlow: 0, ptAngle: 120, ptBoil: 0 }, 1, St));
  ok("Oil Paint: with Flow the strokes run along the stripes, in order; without, they wander", Math.abs(af - 120) < 15 && cf > 0.3 && cf > 3 * cx,
     `texture across ${af.toFixed(1)} deg (coherence ${cf.toFixed(2)}), Flow 0: ${ax.toFixed(1)} deg (${cx.toFixed(2)})`); }
{ const G = flat(0.5), o = run({ ptMode: 0, ptBoil: 0 }, 1, G), o0 = run({ ptMode: 0, ptBoil: 0, ptTexture: 0 }, 1, G);
  ok("Oil Paint: a flat grey keeps its tone and gains stroke texture", Math.abs(mean(o) - 0.5) < 0.03 && sdev(o) > 0.012 && sdev(o) > sdev(o0),
     `mean ${mean(o).toFixed(3)}, spread ${sdev(o).toFixed(4)} (Texture 0 ${sdev(o0).toFixed(4)})`); }
for (const m of [0, 1]) {
  const St = step(0.1, 0.9), o = run({ ptMode: m, ptBoil: 0, ptSize: 100 }, 1, St); let bad = 0, k = 0;
  for (let y = 0; y < 180; y++) for (let x = 0; x < 320; x++) { if (Math.abs(x - 159.5) < 4) continue; const v = Y(o, y * 320 + x); k++; if (x < 160 ? v > 0.35 : v < 0.6) bad++; }
  ok(`${NAMES[m]}: strokes stop at a hard edge`, bad < 0.01 * k, `${(100 * bad / k).toFixed(2)}% across`);
}
{ const o = run({ ptMode: 1, ptBoil: 0 }, 1, flat(0.7)), st = run({ ptMode: 1, ptBoil: 0 }, 1, step(0.85, 0.3));
  let mn = 1, line = 1; for (let i = 0; i < o.n; i++) mn = Math.min(mn, Y(o, i)); for (let y = 10; y < 170; y++) for (let x = 157; x < 163; x++) line = Math.min(line, Y(st, y * 320 + x));
  ok("Cartoon Paint: no line on a flat picture, a dark line on a step", mn > 0.4 && line < 0.12, `flat min ${mn.toFixed(3)}, step line ${line.toFixed(3)}`); }
{ const w = run({ ptMode: 2 }, 1, flat(1.0)), m = run({ ptMode: 2 }, 1, flat(0.45)), p = run({ ptMode: 2 }, 1, flat(0.85));
  let mn = 1; for (let i = 0; i < w.n; i++) mn = Math.min(mn, Y(w, i));
  ok("Watercolour: white is bare paper; a wash granulates, a mid wash more than a pale one", mean(w) > 0.94 && mn > 0.88 && sdev(m) > 0.008 && sdev(m) > sdev(p),
     `paper mean ${mean(w).toFixed(3)} min ${mn.toFixed(3)}, grain mid ${sdev(m).toFixed(4)} pale ${sdev(p).toFixed(4)}`); }
{ const o = run({ ptMode: 2, ptTexture: 0 }, 1, step(0.35, 0.8)); const col = x => { let v = 0; for (let y = 20; y < 160; y++) v += Y(o, y * 320 + x); return v / 140; };
  let rim = 1, rx = 0; for (let x = 130; x < 160; x++) if (col(x) < rim) { rim = col(x); rx = x; }
  let inside = 0; for (let x = 40; x < 90; x++) inside += col(x); inside /= 50;
  ok("Watercolour: the darker wash pools at its border", rim < inside - 0.02, `border ${rim.toFixed(3)} at x ${rx}, inside ${inside.toFixed(3)}`); }
{ const o = run({ ptMode: 3 }, 1, flat(0.7)); let gr = 0; for (let i = 0; i < o.n; i++) if (Y(o, i) < 0.45) gr++;
  ok("Tile Mosaic: grout lines between tiles", gr > 0.05 * o.n && gr < 0.4 * o.n, `${(100 * gr / o.n).toFixed(1)}% grout`);
  const st = run({ ptMode: 3 }, 1, step(0.15, 0.95)); let on = 0, k = 0, bad = 0, kb = 0;
  for (let y = 0; y < 180; y++) { let g = false; for (let x = 156; x < 164; x++) { const v = Y(st, y * 320 + x); if (v > 0.25 && v < 0.42) g = true; } k++; if (g) on++;
    for (let x = 0; x < 320; x++) { if (Math.abs(x - 159.5) < 3) continue; const v = Y(st, y * 320 + x); kb++; if (x < 160 ? v > 0.6 : v < 0.2) bad++; } }
  ok("Tile Mosaic: grout runs along the edge, no tile crosses it", on > 0.9 * k && bad < 0.005 * kb, `grout on the edge in ${(100 * on / k).toFixed(1)}% of rows, ${bad} pixels across`); }
{ const C = image(320, 180, () => [0.7, 0.4, 0.2]), o = run({ ptMode: 4, ptColour: 0, ptBoil: 0 }, 1, C);
  let mr = 0, mg = 0, mb = 0; for (let i = 0; i < o.n; i++) { mr += o.r[i]; mg += o.g[i]; mb += o.b[i]; } mr /= o.n; mg /= o.n; mb /= o.n;
  ok("Spray Paint: a flat colour sprays as one even paint, its tint kept", sdev(o) < 0.03 && Math.abs(mr / mg - 1.75) < 0.12 && Math.abs(mg / mb - 2.0) < 0.15,
     `${mr.toFixed(3)} ${mg.toFixed(3)} ${mb.toFixed(3)}, spread ${sdev(o).toFixed(4)}`);
  const S2 = image(240, 1080, (i, x) => (x < 120 ? [0.1, 0.1, 0.1] : [0.9, 0.9, 0.9]));
  const st = run({ ptMode: 4, ptBoil: 0 }, 1, S2), Rr = 8; let near = 0, kn = 0, far = 0, kf = 0;
  for (let y = 0; y < 1080; y++) for (let x = 120; x < 240; x++) { const d = x - 119.5, v = Y(st, y * 240 + x);
    if (d > 1.2 * Rr && d < 2.0 * Rr) { kn++; if (v < 0.5) near++; } if (d > 2.5 * Rr + 4.2 + 2) { kf++; if (v < 0.5) far++; } }
  ok("Spray Paint: overspray droplets near the border, none beyond their reach", near > 0.02 * kn && far === 0, `${(100 * near / kn).toFixed(1)}% dark at 1.2 to 2 R, ${far} beyond`); }
{ const { sliders } = compile(F, {}, { frame: 1 }); let bad = 0; const S = image(160, 90, (i, x, y) => [rnd(), x / 160, y / 90]);
  for (let k = 0; k < 30; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd(); P.ptMode = Math.round(P.ptMode);
    const o = run(P, Math.floor(rnd() * 999), S); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok("range over 30 slider sets", bad === 0, `bad ${bad}`); }
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
