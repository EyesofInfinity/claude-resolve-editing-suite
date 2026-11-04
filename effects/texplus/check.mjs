import { compile } from "../../tests/cpu/dctl.mjs";

const TX = "build/Develop Texture Plus.dctl";
let s = 29;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function image(W, H, fill) {
  const n = W * H, A = { W, H, n, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let i = 0; i < n; i++) { const c = fill(i, i % W, (i / W) | 0); A.r[i] = c[0]; A.g[i] = c[1]; A.b[i] = c[2]; }
  return A;
}
function run(P, frame, A) {
  const T = compile(TX, P, { frame }).transform;
  const o = { r: new Float32Array(A.n), g: new Float32Array(A.n), b: new Float32Array(A.n) };
  const R = { d: A.r, w: A.W }, G = { d: A.g, w: A.W }, B = { d: A.b, w: A.W };
  for (let y = 0; y < A.H; y++) for (let x = 0; x < A.W; x++) { const c = T(A.W, A.H, x, y, R, G, B), i = y * A.W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z; }
  return o;
}
function win(P, frame, W, H, x0, y0, w, h, v = 0.5) {
  const T = compile(TX, P, { frame }).transform;
  const tex = { d: new Proxy([], { get: () => v }), w: W };
  const o = new Float32Array(w * h), c3 = [new Float32Array(w * h), new Float32Array(w * h), new Float32Array(w * h)];
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const c = T(W, H, x0 + x, y0 + y, tex, tex, tex); const i = y * w + x; o[i] = c.y; c3[0][i] = c.x; c3[1][i] = c.y; c3[2][i] = c.z; }
  return { g: o, rgb: c3, w, h };
}
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const KINDS = ["Moire", "Spots", "Tiles", "Loops", "Micro", "Emboss", "Paint", "Chroma Spiral"];
const W = 320, H = 180;
const chart = image(W, H, (i, x, y) => [x / W, y / H, 0.5 + 0.5 * Math.sin(x / 7 + y / 11)]);
const grey = image(W, H, () => [0.5, 0.5, 0.5]);
const black = image(W, H, () => [0, 0, 0]);
const supers = image(W, H, (i, x) => [x % 3 === 0 ? 1.4 : -0.1, 0.3, 0.7]);
const pct = (arr, p) => { const v = Array.from(arr).sort((a, b) => a - b); return v[Math.floor(p * (v.length - 1))]; };

{ const { sliders } = compile(TX, {}, { frame: 1 });
  const P = { tpAmount: 0 }; for (const [nm, v] of Object.entries(sliders)) if (nm !== "tpAmount") P[nm] = v.hi;
  for (const A of [chart, supers]) {
    const o = run(P, 17, A); let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < A.n; i++) if (o[k][i] !== A[k][i]) d++;
    ok(`Amount 0 is identity${A === supers ? " (superwhite, negative)" : ""}`, d === 0, `differ ${d}`);
  } }

for (let k = 0; k < KINDS.length; k++) {
  const P = { tpKind: k, tpStrength: 62 };
  const a1 = run(P, 236, grey), a2 = run(P, 236, grey), a3 = run(P, 237, grey), b1 = run(P, k === 6 ? 1236 : 260, grey);
  const h1 = run({ ...P, tpSpeed: 0 }, 236, grey), h2 = run({ ...P, tpSpeed: 0 }, 900, grey);
  let rep = 0, mov = 0, hold = 0, lo = 1, hi = 0, step = 0;
  for (let i = 0; i < grey.n; i++) { if (a1.g[i] !== a2.g[i]) rep++; if (Math.abs(a1.g[i] - b1.g[i]) > 2e-3) mov++; if (h1.g[i] !== h2.g[i]) hold++;
    lo = Math.min(lo, a1.g[i]); hi = Math.max(hi, a1.g[i]); step += Math.abs(a1.g[i] - a3.g[i]); }
  step /= grey.n;
  ok(`${KINDS[k]}: repeats, moves 24 frames on, Speed 0 holds, has structure, one frame's change under 0.006`,
     rep === 0 && mov > 0.02 * grey.n && hold === 0 && hi - lo > 0.15 && step < 0.006,
     `repeat ${rep}, moved ${mov}, held-diff ${hold}, range ${lo.toFixed(2)}-${hi.toFixed(2)}, per frame ${step.toFixed(4)}`);
}
{ let worst = 0, wk = "";
  for (let k = 0; k < KINDS.length; k++) { const o = run({ tpKind: k, tpColour: 0 }, 236, grey); const m = pct(o.g, 0.5);
    const d = Math.abs(m - 0.5); if (d > worst) { worst = d; wk = KINDS[k]; } }
  ok("Overlay keeps a grey picture's median within 0.03 for every Kind", worst < 0.03, `worst ${worst.toFixed(3)} (${wk})`); }
{ let bad = 0, dk = 0; for (let k = 0; k < KINDS.length; k++) { const o = run({ tpKind: k, tpBlend: 1 }, 236, chart);
    for (let i = 0; i < chart.n; i++) { if (o.g[i] > chart.g[i] + 1e-6 || o.r[i] > chart.r[i] + 1e-6) bad++; if (o.g[i] < chart.g[i] - 0.02) dk++; } }
  ok("Multiply only darkens, and darkens", bad === 0 && dk > 0.1 * chart.n * 8, `brightened ${bad}, darkened ${dk}`); }
{ let bad = 0, add = 0; for (let k = 0; k < KINDS.length; k++) { const o = run({ tpKind: k, tpBlend: 2, tpColour: 0, tpFollow: 0 }, 236, chart);
    for (let i = 0; i < chart.n; i++) { if (o.g[i] < chart.g[i] - 1e-6 && chart.g[i] < 0.8) bad++; if (o.g[i] > chart.g[i] + 0.02) add++; } }
  const o = run({ tpKind: 3, tpBlend: 2, tpFollow: 0 }, 236, black); let dark = 0; for (let i = 0; i < black.n; i++) if (o.g[i] < 1 / 255) dark++;
  ok("Screen only adds light; Loops on black leave at least 60% of the ground black", bad === 0 && add > 0 && dark > 0.6 * black.n,
     `darkened ${bad}, lit ${add}, black kept ${(dark / black.n * 100).toFixed(0)}%`); }
{ let f100 = 0, f0 = 0, ov = 0;
  for (let k = 0; k < KINDS.length; k++) {
    const a = run({ tpKind: k, tpBlend: 2, tpFollow: 100, tpStrength: 100 }, 236, black), b = run({ tpKind: k, tpBlend: 2, tpFollow: 0, tpStrength: 100 }, 236, black);
    const c = run({ tpKind: k, tpBlend: 0, tpFollow: 100, tpStrength: 100 }, 236, black);
    for (let i = 0; i < black.n; i++) { f100 = Math.max(f100, a.g[i]); f0 = Math.max(f0, b.g[i]); ov = Math.max(ov, c.g[i]); }
  }
  ok("Follow 100 keeps black black (Screen and Overlay); Follow 0 lets Screen light it", f100 === 0 && ov === 0 && f0 > 0.2, `Follow 100 max ${f100}, Overlay ${ov}, Follow 0 max ${f0.toFixed(3)}`); }
{ let moved = 0, out = 0, far = 0;
  for (const k of [2, 4, 5, 7]) { const o = run({ tpKind: k, tpBlend: 3, tpStrength: 100 }, 236, chart);
    for (let i = 0; i < chart.n; i++) { if (Math.abs(o.r[i] - chart.r[i]) > 0.01) moved++; if (o.r[i] < -1e-6 || o.r[i] > 1 + 1e-6) out++; if (Math.abs(o.r[i] - chart.r[i]) * W > 50) far++; } }
  ok("Displace shifts the picture by a bounded amount (Tiles, Micro, Emboss, Chroma)", moved > 0.1 * chart.n && out === 0 && far === 0, `moved ${moved}, out of range ${out}, over 50 px ${far}`); }

const FW = 1920, FH = 1080;
const boxMean = (g, w, h, r) => { const o = []; for (let y = r; y < h - r; y += r) for (let x = r; x < w - r; x += r) { let m = 0, c = 0;
  for (let j = -r; j <= r; j++) for (let i = -r; i <= r; i++) { m += g[(y + j) * w + x + i]; c++; } o.push(m / c); } return o; };
{ const A = win({ tpKind: 0, tpStrength: 62, tpSpeed: 0 }, 1, FW, FH, 700, 400, 300, 200);
  const bm = boxMean(A.g, A.w, A.h, 12), rng = Math.max(...bm) - Math.min(...bm);
  const big = (() => { let d = 0; for (let i = 1; i < A.g.length; i++) d += Math.abs(A.g[i] - A.g[i - 1]); return d / A.g.length; })();
  const sm = run({ tpKind: 0, tpStrength: 62, tpSpeed: 0 }, 1, image(160, 90, () => [0.5, 0.5, 0.5]));
  let e1 = 0, e2 = 0; for (let y = 0; y < 90; y++) for (let x = 0; x + 2 < 160; x++) { const i = y * 160 + x; e1 += Math.abs(sm.g[i + 1] - sm.g[i]); e2 += Math.abs(sm.g[i + 2] - sm.g[i]); }
  ok("Moire: broad bands survive a 25 px average; ribs resolved at 1080, nothing near the pixel limit at 90 rows", rng > 0.15 && big > 0.01 && e1 / e2 < 0.62,
     `band range ${rng.toFixed(3)}, rib change ${big.toFixed(3)} at 1080, one-pixel over two-pixel change ${(e1 / e2).toFixed(3)} at 90 rows`); }
{ const A = win({ tpKind: 1, tpStrength: 62, tpSpeed: 0 }, 1, FW, FH, 600, 300, 400, 300); const m = pct(A.g, 0.5);
  let spot = 0; for (const v of A.g) if (v < m - 0.08) spot++;
  ok("Spots: spots cover 8% to 45% of the ground", spot > 0.08 * A.g.length && spot < 0.45 * A.g.length, `spots ${(spot / A.g.length * 100).toFixed(1)}%`); }
for (let sh = 0; sh < 4; sh++) {
  const A = win({ tpKind: 2, tpStrength: 62, tpShape: sh, tpSpeed: 0 }, 1, FW, FH, 600, 300, 400, 300);
  const p50 = pct(A.g, 0.5); let gr = 0; for (const v of A.g) if (v < p50 - 0.2) gr++;
  const bm = boxMean(A.g, A.w, A.h, 6), sd = Math.sqrt(bm.reduce((a, v) => a + (v - p50) ** 2, 0) / bm.length);
  ok(`Tiles ${["hexagon", "triangle", "diamond", "star and cross"][sh]}: grout 2% to 25%, tile tones vary`, gr > 0.02 * A.g.length && gr < 0.25 * A.g.length && sd > 0.04,
     `grout ${(gr / A.g.length * 100).toFixed(1)}%, tone spread ${sd.toFixed(3)}`); }
{ const a = win({ tpKind: 2, tpStrength: 62, tpSpeed: 100 }, 1, FW, FH, 600, 300, 200, 150), b = win({ tpKind: 2, tpStrength: 62, tpSpeed: 100 }, 2000, FW, FH, 600, 300, 200, 150);
  const ga = pct(a.g, 0.5) - 0.2, gb = pct(b.g, 0.5) - 0.2; let same = 0, n = 0, chg = 0;
  for (let i = 0; i < a.g.length; i++) { if (a.g[i] < ga || b.g[i] < gb) { n++; if ((a.g[i] < ga) === (b.g[i] < gb)) same++; } if (Math.abs(a.g[i] - b.g[i]) > 0.01) chg++; }
  ok("Tiles: the grout holds still while the light moves", same > 0.95 * n && chg > 0.1 * a.g.length, `grout kept ${(same / n * 100).toFixed(1)}%, changed ${chg}`); }
{ const A = win({ tpKind: 3, tpBlend: 2, tpStrength: 100, tpFollow: 0, tpSpeed: 0 }, 1, FW, FH, 600, 300, 400, 300, 0);
  let lit = 0; for (const v of A.g) if (v > 0.02) lit++;
  const v = A.g.filter(x => x > 0.02); const p90 = pct(v, 0.9), p25 = pct(v, 0.25);
  ok("Loops: thin wire (under 20% of pixels), near halves bright and far halves dim", lit < 0.2 * A.g.length && lit > 0.02 * A.g.length && p90 > 2.5 * p25,
     `lit ${(lit / A.g.length * 100).toFixed(1)}%, bright ${p90.toFixed(3)} dim ${p25.toFixed(3)}`); }
{ const A = win({ tpKind: 4, tpStrength: 62, tpSpeed: 0 }, 1, FW, FH, 600, 300, 300, 200);
  let neut = 0; for (let i = 0; i < A.g.length; i++) if (Math.abs(A.rgb[0][i] - A.rgb[2][i]) > 1e-6) neut++;
  const p50 = pct(A.g, 0.5), p95 = pct(A.g, 0.95);
  ok("Micro: grey, with bright tilted rims", neut === 0 && p95 > p50 + 0.12, `coloured ${neut}, median ${p50.toFixed(3)}, p95 ${p95.toFixed(3)}`); }
{ const A = win({ tpKind: 5, tpStrength: 62, tpSpeed: 0 }, 1, FW, FH, 400, 200, 600, 400);
  const p50 = pct(A.g, 0.5), p995 = pct(A.g, 0.995);
  ok("Emboss: highlights well above the surface", p995 > p50 + 0.25, `median ${p50.toFixed(3)}, p99.5 ${p995.toFixed(3)}`); }
{ const A = win({ tpKind: 6, tpStrength: 62, tpSpeed: 0 }, 1, FW, FH, 600, 300, 384, 288); let aniso = 0, n = 0;
  for (let py = 0; py + 24 <= A.h; py += 24) for (let px = 0; px + 24 <= A.w; px += 24) { const d = [0, 0, 0, 0];
    for (let y = py + 1; y < py + 23; y++) for (let x = px + 1; x < px + 23; x++) { const i = y * A.w + x, c = A.g[i];
      d[0] += Math.abs(c - A.g[i + 1]); d[1] += Math.abs(c - A.g[i + A.w]); d[2] += Math.abs(c - A.g[i + A.w + 1]) / 1.41; d[3] += Math.abs(c - A.g[i + A.w - 1]) / 1.41; }
    n++; if (Math.max(...d) > 1.4 * Math.min(...d)) aniso++; }
  ok("Paint: bristle streaks run one way in most patches", aniso > 0.6 * n, `${aniso} of ${n} patches`); }
{ const A = win({ tpKind: 7, tpStrength: 62, tpSpeed: 0 }, 1, FW, FH, 300, 200, 600, 400); let ch = 0; const sext = new Set();
  for (let i = 0; i < A.g.length; i += 3) { const r = A.rgb[0][i], g = A.rgb[1][i], b = A.rgb[2][i], mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    ch += mx - mn; if (mx - mn > 0.1) { let h = mx === r ? (g - b) / (mx - mn) : mx === g ? 2 + (b - r) / (mx - mn) : 4 + (r - g) / (mx - mn); sext.add(Math.floor(((h + 6) % 6))); } }
  ch /= A.g.length / 3;
  ok("Chroma Spiral: coloured, all six hue sextants", ch > 0.15 && sext.size === 6, `mean chroma ${ch.toFixed(3)}, sextants ${sext.size}`); }

{ const res = [];
  for (let bl = 0; bl < 4; bl++) {
    const o = run({ tpKind: bl === 3 ? 2 : 0, tpBlend: bl, tpStrength: 100 }, 236, supers);
    let swKept = 0, sw = 0, ngKept = 0, ng = 0, maxR = -9, minR = 9;
    for (let i = 0; i < supers.n; i++) {
      maxR = Math.max(maxR, o.r[i]); minR = Math.min(minR, o.r[i]);
      if (supers.r[i] > 1) { sw++; if (bl === 1 ? o.r[i] > 1 : o.r[i] === supers.r[i]) swKept++; }
      else { ng++; if (o.r[i] === supers.r[i]) ngKept++; }
    }
    res.push({ bl, swKept, sw, ngKept, ng, maxR, minR });
  }
  const [ov, mu, sc, di] = res;
  const pass = ov.swKept === ov.sw && ov.ngKept === ov.ng && mu.swKept > 0.2 * mu.sw && sc.swKept === sc.sw && di.maxR > 1.05 && di.minR < -0.05;
  ok("superwhite and negative values carry through every Blend", pass,
     `Overlay kept ${ov.swKept}/${ov.sw} superwhite ${ov.ngKept}/${ov.ng} negative; Multiply over 1 ${mu.swKept}/${mu.sw}; Screen kept ${sc.swKept}/${sc.sw}; Displace range ${di.minR.toFixed(2)} to ${di.maxR.toFixed(2)}`); }

{ const { sliders } = compile(TX, {}, { frame: 1 }); let bad = 0; const small = image(96, 54, () => [rnd() * 1.2 - 0.1, rnd(), rnd()]);
  const lim = {}; for (const c of ["r", "g", "b"]) { let lo = 0, hi = 1; for (const v of small[c]) { lo = Math.min(lo, v); hi = Math.max(hi, v); } lim[c] = [lo, hi]; }
  for (let k = 0; k < 30; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd();
    for (const m of ["tpKind", "tpBlend", "tpShape"]) P[m] = Math.round(P[m]);
    const o = run(P, Math.floor(rnd() * 5000), small); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < lim[c][0] || v > lim[c][1]) { bad++; break; } }
  ok("range over 30 slider sets", bad === 0, `bad ${bad}`); }
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
