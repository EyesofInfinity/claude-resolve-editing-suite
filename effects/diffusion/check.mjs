import { compile } from "../../tests/cpu/dctl.mjs";

const F = "build/Develop Diffusion.dctl";
const NAMES = ["Black Mist", "Diffusion", "Fog", "Double Fog", "Frost", "Soft Focus", "Net", "Silk", "Center Spot", "Halo",
  "Atmospheric Glow", "Film Glow", "Smoke and Fog"];
let s = 31;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function image(W, H, fill) {
  const n = W * H, A = { W, H, n, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let i = 0; i < n; i++) { const c = fill(i, i % W, (i / W) | 0); A.r[i] = c[0]; A.g[i] = c[1]; A.b[i] = c[2]; }
  return A;
}
const tex = A => [{ d: A.r, w: A.W }, { d: A.g, w: A.W }, { d: A.b, w: A.W }];
function run(P, frame, A) {
  const T = compile(F, P, { frame }).transform, [R, G, B] = tex(A);
  const o = { r: new Float32Array(A.n), g: new Float32Array(A.n), b: new Float32Array(A.n) };
  for (let y = 0; y < A.H; y++) for (let x = 0; x < A.W; x++) { const c = T(A.W, A.H, x, y, R, G, B), i = y * A.W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z; }
  return o;
}
function boxAt(P, frame, A, x0, y0, x1, y1) {
  const T = compile(F, P, { frame }).transform, [R, G, B] = tex(A);
  let r = 0, g = 0, b = 0, n = 0;
  for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) { const c = T(A.W, A.H, x, y, R, G, B); r += c.x; g += c.y; b += c.z; n++; }
  r /= n; g /= n; b /= n;
  return { r, g, b, y: 0.2126 * r + 0.7152 * g + 0.0722 * b };
}
const inY = (A, x0, y0, x1, y1) => { let m = 0, n = 0; for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) { const i = y * A.W + x; m += 0.2126 * A.r[i] + 0.7152 * A.g[i] + 0.0722 * A.b[i]; n++; } return m / n; };
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const f3 = v => v.toFixed(3);
const { sliders } = compile(F, {}, { frame: 1 });

const A = image(96, 54, (i, x, y) => { if (Math.hypot(x - 30, y - 20) < 3) return [1, 1, 1]; const v = 0.3 + 0.25 * Math.sin(x / 5) * Math.cos(y / 4) + 0.1 * rnd(); return [Math.min(1, v * 1.1), Math.min(1, v), Math.min(1, 0.8 * v)]; });

for (let m = 0; m < 13; m++) {
  const P = { dfAmount: 0 }; for (const [nm, v] of Object.entries(sliders)) if (nm !== "dfAmount") P[nm] = v.hi;
  P.dfMode = m;
  const o = run(P, 10, A), o2 = run({ dfMode: m, dfStrength: 0 }, 10, A);
  let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < A.n; i++) { if (o[k][i] !== A[k][i]) d++; if (o2[k][i] !== A[k][i]) d++; }
  ok(`${NAMES[m]}: Amount 0 and Strength 0 are identity`, d === 0, `differ ${d}`);
}
for (let m = 0; m < 13; m++) {
  const a1 = run({ dfMode: m }, 236, A), a2 = run({ dfMode: m }, 236, A), b1 = run({ dfMode: m }, 290, A);
  let rep = 0, mov = 0, chg = 0;
  for (let i = 0; i < A.n; i++) { if (a1.g[i] !== a2.g[i]) rep++; if (a1.g[i] !== b1.g[i]) mov++; if (Math.abs(a1.g[i] - A.g[i]) > 0.004) chg++; }
  const moves = m === 12;
  ok(`${NAMES[m]}: repeats, ${moves ? "moves" : "holds still"}, changes the picture`, rep === 0 && (moves ? mov > 200 : mov === 0) && chg > (m === 9 || m === 11 ? 20 : 100),
     `repeat ${rep}, moved ${mov}, changed ${chg}`);
}

const W = 960, H = 540;
const lamp = image(W, H, (i, x, y) => (Math.hypot(x - 480, y - 270) < 10 ? [1, 1, 1] : [0.03, 0.03, 0.03]));
const half = image(W, H, (i, x) => (x < 480 ? [1, 1, 1] : [0.04, 0.04, 0.04]));
const grey = image(W, H, () => [0.4, 0.4, 0.4]);
const lift = (P, A0, x0, y0, x1, y1) => boxAt(P, 1, A0, x0, y0, x1, y1).y - inY(A0, x0, y0, x1, y1);

for (const m of [0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 11]) {
  const d = Math.abs(lift({ dfMode: m }, grey, 470, 260, 490, 280));
  ok(`${NAMES[m]}: a flat grey is left alone`, d < 0.004, `change ${d.toFixed(4)}`);
}

{ const near = lift({ dfMode: 0 }, lamp, 494, 266, 498, 274), far = lift({ dfMode: 0 }, lamp, 560, 266, 564, 274);
  ok("Black Mist: the lamp blooms beside it, the black 70 px off barely lifts", near > 0.05 && far < 0.02, `at 4 to 8 px ${f3(near)}, at 70 px ${f3(far)}`); }
const liftAt = {};
for (const m of [0, 1, 2, 3]) liftAt[m] = [lift({ dfMode: m }, half, 500, 260, 504, 280), lift({ dfMode: m }, half, 540, 260, 544, 280), lift({ dfMode: m }, half, 680, 260, 684, 280)];
{ const gh = image(W, H, (i, x) => (x < 480 ? [0.6, 0.6, 0.6] : [0.04, 0.04, 0.04]));
  const m0 = lift({ dfMode: 0 }, gh, 500, 260, 504, 280), m1 = lift({ dfMode: 1 }, gh, 500, 260, 504, 280);
  ok("Black Mist: beside a lit grey the shadow lifts only a little; Diffusion lifts it more than twice as much", m0 < 0.03 && m1 > 2 * m0, `at 20 px Black Mist ${f3(m0)}, Diffusion ${f3(m1)}`); }
ok("Fog: the veil lifts the blacks far from the light, where Black Mist barely does", liftAt[2][2] > 0.05 && liftAt[2][2] > 4 * liftAt[0][2], `at 200 px Fog ${f3(liftAt[2][2])}, Mist ${f3(liftAt[0][2])}`);
ok("Double Fog: a veil at least as strong as Fog's far out", liftAt[3][2] > 0.9 * liftAt[2][2], `at 200 px Double Fog ${f3(liftAt[3][2])}, Fog ${f3(liftAt[2][2])}`);
{ const st = (p) => image(W, H, (i, x) => (Math.floor(x / p) & 1 ? [0.7, 0.7, 0.7] : [0.2, 0.2, 0.2]));
  const fine = st(2), broad = st(32);
  const con = (m, A0, p) => { const a = boxAt({ dfMode: m }, 1, A0, 480 + p / 2 - 1, 260, 480 + p / 2, 280), b = boxAt({ dfMode: m }, 1, A0, 480 + p + p / 2 - 1, 260, 480 + p + p / 2, 280); return Math.abs(a.y - b.y); };
  const rf = con(2, fine, 2) / con(2, broad, 32), rd = con(3, fine, 2) / con(3, broad, 32);
  ok("Double Fog: fine detail keeps more of its contrast than under Fog", rd > rf * 1.03, `fine over broad Double Fog ${f3(rd)}, Fog ${f3(rf)}`);
  const top = lift({ dfMode: 3, dfDepth: 100 }, half, 700, 20, 704, 40), bot = lift({ dfMode: 3, dfDepth: 100 }, half, 700, 500, 704, 520);
  ok("Double Fog: Depth thickens the veil toward the top", top > bot * 1.5, `top ${f3(top)}, bottom ${f3(bot)}`); }

{ const red = image(W, H, (i, x, y) => (Math.hypot(x - 480, y - 270) < 30 ? [1, 0.25, 0.1] : [0.03, 0.03, 0.03]));
  const fr = boxAt({ dfMode: 4 }, 1, red, 516, 266, 520, 274), mi = boxAt({ dfMode: 0 }, 1, red, 516, 266, 520, 274);
  const satOf = c => (Math.max(c.r, c.g, c.b) - Math.min(c.r, c.g, c.b)) / Math.max(c.r, c.g, c.b, 1e-6);
  ok("Frost: its halo off a red light is paler and cooler than Black Mist's", satOf(fr) < satOf(mi) - 0.05 && fr.b / fr.r > mi.b / mi.r, `saturation Frost ${f3(satOf(fr))}, Mist ${f3(satOf(mi))}; blue/red Frost ${f3(fr.b / fr.r)}, Mist ${f3(mi.b / mi.r)}`); }

{ const pt = image(W, H, (i, x, y) => (Math.hypot(x - 480, y - 270) < 2 ? [1, 1, 1] : [0.02, 0.02, 0.02]));
  const a = lift({ dfMode: 5 }, pt, 483, 269, 485, 271), b = lift({ dfMode: 5 }, pt, 486, 269, 488, 271), c = lift({ dfMode: 5 }, pt, 494, 269, 496, 271);
  ok("Soft Focus: a point's halo is a flat disc that ends at its radius", a > 0.03 && a / b < 2.2 && c < 0.25 * a, `at 4 px ${f3(a)}, 7 px ${f3(b)}, 15 px ${f3(c)}`);
  const ed = image(W, H, (i, x) => (x < 480 ? [0.75, 0.75, 0.75] : [0.15, 0.15, 0.15]));
  const l = boxAt({ dfMode: 5 }, 1, ed, 479, 260, 480, 280).y, r = boxAt({ dfMode: 5 }, 1, ed, 480, 260, 481, 280).y;
  const l3 = boxAt({ dfMode: 5 }, 1, ed, 476, 260, 477, 280).y, r3 = boxAt({ dfMode: 5 }, 1, ed, 483, 260, 484, 280).y;
  ok("Soft Focus: an edge keeps a sharp step under its glow", (l - r) > 0.35 * (l3 - r3) && (l - r) > 0.15, `step across the edge ${f3(l - r)}, over 7 px ${f3(l3 - r3)}`); }

{ const pt = image(W, H, (i, x, y) => (Math.hypot(x - 480, y - 270) < 2 ? [1, 1, 1] : [0.02, 0.02, 0.02]));
  const arm = (P, deg) => { let m = 0; for (let d = 6; d < 24; d += 3) { const x = Math.round(480 + d * Math.cos(deg * Math.PI / 180)), y = Math.round(270 + d * Math.sin(deg * Math.PI / 180)); m += lift(P, pt, x, y, x + 1, y + 1); } return m / 6; };
  const a0 = arm({ dfMode: 6 }, 0), a90 = arm({ dfMode: 6 }, 90), a45 = arm({ dfMode: 6 }, 45);
  const b45 = arm({ dfMode: 6, dfAngle: 45 }, 45), b0 = arm({ dfMode: 6, dfAngle: 45 }, 0);
  ok("Net: a point throws a cross along the threads; Angle turns it", a0 > 4 * a45 && a90 > 4 * a45 && b45 > 4 * b0, `Angle 0: along ${f3(a0)} and ${f3(a90)}, diagonal ${f3(a45)}; Angle 45: along ${f3(b45)}, at 0 ${f3(b0)}`);
  const c = arm({ dfMode: 6, dfColour: 100 }, 0), q = (P, d) => { const o = boxAt(P, 1, pt, 480 + d, 270, 481 + d, 271); return o.r / o.b; };
  ok("Net: Colour sends red further along the arm than blue", q({ dfMode: 6, dfColour: 100 }, 24) > 1.1 * q({ dfMode: 6, dfColour: 100 }, 4), `red/blue at 4 px ${f3(q({ dfMode: 6, dfColour: 100 }, 4))}, at 24 px ${f3(q({ dfMode: 6, dfColour: 100 }, 24))} (${f3(c)})`); }

{ const sp = image(W, H, (i, x, y) => (x % 6 === 0 && y % 6 === 0 ? [0.1, 0.1, 0.1] : [0.6, 0.6, 0.6]));
  const before = 0.6 - 0.1, o = boxAt({ dfMode: 7 }, 1, sp, 480, 270, 481, 271).y, n = boxAt({ dfMode: 7 }, 1, sp, 482, 270, 483, 271).y;
  const ed = image(W, H, (i, x) => (x < 480 ? [0.75, 0.75, 0.75] : [0.15, 0.15, 0.15]));
  const l = boxAt({ dfMode: 7 }, 1, ed, 477, 260, 478, 280).y, r = boxAt({ dfMode: 7 }, 1, ed, 482, 260, 483, 280).y;
  ok("Silk: a fine dark speck fills in, a large edge keeps most of its step", (n - o) < 0.75 * before && (l - r) > 0.7 * 0.6, `speck contrast ${f3(n - o)} (in ${f3(before)}), edge over 5 px ${f3(l - r)} (in 0.600)`); }

{ const st = image(W, H, (i, x) => ((x >> 1) & 1 ? [0.7, 0.7, 0.7] : [0.2, 0.2, 0.2]));
  const o = run({ dfMode: 8 }, 1, image(96, 54, (i, x) => ((x >> 1) & 1 ? [0.7, 0.7, 0.7] : [0.2, 0.2, 0.2])));
  let d = 0; for (let y = 22; y < 32; y++) for (let x = 43; x < 53; x++) if (o.g[y * 96 + x] !== st.g[0] && o.g[y * 96 + x] !== st.g[2]) d++;
  const a = boxAt({ dfMode: 8 }, 1, st, 40, 270, 42, 271).y, b = boxAt({ dfMode: 8 }, 1, st, 42, 270, 44, 271).y;
  ok("Center Spot: the centre comes back exactly, the frame's edge is diffused", d === 0 && Math.abs(a - b) < 0.3, `changed in the centre ${d}, stripe contrast at the edge ${f3(Math.abs(a - b))} (in 0.500)`); }

{ const pt = image(W, H, (i, x, y) => (Math.hypot(x - 480, y - 270) < 6 ? [1, 1, 1] : [0.02, 0.02, 0.02]));
  const at = (P, d) => boxAt(P, 1, pt, 480 + d, 268, 482 + d, 272);
  const ring = at({ dfMode: 9 }, 45).y, inner = at({ dfMode: 9 }, 28).y, outer = at({ dfMode: 9 }, 75).y;
  ok("Halo: a ring round a small light, brighter than inside or outside it", ring > 1.15 * inner && ring > 2 * outer && ring > 0.03, `at 28 px ${f3(inner)}, 45 px ${f3(ring)}, 75 px ${f3(outer)}`);
  const o1 = at({ dfMode: 9, dfColour: 100 }, 38), o2 = at({ dfMode: 9, dfColour: 100 }, 54);
  ok("Halo: red on the outside of the ring, blue inside", o2.r / o2.b > 1.1 * (o1.r / o1.b), `red/blue at 38 px ${f3(o1.r / o1.b)}, at 54 px ${f3(o2.r / o2.b)}`); }

{ const a = boxAt({ dfMode: 10 }, 1, lamp, 500, 266, 504, 274), far = lift({ dfMode: 10 }, lamp, 540, 266, 544, 274), mf = lift({ dfMode: 0 }, lamp, 540, 266, 544, 274);
  ok("Atmospheric Glow: the aureole is warm and reaches far (60 px off a lamp of 10)", a.r > 1.1 * a.b && far > 2 * mf && far > 0.005, `r ${f3(a.r)} b ${f3(a.b)}; at 60 px ${f3(far)}, Black Mist ${f3(mf)}`); }

{ const o = boxAt({ dfMode: 11 }, 1, half, 482, 260, 485, 280), m = boxAt({ dfMode: 0 }, 1, half, 482, 260, 485, 280);
  ok("Film Glow: a red fringe hugs a bright edge", o.r - o.b > 0.08 && o.r - o.b > 3 * Math.abs(m.r - m.b), `at 2 to 5 px r ${f3(o.r)} g ${f3(o.g)} b ${f3(o.b)}; Black Mist r - b ${f3(m.r - m.b)}`); }

{ const dl = image(W, H, (i, x) => (x < 480 ? [0.03, 0.03, 0.03] : [0.8, 0.8, 0.8]));
  let tp = 0, bt = 0, nearL = 0, farL = 0;
  for (const f of [100, 200, 300]) {
    tp += lift({ dfMode: 12, dfDepth: 100, dfDensity: 80 }, dl, 380, 10, 470, 60);
    bt += lift({ dfMode: 12, dfDepth: 100, dfDensity: 80 }, dl, 380, 480, 470, 530);
    nearL += lift({ dfMode: 12, dfDensity: 80 }, dl, 440, 200, 470, 340);
    farL += lift({ dfMode: 12, dfDensity: 80 }, dl, 10, 200, 40, 340);
  }
  ok("Smoke and Fog: Depth pools it low; it is lit by the bright half beside it", bt > 1.5 * tp && nearL > 1.5 * farL && nearL > 0.02, `top ${f3(tp / 3)}, bottom ${f3(bt / 3)}; beside the light ${f3(nearL / 3)}, far from it ${f3(farL / 3)}`); }

{ let bad = 0; const sm = image(64, 36, () => [rnd(), rnd(), rnd()]);
  for (let q = 0; q < 30; q++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd(); P.dfMode = q % 13;
    const o = run(P, Math.floor(rnd() * 999), sm); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok("range over 30 slider sets", bad === 0, `bad ${bad}`); }
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
