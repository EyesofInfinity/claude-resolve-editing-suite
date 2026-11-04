import { compile } from "../../tests/cpu/dctl.mjs";

const BK = "build/Develop Bokeh.dctl", LN = "build/Develop Lens.dctl";
let s = 29;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function image(W, H, fill) {
  const n = W * H, A = { W, H, n, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let i = 0; i < n; i++) { const c = fill(i, i % W, (i / W) | 0); A.r[i] = c[0]; A.g[i] = c[1]; A.b[i] = c[2]; }
  return A;
}
function run(F, P, frame, A) {
  const T = compile(F, P, { frame }).transform;
  const o = { r: new Float32Array(A.n), g: new Float32Array(A.n), b: new Float32Array(A.n) };
  const R = { d: A.r, w: A.W }, G = { d: A.g, w: A.W }, Bt = { d: A.b, w: A.W };
  for (let y = 0; y < A.H; y++) for (let x = 0; x < A.W; x++) { const c = T(A.W, A.H, x, y, R, G, Bt), i = y * A.W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z; }
  return o;
}
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const W = 400, H = 1080;
const A = image(W, H, (i, x, y) => { const v = 0.4 + 0.3 * Math.sin(x / 13) * Math.cos(y / 17) + 0.05 * rnd(); return [v, 0.9 * v, 0.8 * v]; });
const flat = image(W, H, () => [0.4, 0.45, 0.5]);
const point = (px, py) => image(W, H, (i, x, y) => (Math.hypot(x - px, y - py) < 1.5 ? [1, 1, 1] : [0.02, 0.02, 0.02]));
const same = (o, B, th) => { let d = 0; for (let i = 0; i < B.n; i++) d = Math.max(d, Math.abs(o.r[i] - B.r[i]), Math.abs(o.g[i] - B.g[i]), Math.abs(o.b[i] - B.b[i])); return d < th ? true : d; };
for (const [F, off] of [[BK, { bkAmount: 0 }], [LN, { lnAmount: 0 }]]) {
  const P = { ...off }; for (const [nm, v] of Object.entries(compile(F, {}, { frame: 1 }).sliders)) if (!(nm in off)) P[nm] = v.hi;
  const o = run(F, P, 10, A); let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < A.n; i++) if (o[k][i] !== A[k][i]) d++;
  ok(`${F.slice(6)} off is identity`, d === 0, `differ ${d}`);
}
for (let m = 0; m < 4; m++) {
  const a1 = run(BK, { bkMode: m }, 236, A), a2 = run(BK, { bkMode: m }, 236, A), b1 = run(BK, { bkMode: m }, 260, A);
  let rep = 0, mov = 0; for (let i = 0; i < A.n; i++) { if (a1.g[i] !== a2.g[i]) rep++; if (a1.g[i] !== b1.g[i]) mov++; }
  ok(`Bokeh mode ${m}: repeat identical, ${m === 2 ? "the lights move" : "holds"}`, rep === 0 && (m === 2 ? mov > 100 : mov === 0), `repeat ${rep}, moved ${mov}`);
}
for (const m of [0, 1, 3]) { const r = same(run(BK, { bkMode: m }, 1, flat), flat, 1e-5); ok(`Bokeh mode ${m}: a flat picture stays flat`, r === true, `${r}`); }
const ext = (o, cx, cy, ang, th) => { let r = 0; for (let k = 0; k < 80; k++) { const x = Math.round(cx + k * Math.cos(ang)), y = Math.round(cy + k * Math.sin(ang)); if (x < 0 || y < 0 || x >= W || y >= H) break; if (o.g[y * W + x] > th) r = k; } return r; };
{ const o = run(BK, { bkMode: 0, bkCat: 0 }, 1, point(200, 540)), rs = [0, 1, 2, 3, 4, 5].map(k => ext(o, 200, 540, k * Math.PI / 3 + 0.26, 0.025));
  ok("Lens Defocus: a point opens into a disc about Defocus wide", Math.min(...rs) >= 17 && Math.max(...rs) <= 27, `extents ${rs.join(" ")} px (R 24.6)`); }
{ const o = run(BK, { bkMode: 0, bkCat: 0, bkRound: 0, bkRotate: 0 }, 1, point(200, 540));
  const corner = [0, 1, 2, 3, 4, 5].map(k => ext(o, 200, 540, k * Math.PI / 3, 0.025)), flatE = [0, 1, 2, 3, 4, 5].map(k => ext(o, 200, 540, k * Math.PI / 3 + Math.PI / 6, 0.025));
  const mc = corner.reduce((a, b) => a + b) / 6, mf = flatE.reduce((a, b) => a + b) / 6;
  ok("Lens Defocus: six blades make a hexagon (corners further than flats)", mc > mf + 1.5, `corners ${mc.toFixed(1)}, flats ${mf.toFixed(1)} px`); }
{ const o = run(BK, { bkMode: 1, bkCat: 0, bkFringe: 100 }, 1, point(200, 540)); let er = 0, eb = 0;
  for (let k = 0; k < 6; k++) { const a = k * Math.PI / 3 + 0.26; let rr = 0, rb = 0; for (let j = 0; j < 80; j++) { const x = Math.round(200 + j * Math.cos(a)), y = Math.round(540 + j * Math.sin(a)); if (o.r[y * W + x] > 0.025) rr = j; if (o.b[y * W + x] > 0.025) rb = j; } er += rr; eb += rb; }
  ok("Prism Defocus: red discs wider than blue", er > eb + 6, `red ${(er / 6).toFixed(1)}, blue ${(eb / 6).toFixed(1)} px`); }
{ const area = o => { let a = 0; for (let i = 0; i < o.g.length; i++) if (o.g[i] > 0.025) a++; return a; };
  const c = area(run(BK, { bkMode: 0, bkCat: 100 }, 1, point(200, 540))), e = area(run(BK, { bkMode: 0, bkCat: 100 }, 1, point(370, 60)));
  ok("Lens Defocus: cat's eye cuts the discs toward the corners", e < 0.8 * c, `centre ${c} px, corner ${e} px`); }
{ const o = run(BK, { bkMode: 3 }, 1, A); const row = Math.round((1 - 0.55) * H); let dIn = 0, dOut = 0;
  for (let x = 0; x < W; x++) { dIn = Math.max(dIn, Math.abs(o.g[row * W + x] - A.g[row * W + x])); dOut += Math.abs(o.g[30 * W + x] - A.g[30 * W + x]); }
  ok("Split Field: sharp in its band, blurred far from it", dIn < 1e-5 && dOut / W > 0.01, `in band ${dIn.toExponential(1)}, far ${(dOut / W).toFixed(4)}`); }
{ const blk = image(W, H, () => [0, 0, 0]), o = run(BK, { bkMode: 2, bkHue: 40 }, 100, blk); let lit = 0; for (let i = 0; i < blk.n; i++) if (o.g[i] > 0.05 || o.r[i] > 0.05 || o.b[i] > 0.05) lit++;
  ok("Bokeh Lights: lights over a black picture", lit > 1000, `${lit} lit pixels`); }
{ const P = { lnDist: 0, lnCA: 0, lnFringe: 0, lnVig: 0, lnSoft: 0, lnStretch: 0, lnShake: 0 }, r = same(run(LN, P, 1, A), A, 1e-6);
  ok("Lens: every part at 0 gives the picture back", r === true, `${r}`); }
{ const wh = image(W, H, () => [0.8, 0.8, 0.8]), o = run(LN, { lnDist: 0, lnCA: 0, lnFringe: 0, lnSoft: 0 }, 1, wh), c = o.g[540 * W + 200], k = o.g[2 * W + 2];
  ok("Lens: the vignette darkens the corners, not the centre", Math.abs(c - 0.8) < 1e-4 && k < 0.75, `centre ${c.toFixed(4)}, corner ${k.toFixed(4)}`); }
{ const ln = image(W, H, (i, x) => (x >= 370 && x <= 372 ? [1, 1, 1] : [0.1, 0.1, 0.1])), o = run(LN, { lnDist: 0, lnCA: 100, lnFringe: 0, lnVig: 0, lnSoft: 0 }, 1, ln), y = 540;
  let rOut = 0, bIn = 0; for (let x = 360; x < 385; x++) { const i = y * W + x; if (o.r[i] - o.b[i] > 0.05) rOut = Math.max(rOut, x); if (o.b[i] - o.r[i] > 0.05) bIn = bIn || x; }
  ok("Lens: aberration rims a line red outside, blue inside", rOut > 372 && bIn > 0 && bIn < 370, `red to x ${rOut}, blue from x ${bIn}`); }
{ const ln = image(W, H, (i, x, y) => (y >= 100 && y <= 102 ? [1, 1, 1] : [0.1, 0.1, 0.1])), o = run(LN, { lnDist: 80, lnCA: 0, lnFringe: 0, lnVig: 0, lnSoft: 0 }, 1, ln);
  const rowAt = x => { let best = 0, by = 0; for (let y = 0; y < 400; y++) if (o.g[y * W + x] > best) { best = o.g[y * W + x]; by = y; } return by; };
  ok("Lens: barrel bends a straight line", Math.abs(rowAt(200) - rowAt(5)) >= 2, `line at x 200 row ${rowAt(200)}, at x 5 row ${rowAt(5)}`); }
{ const a = run(LN, { lnShake: 0 }, 10, A), b = run(LN, { lnShake: 0 }, 40, A), c = run(LN, { lnShake: 80 }, 10, A), d = run(LN, { lnShake: 80 }, 40, A);
  let h = 0, mv = 0; for (let i = 0; i < A.n; i++) { if (a.g[i] !== b.g[i]) h++; if (Math.abs(c.g[i] - d.g[i]) > 0.01) mv++; }
  ok("Lens: Shake 0 holds the frame, Shake moves it", h === 0 && mv > 0.2 * A.n, `held ${h}, moved ${mv}`); }
for (const F of [BK, LN]) { const { sliders } = compile(F, {}, { frame: 1 }); let bad = 0; const sm = image(120, 270, () => [rnd(), rnd(), rnd()]);
  for (let k = 0; k < 20; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd(); if (P.bkMode !== undefined) P.bkMode = Math.round(P.bkMode);
    const o = run(F, P, Math.floor(rnd() * 999), sm); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok(`${F.slice(6)} range over 20 slider sets`, bad === 0, `bad ${bad}`); }
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
