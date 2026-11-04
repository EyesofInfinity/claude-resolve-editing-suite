import { compile, runTransition, run } from "../../tests/cpu/dctl.mjs";

const TT = "build/Develop Tritone Dissolve.dctl", DB = "build/Develop Deband.dctl";
let s = 32;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function img(W, H, fn) {
  const n = W * H, o = { w: W, h: H, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const c = fn(x, y), i = y * W + x; o.r[i] = c[0]; o.g[i] = c[1]; o.b[i] = c[2]; }
  return o;
}
const cl = v => Math.min(Math.max(v, 0), 1);
const lin = v => Math.pow(Math.max(v, 0), 2.4), disp = v => Math.pow(Math.max(v, 0), 1 / 2.4);
const tone = (r, g, b) => disp(0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b));
let fails = 0, count = 0;
const ok = (name, pass, info) => { count++; console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const diff = (o, q) => { let d = 0, m = 0; const n = o.r.length; for (const k of ["r", "g", "b"]) for (let i = 0; i < n; i++) { const e = Math.abs(o[k][i] - q[k][i]); if (e > 1e-9) d++; m += e; } return { n: d, mean: +(m / (3 * n)).toFixed(5) }; };

{
  const W = 320, H = 180;
  const A = img(W, H, (x, y) => { const v = 0.35 + 0.25 * Math.sin(x / 7) * Math.cos(y / 11) + (y < 40 ? 0.45 : 0) + (rnd() < 0.004 ? 0.6 : 0); return [cl(v), cl(0.9 * v), cl(0.7 * v + 0.05 * rnd())]; });
  const B = img(W, H, (x, y) => { const r = Math.hypot(x - W / 2, y - H / 3), v = 0.3 + 0.3 * Math.sin(r / 6) + (r < 25 ? 0.5 : 0); return [cl(0.5 * v), cl(0.8 * v), cl(v)]; });
  const tt = (p, a = A, b = B, P = {}) => runTransition(TT, P, { progress: p, frame: 1 }, a, b);
  ok("Tritone starts exactly on the outgoing shot", diff(tt(0), A).n === 0, JSON.stringify(diff(tt(0), A)));
  ok("Tritone ends exactly on the incoming shot", diff(tt(1), B).n === 0, JSON.stringify(diff(tt(1), B)));
  const e0 = diff(tt(0.02), A).mean, e1 = diff(tt(0.98), B).mean;
  ok("Tritone eases out and in (within 0.005 at progress 0.02 and 0.98)", e0 < 0.005 && e1 < 0.005, `${e0} ${e1}`);
  {
    const o = tt(0.5, A, B, { ttTone: 0, ttLead: 0 });
    let m = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < W * H; i++) m = Math.max(m, Math.abs(o[k][i] - 0.5 * (A[k][i] + B[k][i])));
    ok("Tritone at Tone 0 is a plain dissolve", m < 1e-6, `max ${m.toExponential(2)}`);
  }
  const S = [31, 23, 17].map(v => v / 255), M = [168, 138, 101].map(v => v / 255), HI = [245, 235, 211].map(v => v / 255);
  const ts = tone(...S), th = tone(...HI);
  {
    const o = tt(0.5, A, B, { ttPulse: 0, ttLead: 0 });
    let m = 0, warm = 0;
    for (let i = 0; i < W * H; i++) {
      const T = 0.5 * tone(cl(A.r[i]), cl(A.g[i]), cl(A.b[i])) + 0.5 * tone(cl(B.r[i]), cl(B.g[i]), cl(B.b[i]));
      m = Math.max(m, Math.abs(tone(o.r[i], o.g[i], o.b[i]) - (ts + (th - ts) * T)));
      if (o.r[i] >= o.g[i] && o.g[i] >= o.b[i]) warm++;
    }
    ok("Tritone at the peak prints the mixed tone between floor and ceiling", m < 0.004, `max tone error ${m.toFixed(5)}`);
    ok("Tritone at the peak is all in the default inks (red over green over blue)", warm === W * H, `${warm} of ${W * H}`);
  }
  {
    const tm = tone(...M), u = (tm - ts) / (th - ts);
    const g = disp(u ** 2.4); // a grey whose tone is u
    const K = img(8, 8, () => [0, 0, 0]), Wh = img(8, 8, () => [1, 1, 1]), G = img(8, 8, () => [g, g, g]);
    const P = { ttPulse: 0, ttLead: 0 };
    const at = (a, b) => { const o = tt(0.5, a, b, P); return [o.r[0], o.g[0], o.b[0]].map(v => Math.round(v * 255)); };
    const k = at(K, K), w = at(Wh, Wh), mm = at(G, G);
    const near = (c, t, e) => c.every((v, i) => Math.abs(v - t[i] * 255) <= e);
    ok("Tritone prints black at the warm near-black floor #1F1711", near(k, S, 1), `got ${k}`);
    ok("Tritone prints white at the cream ceiling #F5EBD3", near(w, HI, 1.5), `got ${w}`);
    ok("Tritone prints the mid tone at the sepia mid #A88A65", near(mm, M, 2), `got ${mm}`);
  }
  {
    const S0 = [31, 23, 17].map(v => v / 255), H0 = [245, 235, 211].map(v => v / 255), Mc = [84, 126, 168].map(v => v / 255);
    const u = (tone(...Mc) - tone(...S0)) / (tone(...H0) - tone(...S0)), gv = disp(u ** 2.4);
    const Gm = img(8, 8, () => [gv, gv, gv]), K = img(8, 8, () => [0, 0, 0]);
    const o = tt(0.5, Gm, Gm, { ttMiH: 210, ttMiS: 50, ttPulse: 0 }), k0 = tt(0.5, K, K, { ttMiH: 210, ttMiS: 50, ttPulse: 0 }), k1 = tt(0.5, K, K, { ttPulse: 0 });
    ok("Tritone's Mid colour sets the print's mid tones", o.b[0] > o.r[0] + 0.05 && Math.abs(k0.r[0] - k1.r[0]) < 1e-9, `mid r ${o.r[0].toFixed(3)} b ${o.b[0].toFixed(3)}`);
  }
  {
    const Gm = img(W, H, () => [0.5, 0.5, 0.5]), KW = img(W, H, x => (x < W / 2 ? [0, 0, 0] : [1, 1, 1]));
    const tOf = (L, x) => { const o = tt(0.42, Gm, KW, { ttTone: 0, ttLead: L }); const v = o.g[90 * W + x]; return x < W / 2 ? (0.5 - v) / 0.5 : (v - 0.5) / 0.5; };
    const dP = tOf(100, 40), bP = tOf(100, 280), dN = tOf(-100, 40), bN = tOf(-100, 280);
    ok("Tritone's Tone Lead brings the shadows in first (and the highlights at negative Lead)", dP > bP + 0.2 && bN > dN + 0.2, `Lead 100: dark ${dP.toFixed(2)} bright ${bP.toFixed(2)}; Lead -100: dark ${dN.toFixed(2)} bright ${bN.toFixed(2)}`);
  }
  {
    const Gm = img(8, 8, () => [0.4, 0.4, 0.4]), K = img(8, 8, () => [0, 0, 0]);
    const a = tt(0.5, Gm, Gm, { ttPulse: 100 }).g[0], b = tt(0.5, Gm, Gm, { ttPulse: 0 }).g[0];
    const ka = tt(0.5, K, K, { ttPulse: 100 }).g[0], kb = tt(0.5, K, K, { ttPulse: 0 }).g[0];
    ok("Tritone's Pulse breathes the mid tones and holds the floor", a > b + 0.02 && Math.abs(ka - kb) < 1e-9, `mid ${b.toFixed(3)} to ${a.toFixed(3)}, floor ${kb.toFixed(4)} ${ka.toFixed(4)}`);
  }
  {
    const { sliders } = compile(TT, {}, { progress: 0.5 });
    let bad = 0;
    for (let k = 0; k < 30; k++) {
      const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd();
      const o = runTransition(TT, P, { progress: rnd(), frame: 1 }, A, B);
      for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; }
    }
    ok("Tritone range over 30 slider sets", bad === 0, `bad ${bad}`);
  }
}

{
  const db = (P, im, frame = 1) => run(compile(DB, P, { frame }).transform, im);
  const { sliders } = compile(DB, {}, { frame: 1 });
  const W = 400, H = 120;
  const tex = img(W, H, (x, y) => { const v = 0.3 + 0.2 * Math.sin(x / 3) * Math.cos(y / 4) + 0.1 * rnd(); return [v, 0.9 * v, 0.8 * v]; });
  {
    const P = { dbAmount: 0 }; for (const [nm, v] of Object.entries(sliders)) if (nm !== "dbAmount") P[nm] = v.hi;
    ok("Deband: Amount 0 is identity", diff(db(P, tex), tex).n === 0, JSON.stringify(diff(db(P, tex), tex)));
  }
  for (const per of [12, 40, 100]) {
    const RW = 900, RH = 1080, tru = new Float64Array(RW);
    const R = img(RW, RH, x => { const t = (14 + x / per) / 255; tru[x] = t; const q = Math.round(t * 255) / 255; return [0.55 * q, 0.7 * q, q]; });
    const o = run(compile(DB, { dbDither: 0 }, { frame: 1 }).transform, R, { x0: 0, y0: 500, x1: RW, y1: 520 });
    let e0 = 0, e1 = 0, c = 0;
    for (let y = 0; y < 20; y++) for (let x = 150; x < RW - 150; x++) { e0 += (R.b[(500 + y) * RW + x] - tru[x]) ** 2; e1 += (o.b[y * RW + x] - tru[x]) ** 2; c++; }
    e0 = Math.sqrt(e0 / c) * 1023; e1 = Math.sqrt(e1 / c) * 1023;
    ok(`Deband smooths an 8-bit ramp of ${per} px per code back toward the true ramp`, e1 < 0.5 * e0, `RMS error ${e0.toFixed(2)} to ${e1.toFixed(2)} ten-bit codes`);
  }
  {
    const RW = 900, RH = 1080, tru = new Float64Array(RW);
    const R = img(RW, RH, x => { const t = (20 + x / 10) / 255; tru[x] = t; const q = 3 * Math.round(t * 255 / 3) / 255; return [0.55 * q, 0.7 * q, q]; });
    const o = run(compile(DB, { dbDither: 0 }, { frame: 1 }).transform, R, { x0: 0, y0: 500, x1: RW, y1: 520 });
    let e0 = 0, e1 = 0, c = 0;
    for (let y = 0; y < 20; y++) for (let x = 150; x < RW - 150; x++) { e0 += (R.b[(500 + y) * RW + x] - tru[x]) ** 2; e1 += (o.b[y * RW + x] - tru[x]) ** 2; c++; }
    e0 = Math.sqrt(e0 / c) * 255; e1 = Math.sqrt(e1 / c) * 255;
    ok("Deband smooths the 3-code bands of a pushed sky at the default Threshold", e1 < 0.35 * e0, `RMS error ${e0.toFixed(2)} to ${e1.toFixed(2)} eight-bit codes`);
  }
  {
    const E = img(W, H, x => (x < W / 2 ? [0.1, 0.12, 0.2] : [0.18, 0.2, 0.28]));
    const o = db({ dbDither: 0 }, E);
    let m = 0; for (let y = 0; y < H; y++) for (const x of [W / 2 - 2, W / 2 - 1, W / 2, W / 2 + 1]) m = Math.max(m, Math.abs(o.g[y * W + x] - E.g[y * W + x]));
    ok("Deband never reaches across an edge", m < 1e-9, `largest change beside the edge ${(m * 255).toFixed(4)} codes`);
  }
  {
    const Ln = img(W, H, (x, y) => (y === 60 ? [0.5, 0.5, 0.55] : [0.06, 0.07, 0.12]));
    const o = db({ dbDither: 0 }, Ln);
    let m = 0; for (let x = 0; x < W; x++) m = Math.max(m, Math.abs(o.r[60 * W + x] - 0.5));
    ok("Deband keeps a thin line", m < 1e-9, `largest change on the line ${m.toExponential(2)}`);
  }
  {
    const o = db({ dbDither: 0 }, tex);
    ok("Deband leaves texture alone", diff(o, tex).mean * 255 < 0.05, `mean change ${(diff(o, tex).mean * 255).toFixed(4)} codes`);
  }
  {
    const F = img(W, H, () => [0.1, 0.12, 0.2]);
    const o1 = db({}, F, 5), o2 = db({}, F, 6);
    let m = 0, v = 0, c = 0, nn = 0, fd = 0;
    for (let i = 0; i < W * H; i++) { const d = o1.g[i] - 0.12; m += d; v += d * d; if (o1.g[i] !== o2.g[i]) fd++; }
    m /= W * H; v /= W * H;
    for (let y = 0; y < H; y++) for (let x = 0; x < W - 1; x++) { c += (o1.g[y * W + x] - 0.12) * (o1.g[y * W + x + 1] - 0.12); nn++; }
    const sd = Math.sqrt(v) * 255, rho = c / nn / v;
    ok("Deband dithers about half a code, zero mean", sd > 0.4 && sd < 0.7 && Math.abs(m * 255) < 0.02, `spread ${sd.toFixed(3)} codes, mean ${(m * 255).toFixed(4)}`);
    ok("Deband's dither is new each frame and blue-leaning", fd > 0.95 * W * H && rho < -0.05, `changed ${(fd / (W * H)).toFixed(3)}, neighbour correlation ${rho.toFixed(3)}`);
  }
  {
    const K = img(W, H, () => [0, 0, 0]), Wh = img(W, H, () => [1, 1, 1]);
    ok("Deband keeps pure black and pure white clean", diff(db({ dbDither: 3 }, K), K).n === 0 && diff(db({ dbDither: 3 }, Wh), Wh).n === 0, "");
  }
  {
    const half = img(W, H, (x, y) => (x < W / 2 ? [0.08, 0.09, 0.15] : [tex.r[y * W + x], tex.g[y * W + x], tex.b[y * W + x]]));
    const o = db({ dbView: 1 }, half);
    let a = 0, b = 0, na = 0, nb = 0;
    for (let y = 10; y < H - 10; y++) for (let x = 10; x < W - 10; x++) { if (x < W / 2 - 30) { a += o.g[y * W + x]; na++; } else if (x > W / 2 + 30) { b += o.g[y * W + x]; nb++; } }
    ok("Deband View 1 shows where it smooths", a / na > 0.95 && b / nb < 0.1, `flat ${(a / na).toFixed(3)}, texture ${(b / nb).toFixed(3)}`);
  }
  {
    let bad = 0;
    const R = img(W, H, x => { const q = Math.round((10 + x / 30) * 1) / 255; return [q, q, q]; });
    for (let k = 0; k < 30; k++) {
      const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd();
      for (const im of [tex, R]) { const o = db(P, im, 1 + k); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
    }
    ok("Deband range over 30 slider sets", bad === 0, `bad ${bad}`);
  }
  {
    const stats = (H, grain) => {
      const W = 300, n = W * H, F = { w: W, h: H, r: new Float32Array(n).fill(0.1), g: new Float32Array(n).fill(0.12), b: new Float32Array(n).fill(0.2) };
      const y0 = Math.floor(H / 2) - 40, rows = 80;
      const o = run(compile(DB, { dbGrain: grain }, { frame: 5 }).transform, F, { x0: 0, y0, x1: W, y1: y0 + rows });
      const cell = 1 + (grain - 1) * H / 1080, lag = Math.max(1, Math.round(cell));
      let v = 0, c = 0, nn = 0;
      const par = [[0, 0], [0, 0]];
      for (let y = 0; y < rows; y++) for (let x = 0; x < W; x++) {
        const d = o.g[y * W + x] - 0.12; v += d * d;
        const k = (x % 2) ^ ((y0 + y) % 2); par[k][0] += d * d; par[k][1]++;
        if (x + lag < W) { c += d * (o.g[y * W + x + lag] - 0.12); nn++; }
      }
      v /= W * rows;
      const sp = q => Math.sqrt(q[0] / q[1]) * 255;
      return { sd: Math.sqrt(v) * 255, rho: c / nn / v, par: sp(par[1]) / sp(par[0]), lag };
    };
    const a = stats(1080, 1), b = stats(2160, 1), g = stats(1080, 2.5), u = stats(2160, 1.75);
    const info = s => `spread ${s.sd.toFixed(3)}, lag ${s.lag} corr ${s.rho.toFixed(3)}, odd/even ${s.par.toFixed(3)}`;
    ok("Deband's dither at 2160 rows is 1080's (spread and neighbour correlation)", Math.abs(b.sd / a.sd - 1) < 0.05 && Math.abs(b.rho - a.rho) < 0.05,
      `1080: ${info(a)}; 2160: ${info(b)}`);
    ok("Deband's grain on a cell between lattice points keeps its judged strength at 1080 and 2160, anti-correlated one cell along",
      Math.abs(g.sd / 0.368 - 1) < 0.03 && Math.abs(u.sd / g.sd - 1) < 0.05 && [g, u].every(s => Math.abs(s.par - 1) < 0.08 && s.rho < -0.05),
      `cell 2.5 at 1080: ${info(g)}; cell 2.5 at 2160: ${info(u)}`);
  }
}
console.log(fails ? `${fails} of ${count} FAILED` : `all ${count} pass`);
process.exit(fails ? 1 : 0);
