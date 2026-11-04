import { compile } from "../../tests/cpu/dctl.mjs";

const F = "build/Develop Optics.dctl", SK = "../art/build/Develop Art.dctl";
let s = 31;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function image(W, H, fill) {
  const n = W * H, A = { W, H, n, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let i = 0; i < n; i++) { const c = fill(i, i % W, (i / W) | 0); A.r[i] = c[0]; A.g[i] = c[1]; A.b[i] = c[2]; }
  return A;
}
function run(P, frame, A, file = F) {
  const T = compile(file, P, { frame }).transform;
  const o = { r: new Float32Array(A.n), g: new Float32Array(A.n), b: new Float32Array(A.n) };
  const R = { d: A.r, w: A.W }, G = { d: A.g, w: A.W }, Bt = { d: A.b, w: A.W };
  for (let y = 0; y < A.H; y++) for (let x = 0; x < A.W; x++) { const c = T(A.W, A.H, x, y, R, G, Bt), i = y * A.W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z; }
  return o;
}
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const NAMES = ["Pastel", "Pencil", "Rainbow", "Soft Light", "Star", "Flag / Dot"];
const Y = (o, i) => 0.2126 * o.r[i] + 0.7152 * o.g[i] + 0.0722 * o.b[i];
const meanY = (o, W, x0, y0, x1, y1) => { let m = 0, n = 0; for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) { m += Y(o, y * W + x); n++; } return m / n; };
const flat = (W, H, c) => image(W, H, () => c);
const lin = v => Math.pow(Math.max(v, 0), 2.4);
const A = image(240, 135, (i, x, y) => { if (Math.hypot(x - 60, y - 40) < 2) return [1, 1, 1]; const v = 0.3 + 0.25 * Math.sin(x / 9) * Math.cos(y / 7) + 0.1 * rnd(); return [Math.min(1, v * 1.1), Math.min(1, v), Math.min(1, 0.8 * v)]; });

for (let m = 0; m < 6; m++) {
  const P = { opAmount: 0 }; for (const [nm, v] of Object.entries(compile(F, {}, { frame: 1 }).sliders)) if (nm !== "opAmount") P[nm] = v.hi;
  P.opMode = m;
  const o = run(P, 10, A); let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < A.n; i++) if (o[k][i] !== A[k][i]) d++;
  ok(`${NAMES[m]}: off is identity`, d === 0, `differ ${d}`);
}
for (let m = 0; m < 6; m++) {
  const a1 = run({ opMode: m }, 236, A), a2 = run({ opMode: m }, 236, A), a3 = run({ opMode: m }, 238, A), b1 = run({ opMode: m }, 260, A);
  const h1 = run({ opMode: m, opBoil: 0 }, 236, A), h2 = run({ opMode: m, opBoil: 0 }, 260, A);
  let rep = 0, same = 0, mov = 0, held = 0, chg = 0;
  for (let i = 0; i < A.n; i++) { if (a1.g[i] !== a2.g[i]) rep++; if (a1.g[i] !== a3.g[i]) same++; if (a1.g[i] !== b1.g[i]) mov++; if (h1.g[i] !== h2.g[i]) held++; if (Math.abs(a1.g[i] - A.g[i]) > 0.004) chg++; }
  const boils = m < 2;
  ok(`${NAMES[m]}: repeats, ${boils ? "boils (Boil 0 holds)" : "holds still"}, changes the picture`, rep === 0 && same === 0 && held === 0 && (boils ? mov > 1000 : mov === 0) && chg > 100,
     `repeat ${rep}, within a boil ${same}, moved ${mov}, at Boil 0 ${held}, changed ${chg}`);
}

function dirE(o, W, H, x0, y0, x1, y1) {
  const L = new Float32Array(W * H); for (let i = 0; i < W * H; i++) L[i] = Y(o, i);
  const hp = (x, y) => { let m = 0; for (let j = -2; j <= 2; j++) for (let i = -2; i <= 2; i++) m += L[(y + j) * W + x + i]; return L[y * W + x] - m / 25; };
  let eh = 0, ev = 0; for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) { const c = hp(x, y); eh += (hp(x + 1, y) - c) ** 2; ev += (hp(x, y + 1) - c) ** 2; }
  return { eh, ev };
}
const SW = 320, SH = 1080;
{ const g = flat(SW, SH, [0.5, 0.5, 0.5]);
  const h0 = dirE(run({ opMode: 0, opAngle: 0 }, 1, g), SW, SH, 20, 300, 300, 700), h9 = dirE(run({ opMode: 0, opAngle: 90 }, 1, g), SW, SH, 20, 300, 300, 700);
  ok("Pastel: strokes run the hand's way (Angle 0 along x, 90 along y)", h0.ev > 1.15 * h0.eh && h9.eh > 1.15 * h9.ev, `Angle 0 ev/eh ${(h0.ev / h0.eh).toFixed(2)}, Angle 90 eh/ev ${(h9.eh / h9.ev).toFixed(2)}`); }
{ const dk = flat(SW, SH, [0.30, 0.08, 0.08]), o = run({ opMode: 0 }, 1, dk), my = meanY(o, SW, 20, 300, 300, 700);
  let mr = 0, mb = 0, sd = 0, n = 0; for (let y = 300; y < 700; y++) for (let x = 20; x < 300; x++) { const i = y * SW + x; mr += o.r[i]; mb += o.b[i]; n++; }
  for (let y = 300; y < 700; y++) for (let x = 20; x < 300; x++) sd += (Y(o, y * SW + x) - my) ** 2;
  sd = Math.sqrt(sd / n);
  ok("Pastel: chalk lifts a dark red and keeps it red, the paper's tooth showing", my > 0.2126 * 0.3 + 0.7152 * 0.08 + 0.0722 * 0.08 + 0.03 && mr / n > 1.6 * mb / n && sd > 0.01, `luma ${my.toFixed(3)} (in 0.127), red ${(mr / n).toFixed(3)} blue ${(mb / n).toFixed(3)}, texture sd ${sd.toFixed(3)}`); }
{ const e = image(SW, SH, (i, x) => (x < 160 ? [0.75, 0.12, 0.10] : [0.10, 0.20, 0.75])), o = run({ opMode: 0 }, 1, e);
  let lr = 0, lb = 0, rr = 0, rb = 0; for (let y = 300; y < 700; y++) { for (let x = 150; x < 156; x++) { lr += o.r[y * SW + x]; lb += o.b[y * SW + x]; } for (let x = 164; x < 170; x++) { rr += o.r[y * SW + x]; rb += o.b[y * SW + x]; } }
  ok("Pastel: strokes stop at an edge (red stays left of it, blue right, 4 to 10 px off)", lr > 2 * lb && rb > 2 * rr, `left red/blue ${(lr / lb).toFixed(2)}, right blue/red ${(rb / rr).toFixed(2)}`); }
{ const t = [0.2, 0.5, 0.8].map(v => meanY(run({ opMode: 1 }, 1, flat(SW, SH, [v, v, v])), SW, 20, 300, 300, 700));
  const w = meanY(run({ opMode: 1 }, 1, flat(SW, SH, [0.97, 0.97, 0.97])), SW, 20, 300, 300, 700);
  ok("Pencil: tone in order, white stays paper", t[0] < t[1] - 0.05 && t[1] < t[2] - 0.05 && w > 0.9, `0.2 to ${t[0].toFixed(3)}, 0.5 to ${t[1].toFixed(3)}, 0.8 to ${t[2].toFixed(3)}, white ${w.toFixed(3)}`); }
{ const g = flat(SW, SH, [0.45, 0.45, 0.45]), hand = dirE(run({ opMode: 1, opAngle: 0, opSoft: 0 }, 1, g), SW, SH, 20, 300, 300, 700);
  const gr = image(SW, SH, (i, x) => { const v = 0.45 + 0.25 * Math.sin(x * 2 * Math.PI / 24); return [v, v, v]; }), form = dirE(run({ opMode: 1, opAngle: 0, opSoft: 0 }, 1, gr), SW, SH, 20, 300, 300, 700);
  ok("Pencil: strokes follow the forms (across a tone running along x they turn to y), the hand's angle where flat", hand.ev > 1.2 * hand.eh && form.eh > 1.2 * form.ev, `flat ev/eh ${(hand.ev / hand.eh).toFixed(2)}, form eh/ev ${(form.eh / form.ev).toFixed(2)}`); }
{ const g = flat(SW, SH, [0.45, 0.45, 0.45]), pn = meanY(run({ opMode: 1 }, 1, g), SW, 20, 300, 300, 700), sk = meanY(run({ arMode: 5 }, 1, g, SK), SW, 20, 300, 300, 700);
  ok("Pencil: builds the tone where ART's Sketch only shades (a flat 0.45 grey)", sk - pn > 0.1, `Pencil ${pn.toFixed(3)}, Sketch ${sk.toFixed(3)}`); }

{ const W = 480, H = 270, o = run({ opMode: 2, opLevel: 100 }, 1, flat(W, H, [0, 0, 0])), x = 240;
  const peak = (k, y0, y1) => { let best = -1, by = 0; for (let y = y0; y < y1; y++) if (o[k][y * W + x] > best) { best = o[k][y * W + x]; by = y; } return by; };
  const top = Math.round(0.35 * H), sec = Math.round((0.35 + 1 - 51.9 / 42.3) * H);
  const pr = peak("r", top - 15, top + 25), pb = peak("b", top - 15, top + 25), sr = peak("r", sec - 25, sec + 15), sb = peak("b", sec - 25, sec + 15);
  ok("Rainbow: primary red outside blue, secondary reversed above it", pr < pb && sb < sr && sr < pr - 20, `primary red row ${pr}, blue ${pb}; secondary red ${sr}, blue ${sb}`);
  const gy = flat(W, H, [0.35, 0.35, 0.35]), og = run({ opMode: 2, opLevel: 100, opSoft: 0 }, 1, gy);
  const R = H, cy = 0.35 * H + R, rowAt = th => Math.round(cy - R * th / 42.3);
  const band = meanY(og, W, 230, rowAt(48), 250, rowAt(45)), inside = meanY(og, W, 230, rowAt(38), 250, rowAt(35));
  ok("Rainbow: the dark band between the bows, the sky brighter inside", band < 0.35 - 0.005 && inside > 0.35 + 0.005, `band ${band.toFixed(3)}, inside ${inside.toFixed(3)} (in 0.350)`); }

{ const W = 480, H = 270, sh = image(W, H, (i, x, y) => (Math.abs(x - 240) < 8 && Math.abs(y - 135) < 8 ? [0.15, 0.15, 0.15] : [0.6, 0.6, 0.6]));
  const o = run({ opMode: 3, opX: 50, opY: 50 }, 1, sh), c = meanY(o, W, 237, 132, 243, 138), su = meanY(o, W, 200, 132, 210, 138);
  ok("Soft Light: the shadow is filled (less contrast to its surround)", su / c < 0.6 / 0.15 * 0.7, `surround/shadow ${(su / c).toFixed(2)} (in 4.00)`);
  const g = flat(W, H, [0.5, 0.5, 0.5]), wa = run({ opMode: 3, opWarm: 80, opX: 50, opY: 50 }, 1, g), co = run({ opMode: 3, opWarm: -80, opX: 50, opY: 50 }, 1, g), i = 135 * W + 240;
  ok("Soft Light: Warmth tints the light warm above 0, cool below", wa.r[i] > wa.b[i] + 0.03 && co.b[i] > co.r[i] + 0.03, `warm r ${wa.r[i].toFixed(3)} b ${wa.b[i].toFixed(3)}; cool r ${co.r[i].toFixed(3)} b ${co.b[i].toFixed(3)}`); }

{ const W = 540, H = 540, cx = 270, cy = 270, pt = image(W, H, (i, x, y) => (Math.hypot(x - cx, y - cy) < 2 ? [1, 1, 1] : [0.02, 0.02, 0.02]));
  const ray = (o, deg) => { let m = 0; for (let d = 20; d < 70; d++) { const x = Math.round(cx + d * Math.cos(deg * Math.PI / 180)), y = Math.round(cy + d * Math.sin(deg * Math.PI / 180)); m += Y(o, y * W + x); } return m / 50; };
  for (const p of [4, 6, 8]) {
    const o = run({ opMode: 4, opPoints: p, opAngle: 60 }, 1, pt), step = 360 / p;
    let on = 0, off = 0; for (let k = 0; k < p; k++) { on += ray(o, 60 + k * step) / p; off += ray(o, 60 + k * step + step / 2) / p; }
    ok(`Star: ${p} points make ${p} arms along Angle`, on > 5 * off && on > 0.1, `along the arms ${on.toFixed(3)}, between ${off.toFixed(3)}`);
  }
  const o = run({ opMode: 4, opPoints: 4, opAngle: 0, opColour: 100 }, 1, pt);
  const rb = d => o.r[cy * W + cx + d] / o.b[cy * W + cx + d];
  ok("Star: Colour sends red further than blue toward the tips", rb(55) > 1.15 * rb(12), `red/blue at 12 px ${rb(12).toFixed(2)}, at 55 px ${rb(55).toFixed(2)}`);
  const half = image(W, H, (i, x) => (x < 200 ? [0.97, 0.97, 0.97] : [0.05, 0.05, 0.05])), oh = run({ opMode: 4, opLevel: 100 }, 1, half);
  let add = 0; for (let y = 200; y < 340; y++) for (let x = 230; x < 300; x++) add = Math.max(add, Y(oh, y * W + x) - 0.05);
  ok("Star: a broad bright area throws no wall of light (60 px off its edge)", add < 0.04, `most added ${add.toFixed(3)}`);
  const lo = image(240, 135, (i, x, y) => [0.2 + 0.5 * x / 240, 0.3, 0.6 * y / 135]), ol = run({ opMode: 4 }, 1, lo); let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < lo.n; i++) if (ol[k][i] !== lo[k][i]) d++;
  ok("Star: a picture under Threshold comes back exactly", d === 0, `differ ${d}`); }

{ const W = 480, H = 270, g = flat(W, H, [0.5, 0.5, 0.5]), o = run({ opMode: 5, opX: 50, opY: 50, opAspect: 50 }, 1, g), c = (135 * W + 240);
  const stops = Math.log2(lin(0.5) / lin(Y(o, c)));
  ok("Flag / Dot: the middle loses between 0.8 and 2 stops at Level 50, the corner untouched", stops > 0.8 && stops < 2 && o.g[2 * W + 2] === 0.5, `${stops.toFixed(2)} stops, corner ${o.g[2 * W + 2]}`);
  const s = (0.04 + 0.0046 * 50) * H, P = { opMode: 5, opX: 50, opY: 50, opAspect: 50, opSoft: 0, opAngle: 0 };
  const dot = run({ ...P, opRound: 100 }, 1, g), fl = run({ ...P, opRound: 0 }, 1, g);
  const at = (o, dx, dy) => Y(o, Math.round(135 + dy) * W + Math.round(240 + dx));
  const r1 = at(dot, 0.8 * s, 0), r2 = at(dot, 0.8 * s / Math.SQRT2, 0.8 * s / Math.SQRT2), dg = 0.88 * s;
  ok("Flag / Dot: a dot is round, a flag keeps its corners", Math.abs(r1 - r2) < 0.01 && at(fl, dg, dg) < at(dot, dg, dg) - 0.1, `dot at 0.8 of its radius ${r1.toFixed(3)} and ${r2.toFixed(3)}; at the corner flag ${at(fl, dg, dg).toFixed(3)}, dot ${at(dot, dg, dg).toFixed(3)}`);
  const tw = image(W, H, (i, x) => (x < 240 ? [0.85, 0.85, 0.85] : [0.06, 0.06, 0.06])), ot = run({ opMode: 5, opX: 50, opY: 50, opAspect: 50, opAngle: 0 }, 1, tw);
  const sb = Math.log2(lin(0.85) / lin(Y(ot, 135 * W + 236))), sdk = Math.log2(lin(0.06) / lin(Y(ot, 135 * W + 244)));
  ok("Flag / Dot: brights lose more stops than deep shadows", sb > sdk + 0.3, `bright ${sb.toFixed(2)} stops, shadow ${sdk.toFixed(2)}`); }

{ const { sliders } = compile(F, {}, { frame: 1 }); let bad = 0; const sm = image(96, 54, () => [rnd(), rnd(), rnd()]);
  for (let k = 0; k < 30; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd(); P.opMode = k % 6; P.opPoints = 4 + 2 * Math.floor(rnd() * 3);
    const o = run(P, Math.floor(rnd() * 999), sm); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok("range over 30 slider sets", bad === 0, `bad ${bad}`); }
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
