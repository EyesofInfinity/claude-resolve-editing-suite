import { compile } from "../../tests/cpu/dctl.mjs";

const TX = "build/Develop Texture.dctl", FI = "build/Develop Filter.dctl";
let s = 23;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function image(W, H, fill) {
  const n = W * H, A = { W, H, n, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let i = 0; i < n; i++) { const c = fill(i, i % W, (i / W) | 0); A.r[i] = c[0]; A.g[i] = c[1]; A.b[i] = c[2]; }
  return A;
}
function run(F, P, frame, A) {
  const T = compile(F, P, { frame }).transform;
  const o = { r: new Float32Array(A.n), g: new Float32Array(A.n), b: new Float32Array(A.n) };
  const R = { d: A.r, w: A.W }, G = { d: A.g, w: A.W }, B = { d: A.b, w: A.W };
  for (let y = 0; y < A.H; y++) for (let x = 0; x < A.W; x++) { const c = T(A.W, A.H, x, y, R, G, B), i = y * A.W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z; }
  return o;
}
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const mean = (o, k, A, f = () => true) => { let m = 0, c = 0; for (let i = 0; i < A.n; i++) if (f(i)) { m += o[k][i]; c++; } return m / c; };
const KINDS = ["Cells", "Flux", "Neurons", "Ridges", "Folded", "Plasma", "Weave"];
const W = 320, H = 180;
const chart = image(W, H, (i, x, y) => [x / W, y / H, 0.5 + 0.5 * Math.sin(x / 7 + y / 11)]);
const grey = image(W, H, () => [0.5, 0.5, 0.5]);
const supers = image(W, H, (i, x) => [x % 3 === 0 ? 1.4 : -0.1, 0.3, 0.7]);

for (const [F, amt] of [[TX, "txAmount"], [FI, "fiAmount"]]) {
  const { sliders } = compile(F, {}, { frame: 1 });
  const P = { [amt]: 0 }; for (const [nm, v] of Object.entries(sliders)) if (nm !== amt) P[nm] = v.hi;
  for (const A of [chart, supers]) {
    const o = run(F, P, 17, A); let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < A.n; i++) if (o[k][i] !== A[k][i]) d++;
    ok(`${F.slice(6)}: Amount 0 is identity${A === supers ? " (superwhite, negative)" : ""}`, d === 0, `differ ${d}`);
  }
}

for (let k = 0; k < KINDS.length; k++) {
  const a1 = run(TX, { txKind: k }, 236, grey), a2 = run(TX, { txKind: k }, 236, grey), b1 = run(TX, { txKind: k }, 260, grey);
  const h1 = run(TX, { txKind: k, txSpeed: 0 }, 236, grey), h2 = run(TX, { txKind: k, txSpeed: 0 }, 900, grey);
  let rep = 0, mov = 0, hold = 0, lo = 1, hi = 0;
  for (let i = 0; i < grey.n; i++) { if (a1.g[i] !== a2.g[i]) rep++; if (Math.abs(a1.g[i] - b1.g[i]) > 2e-3) mov++; if (h1.g[i] !== h2.g[i]) hold++; lo = Math.min(lo, a1.g[i]); hi = Math.max(hi, a1.g[i]); }
  ok(`Texture ${KINDS[k]}: repeats, moves 24 frames on, Speed 0 holds, has structure`, rep === 0 && mov > 0.05 * grey.n && hold === 0 && hi - lo > 0.15,
     `repeat ${rep}, moved ${mov}, held-diff ${hold}, range ${lo.toFixed(2)}-${hi.toFixed(2)}`);
}
{ let worst = 0, wk = "";
  for (let k = 0; k < KINDS.length; k++) { const o = run(TX, { txKind: k, txHue: 0, txColour: 0 }, 236, grey); const v = Array.from(o.g).sort((a, b) => a - b);
    const d = Math.abs(v[v.length >> 1] - 0.5); if (d > worst) { worst = d; wk = KINDS[k]; } }
  ok("Texture Overlay keeps a grey picture's median within 0.03 for every Kind", worst < 0.03, `worst ${worst.toFixed(3)} (${wk})`); }
{ let bad = 0, lit = 0; for (let k = 0; k < KINDS.length; k++) { const o = run(TX, { txKind: k, txBlend: 1 }, 236, chart);
    for (let i = 0; i < chart.n; i++) { if (o.g[i] > chart.g[i] + 1e-6 || o.r[i] > chart.r[i] + 1e-6) bad++; if (o.g[i] < chart.g[i] - 0.02) lit++; } }
  ok("Texture Multiply only darkens, and darkens", bad === 0 && lit > 0.2 * chart.n * 7, `brightened ${bad}, darkened ${lit}`); }
{ let bad = 0, add = 0; for (let k = 0; k < KINDS.length; k++) { const o = run(TX, { txKind: k, txBlend: 2, txHue: 0, txColour: 0 }, 236, chart);
    for (let i = 0; i < chart.n; i++) { if (o.g[i] < chart.g[i] - 1e-6 && chart.g[i] < 0.8) bad++; if (o.g[i] > chart.g[i] + 0.02) add++; } }
  const black = image(W, H, () => [0, 0, 0]), o = run(TX, { txKind: 2, txBlend: 2 }, 236, black);
  let dark = 0; for (let i = 0; i < black.n; i++) if (o.g[i] < 1 / 255) dark++;
  ok("Texture Screen only adds light; Neurons on black leave at least the darker half of the ground black", bad === 0 && add > 0 && dark > 0.45 * black.n, `darkened ${bad}, lit ${add}, black kept ${(dark / black.n * 100).toFixed(0)}%`); }
{ const o = run(TX, { txKind: 0, txBlend: 3, txStrength: 100 }, 236, chart); let moved = 0, out = 0;
  for (let i = 0; i < chart.n; i++) { if (Math.abs(o.r[i] - chart.r[i]) > 0.01) moved++; if (o.r[i] < -1e-6 || o.r[i] > 1 + 1e-6) out++; }
  let far = 0; for (let i = 0; i < chart.n; i++) if (Math.abs(o.r[i] - chart.r[i]) * W > 50) far++;
  ok("Texture Displace shifts the picture by a bounded amount", moved > 0.1 * chart.n && out === 0 && far === 0, `moved ${moved}, out of range ${out}, over 50 px ${far}`); }
{ const o = run(TX, { txKind: 0, txStrength: 62, txSpeed: 0 }, 1, grey); let wall = 0, darkc = 0;
  for (let i = 0; i < grey.n; i++) { if (o.g[i] > 0.85) wall++; if (o.g[i] < 0.35) darkc++; }
  ok("Cells: thin light walls (under 25% of pixels), dark nuclei", wall > 0.03 * grey.n && wall < 0.25 * grey.n && darkc > 0.01 * grey.n, `walls ${(wall / grey.n * 100).toFixed(1)}%, nuclei ${(darkc / grey.n * 100).toFixed(1)}%`); }
{ const o = run(TX, { txKind: 2, txBlend: 2, txStrength: 100 }, 236, image(W, H, () => [0, 0, 0]));
  const v = Array.from(o.g).sort((a, b) => a - b), p75 = v[Math.floor(0.75 * v.length)], p98 = v[Math.floor(0.98 * v.length)];
  let greenish = 0, lit = 0; for (let i = 0; i < grey.n; i++) if (o.g[i] > 0.05) { lit++; if (o.g[i] > o.r[i] && o.g[i] > o.b[i]) greenish++; }
  ok("Neurons: sparse bright lines on a dark ground, green", p98 > 4 * p75 && p98 > 0.3 && greenish === lit, `p75 ${p75.toFixed(3)}, p98 ${p98.toFixed(3)}, green ${greenish} of ${lit}`); }
{ const o = run(TX, { txKind: 1, txSpeed: 0 }, 1, grey); let dx = 0, dy = 0;
  for (let y = 1; y < H; y++) for (let x = 1; x < W; x++) { const i = y * W + x; dx += Math.abs(o.g[i] - o.g[i - 1]); dy += Math.abs(o.g[i] - o.g[i - W]); }
  ok("Flux: streamlines run across (change along x under change along y)", dx < 0.8 * dy, `along x ${dx.toFixed(0)}, along y ${dy.toFixed(0)}`); }
for (const k of [3, 4]) {
  const o = run(TX, { txKind: k, txStrength: 62, txSpeed: 0 }, 1, grey);
  let lo = 0, hi = 0; for (let i = 0; i < grey.n; i++) { if (o.g[i] < 0.45) lo++; if (o.g[i] > 0.55) hi++; }
  ok(`${KINDS[k]}: lit relief has light and shade`, lo > 0.02 * grey.n && hi > 0.02 * grey.n, `shade ${lo}, light ${hi}`);
}
{ const WW = 200, HH = 1080, gg = image(WW, HH, () => [0.5, 0.5, 0.5]), o = run(TX, { txKind: 6, txSpeed: 0, txSize: 0 }, 1, gg);
  const pitch = 7 + 18 * 0.05 / 0.4; const ac = d => { let s2 = 0; for (let y = 0; y < HH; y += 2) for (let x = 0; x + d < WW; x++) { const i = y * WW + x; s2 += (o.g[i] - 0.5) * (o.g[i + d] - 0.5); } return s2; };
  ok("Weave: repeats at the thread pitch", ac(Math.round(pitch)) > 0 && ac(Math.round(pitch / 2)) < ac(Math.round(pitch)), `ac(p) ${ac(Math.round(pitch)).toFixed(1)}, ac(p/2) ${ac(Math.round(pitch / 2)).toFixed(1)}`); }

const C = { grey: [0.5, 0.5, 0.5], sky: [0.45, 0.62, 0.92], leaf: [0.30, 0.50, 0.15], red: [0.8, 0.15, 0.1], white: [1, 1, 1] };
const names = Object.keys(C), sw = image(names.length, 1, i => C[names[i]]);
const one = (P) => { const o = run(FI, P, 1, sw); const r = {}; names.forEach((k, i) => { r[k] = [o.r[i], o.g[i], o.b[i]]; }); return r; };
const Y = c => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
{ let worst = 0; for (let f = 0; f <= 27; f++) { const r = one({ fiFilter: f, fiStrength: 0, fiFilm: 1 }); for (const k of names) for (let c = 0; c < 3; c++) worst = Math.max(worst, Math.abs(r[k][c] - C[k][c])); }
  ok("Filter Strength 0 is clear glass (colour, every filter)", worst < 2e-3, `worst ${worst.toExponential(2)}`); }
{ const rb = f => { const g = one({ fiFilter: f }).grey; return g[0] - g[2]; };
  const w = [4, 5, 0, 1].map(rb), c = [6, 7, 3, 2].map(rb);
  const mono = arr => arr.every((v, i) => i === 0 || v > arr[i - 1]);
  const yk = [0, 2, 5, 18, 20].map(f => Math.abs(Y(one({ fiFilter: f }).grey) - 0.5));
  ok("Filter warming 81A < 81EF < 85 < 85B, cooling 82A < 82C < 80B < 80A, grey's brightness kept within 0.05", mono(w) && w[0] > 0 && mono(c.map(v => -v)) && c[0] < 0 && Math.max(...yk) < 0.05,
     `warm ${w.map(v => v.toFixed(3))}, cool ${c.map(v => v.toFixed(3))}, Y off ${Math.max(...yk).toFixed(3)}`); }
{ const g = f => one({ fiFilter: f }); const sk = f => g(f).sky[0], rd = f => g(f).red[0];
  const neutral = [8, 9, 14, 16].every(f => { const c = g(f).grey; return Math.abs(c[0] - c[1]) < 1e-9 && Math.abs(c[1] - c[2]) < 1e-9 && Math.abs(c[0] - 0.5) < 0.03; });
  const order = sk(8) > sk(9) && sk(9) > sk(11) && sk(11) > sk(13) && sk(13) > sk(14) && sk(14) > sk(15);
  ok("Filter B&W: grey neutral; sky darkens pan > 8 > 15 > 23A > 25 > 29; red lightens under 25, darkens under 47; 47 lightens sky",
     neutral && order && rd(14) > rd(8) + 0.1 && rd(16) < rd(8) - 0.1 && sk(16) > sk(8),
     `sky ${[8, 9, 11, 13, 14, 15, 16].map(f => sk(f).toFixed(2))}, red pan ${rd(8).toFixed(2)} 25 ${rd(14).toFixed(2)} 47 ${rd(16).toFixed(2)}`); }
{ const lf = f => one({ fiFilter: f }).leaf[0]; ok("Filter B&W: 11 and 58 lighten foliage", lf(10) > lf(8) && lf(17) > lf(8), `pan ${lf(8).toFixed(3)}, 11 ${lf(10).toFixed(3)}, 58 ${lf(17).toFixed(3)}`); }
{ const pr = one({ fiFilter: 25 }).grey, cg = one({ fiFilter: 24 }).grey, pg = one({ fiFilter: 21 }).grey, mg = one({ fiFilter: 22 }).grey;
  ok("Filter gels: primary red red, deep violet violet, plus green green, minus green magenta", pr[0] > 5 * pr[1] && cg[2] > cg[0] && cg[0] > 2 * cg[1] && pg[1] > pg[0] && pg[1] > pg[2] && mg[1] < mg[0] && mg[1] < mg[2],
     `red ${pr.map(v => v.toFixed(2))}, violet ${cg.map(v => v.toFixed(2))}, +g ${pg.map(v => v.toFixed(2))}, -g ${mg.map(v => v.toFixed(2))}`); }
{ const a = one({ fiFilter: 4 }).grey, b = one({ fiFilter: 4, fiStrength: 200 }).grey; ok("Filter Strength 200 thickens (81A)", b[0] - b[2] > 1.5 * (a[0] - a[2]), `${(a[0] - a[2]).toFixed(3)} to ${(b[0] - b[2]).toFixed(3)}`); }
{ const skyImg = image(64, 36, () => C.sky);
  const at = (P) => { const o = run(FI, { fiFilter: 28, ...P }, 1, skyImg); return [o.r[18 * 64 + 32], o.g[18 * 64 + 32], o.b[18 * 64 + 32]]; };
  const s90 = at({ fiSunAz: 90, fiSunEl: 0 }), s180 = at({ fiSunAz: 180, fiSunEl: 0 }), t45 = at({ fiTurn: 45 }), t90 = at({ fiTurn: 90 });
  const gw = one({ fiFilter: 28 }); const pass = Math.abs(gw.grey[1] - 0.5) < 2e-3 && Math.abs(gw.white[1] - 1) < 2e-3;
  ok("Polarizer: sky darkest 90 degrees from the sun, none with the sun behind, grey and white pass, Turn 45 none, 90 reverses",
     Y(s90) < Y(C.sky) - 0.12 && Math.abs(Y(s180) - Y(C.sky)) < 0.01 && pass && Math.abs(Y(t45) - Y(C.sky)) < 2e-3 && Y(t90) > Y(C.sky) + 0.05 && s90[2] > s90[0],
     `sky Y ${Y(C.sky).toFixed(3)}: 90 deg ${Y(s90).toFixed(3)}, behind ${Y(s180).toFixed(3)}, turn 45 ${Y(t45).toFixed(3)}, 90 ${Y(t90).toFixed(3)}`); }
{ const field = image(64, 36, (i, x, y) => ((x * 7 + y * 13) % 5 === 0 ? [0.55, 0.65, 0.45] : [0.25, 0.45, 0.12]));
  const rock = image(64, 36, (i, x, y) => ((x * 7 + y * 13) % 5 === 0 ? [0.7, 0.7, 0.7] : [0.4, 0.4, 0.4]));
  const P = { fiFilter: 28, fiSunAz: 180, fiHorizon: 0 }, of = run(FI, P, 1, field), orr = run(FI, P, 1, rock);
  const sat = (o, i) => (Math.max(o.r[i], o.g[i], o.b[i]) - Math.min(o.r[i], o.g[i], o.b[i]));
  const i0 = 18 * 64 + 30; let rk = 0; for (let i = 0; i < rock.n; i++) rk = Math.max(rk, Math.abs(orr.g[i] - rock.g[i]));
  ok("Polarizer glare: sheen on foliage cut (more saturated), grey rock untouched", sat(of, i0) > sat(field, i0) + 0.01 && rk < 1e-3,
     `foliage sat ${sat(field, i0).toFixed(3)} to ${sat(of, i0).toFixed(3)}, rock worst ${rk.toExponential(2)}`); }
{ const g = image(64, 36, () => [0.5, 0.5, 0.5]), o = run(FI, { fiFilter: 29, fiStops: 2, fiSoft: 20 }, 1, g), r = run(FI, { fiFilter: 30, fiStops: 2, fiSoft: 20 }, 1, g);
  const top = o.g[1 * 64 + 32], bot = o.g[34 * 64 + 32], lin = v => Math.pow(v, 2.4);
  const rl = r.g[Math.round(0.45 * 36 - 2) * 64 + 32], rt = r.g[1 * 64 + 32];
  ok("Grad ND: top two stops down, bottom untouched; Reverse densest at the line", Math.abs(lin(top) / lin(0.5) - 0.25) < 0.02 && Math.abs(bot - 0.5) < 2e-3 && rl < rt,
     `top ${(lin(top) / lin(0.5)).toFixed(3)} of the light, bottom ${bot.toFixed(4)}, reverse line ${rl.toFixed(3)} top ${rt.toFixed(3)}`); }

for (const F of [TX, FI]) {
  const { sliders } = compile(F, {}, { frame: 1 }); let bad = 0; const small = image(96, 54, () => [rnd() * 1.2 - 0.1, rnd(), rnd()]);
  for (let k = 0; k < 30; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd();
    for (const m of ["txKind", "txBlend", "fiFilter", "fiFilm", "fiGradCol"]) if (m in P) P[m] = Math.round(P[m]);
    const o = run(F, P, Math.floor(rnd() * 5000), small); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok(`${F.slice(6)}: range over 30 slider sets`, bad === 0, `bad ${bad}`);
}
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
