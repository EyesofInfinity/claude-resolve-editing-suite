import { compile } from "../../tests/cpu/dctl.mjs";

const GL = "build/Develop Glare.dctl", GP = "build/Develop Glow Plus.dctl";
let s = 7;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function img(W, H, fn) {
  const n = W * H, o = { w: W, h: H, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const c = fn(x, y), i = y * W + x; o.r[i] = c[0]; o.g[i] = c[1]; o.b[i] = c[2]; }
  return o;
}
function run(file, P, A, frame = 236) {
  const T = compile(file, P, { frame }).transform, W = A.w, H = A.h, n = W * H;
  const o = { w: W, h: H, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  const R = { d: A.r, w: W }, G = { d: A.g, w: W }, B = { d: A.b, w: W };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const c = T(W, H, x, y, R, G, B), i = y * W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z; }
  return o;
}
const at = (o, x, y) => [o.r[y * o.w + x], o.g[y * o.w + x], o.b[y * o.w + x]];
const L = c => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
const diffN = (o, a) => { let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < a.r.length; i++) if (Math.abs(o[k][i] - a[k][i]) > 1e-9) d++; return d; };
const meanD = (o, a) => { let m = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < a.r.length; i++) m += Math.abs(o[k][i] - a[k][i]); return m / (3 * a.r.length); };
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };

const W = 320, H = 180;
const TX = img(W, H, (x, y) => {
  let v = 0.08 + 0.06 * Math.sin(x / 5) * Math.cos(y / 7) + 0.03 * rnd();
  if (y < 18) v = 0.92;
  if (Math.hypot(x - 200, y - 100) < 3.5) v = 1;
  if ((x === 60 && y === 120) || (x === 260 && y === 60)) v = 1;
  return [Math.min(v, 1), Math.min(0.95 * v, 1), Math.min(0.9 * v + 0.02, 1)];
});
const K = img(W, H, () => [0.05, 0.05, 0.06]);
const disc = (cx, cy, r, v = 1, bg = 0.05) => img(W, H, (x, y) => (Math.hypot(x - cx, y - cy) < r ? [v, v, v] : [bg, bg, bg * 1.1]));

for (let m = 0; m < 4; m++) ok(`Glare mode ${m}: Glare 0 is the input exactly`, diffN(run(GL, { glAmount: 0, glMode: m }, TX), TX) === 0, "");
for (let m = 0; m < 8; m++) ok(`Glow Plus mode ${m}: Glow 0 is the input exactly`, diffN(run(GP, { gpAmount: 0, gpMode: m }, TX), TX) === 0, "");
for (let m = 0; m < 3; m++) ok(`Glare mode ${m}: nothing over Threshold, nothing added`, diffN(run(GL, { glMode: m }, K), K) === 0, "");
for (const m of [0, 1, 2, 3, 4]) ok(`Glow Plus mode ${m}: nothing over Threshold, nothing added`, diffN(run(GP, { gpMode: m }, K), K) === 0, "");

const W2 = 640, H2 = 360;
const disc2 = (cx, cy, r, v = 1, bg = 0.05) => img(W2, H2, (x, y) => (Math.hypot(x - cx, y - cy) < r ? [v, v, v] : [bg, bg, bg * 1.1]));
{
  const D = disc2(320, 180, 8);
  const o = run(GL, { glMode: 0, glColour: 0 }, D);
  let lit = 0;
  for (let a = 0; a < 128; a++) { const x = Math.round(320 + 30 * Math.cos(a / 128 * 2 * Math.PI)), y = Math.round(180 + 30 * Math.sin(a / 128 * 2 * Math.PI)); lit = Math.max(lit, L(at(o, x, y)) - L(at(D, x, y))); }
  ok("Glare: a lamp throws needles 30 px out", lit > 0.03, `brightest lift ${lit.toFixed(3)}`);
  const S = img(W, H, (x, y) => (y < 90 ? [0.95, 0.95, 0.97] : [0.05, 0.05, 0.06]));
  const os = run(GL, { glMode: 0 }, S);
  ok("Glare: a bright sky throws nothing below its edge", meanD(os, S) < 0.002, `mean change ${meanD(os, S).toFixed(5)}`);
}
{
  const D = disc2(320, 180, 8);
  const o = run(GL, { glMode: 1, glDirs: 1, glAngle: 0 }, D);
  const along = L(at(o, 350, 180)) - L(at(D, 350, 180)), across = L(at(o, 320, 210)) - L(at(D, 320, 210));
  ok("Streaks: the line runs along Angle", along > 0.03 && along > 5 * Math.max(across, 1e-4), `along ${along.toFixed(3)}, across ${across.toFixed(4)}`);
  const o2 = run(GL, { glMode: 1, glDirs: 1, glAngle: 0, glSide: 100 }, D);
  const l = L(at(o2, 290, 180)) - L(at(D, 290, 180)), r = L(at(o2, 350, 180)) - L(at(D, 350, 180));
  ok("Streaks: One Side 100 smears one way", Math.max(l, r) > 0.02 && Math.min(l, r) < 0.1 * Math.max(l, r), `left ${l.toFixed(3)}, right ${r.toFixed(3)}`);
  const o4 = run(GL, { glMode: 1, glDirs: 2, glAngle: 0 }, D);
  ok("Streaks: Directions 2 adds a line across", L(at(o4, 320, 210)) - L(at(D, 320, 210)) > 0.02, `across ${(L(at(o4, 320, 210)) - L(at(D, 320, 210))).toFixed(3)}`);
}
{
  const D = disc2(200, 180, 3);
  const o = run(GL, { glMode: 2, glDirs: 1, glAngle: 0, glSize: 50, glColour: 100 }, D);
  const S = (20 + 1.6 * 50) / 3;
  const near = at(o, Math.round(200 + 0.62 * S), 180), far = at(o, Math.round(200 + 0.95 * S), 180);
  ok("Chroma Bands: blue near the light, red far", near[2] > near[0] && far[0] > far[2], `near ${near.map(v => v.toFixed(2))}, far ${far.map(v => v.toFixed(2))}`);
}
{
  const big = (cx, cy) => img(W, H, (x, y) => { const d = Math.hypot(x - cx, y - cy); const v = d < 5 ? 1 : 0.25 + 0.15 * Math.exp(-d / 30); return [v, v, v * 1.05]; });
  const R = (0.12 + 0.0068 * 30) * H;
  const ring = (o, A, cx, cy, r) => { let m = 0; for (let a = 0; a < 32; a++) { const x = Math.round(cx + r * Math.cos(a / 32 * 2 * Math.PI)), y = Math.round(cy + r * Math.sin(a / 32 * 2 * Math.PI)); if (x >= 0 && y >= 0 && x < W && y < H) m += L(at(o, x, y)) - L(at(A, x, y)); } return m / 32; };
  const A1 = big(120, 70), o1 = run(GL, { glMode: 3, glSize: 30, glArcs: 0 }, A1);
  const on = ring(o1, A1, 120, 70, R * 1.01), inside = ring(o1, A1, 120, 70, R * 0.7);
  ok("Ice Halos: a ring at the halo's radius, nothing inside it", on > 0.01 && inside < 0.1 * on, `ring ${on.toFixed(4)}, inside ${inside.toFixed(5)}`);
  const A2 = big(200, 80), o2 = run(GL, { glMode: 3, glSize: 30, glArcs: 0 }, A2);
  ok("Ice Halos: Find Sun follows the light", ring(o2, A2, 200, 80, R * 1.01) > 0.01 && ring(o2, A2, 120, 70, R * 1.01) < 0.5 * ring(o2, A2, 200, 80, R * 1.01), `ring at the new place ${ring(o2, A2, 200, 80, R * 1.01).toFixed(4)}`);
  const o3 = run(GL, { glMode: 3, glSize: 30, glArcs: 100 }, A1);
  const dog = L(at(o3, Math.round(120 + 1.06 * R), 70)) - L(at(o1, Math.round(120 + 1.06 * R), 70));
  ok("Ice Halos: Arcs adds sun dogs at the sun's height", dog > 0.01, `lift ${dog.toFixed(4)}`);
}
{
  const D = disc(160, 90, 5);
  const o = run(GP, { gpMode: 0 }, D);
  ok("Glow: a light glows round it", L(at(o, 172, 90)) - L(at(D, 172, 90)) > 0.03, `lift 12 px out ${(L(at(o, 172, 90)) - L(at(D, 172, 90))).toFixed(3)}`);
  const Rd = img(W, H, (x, y) => (Math.hypot(x - 160, y - 90) < 8 ? [1, 0.7, 0.6] : [0.05, 0.05, 0.05]));
  const kr = run(GP, { gpMode: 0, gpKeyHue: 10, gpKeyW: 30, gpThresh: 50 }, Rd), kb = run(GP, { gpMode: 0, gpKeyHue: 220, gpKeyW: 30, gpThresh: 50 }, Rd);
  const a = L(at(kr, 175, 90)) - L(at(Rd, 175, 90)), b = L(at(kb, 175, 90)) - L(at(Rd, 175, 90));
  ok("Glow: Key Hue glows only the chosen colour", a > 0.02 && b < 0.1 * a, `red key ${a.toFixed(3)}, blue key ${b.toFixed(4)}`);
  const sp = run(GP, { gpMode: 0, gpSpread: 100 }, D), c = at(sp, 180, 90);
  ok("Glow: Spread lets blue reach further than red", c[2] > c[0], `at 20 px ${c.map(v => v.toFixed(3))}`);
}
{
  const ln = img(W2, H2, (x, y) => (x >= 160 && x < 163 && y > 80 && y < 280 ? [1, 1, 1] : [0.05, 0.05, 0.05]));
  const sq = img(W2, H2, (x, y) => (x >= 360 && x < 480 && y > 80 && y < 280 ? [1, 1, 1] : [0.05, 0.05, 0.05]));
  const dl = L(at(run(GP, { gpMode: 1 }, ln), 169, 180)) - 0.05, ds = L(at(run(GP, { gpMode: 1 }, sq), 486, 180)) - 0.05;
  const gl = L(at(run(GP, { gpMode: 0, gpBroad: 100 }, ln), 169, 180)) - 0.05, gs = L(at(run(GP, { gpMode: 0, gpBroad: 100 }, sq), 486, 180)) - 0.05;
  ok("Distance: a line glows about as far as a big shape", dl > 0.02 && dl / ds > 0.6 && dl / ds < 1.67 && gl / gs < dl / ds, `distance line ${dl.toFixed(3)} square ${ds.toFixed(3)}; glow line ${gl.toFixed(3)} square ${gs.toFixed(3)}`);
}
{
  const D = disc2(320, 180, 50);
  const o = run(GP, { gpMode: 2 }, D), v = [];
  for (let a = 0; a < 240; a++) v.push(L(at(o, Math.round(320 + 56 * Math.cos(a / 240 * 2 * Math.PI)), Math.round(180 + 56 * Math.sin(a / 240 * 2 * Math.PI)))) - 0.05);
  const mu = v.reduce((p, q) => p + q, 0) / v.length, sd = Math.sqrt(v.reduce((p, q) => p + (q - mu) * (q - mu), 0) / v.length);
  ok("Aura: streamers break the glow along the outline", mu > 0.01 && sd / mu > 0.25, `mean ${mu.toFixed(3)}, spread ${(sd / mu).toFixed(2)}`);
  const o2 = run(GP, { gpMode: 2 }, D, 248);
  ok("Aura: it flickers frame to frame, and repeats exactly", diffN(o2, o) > 100 && diffN(run(GP, { gpMode: 2 }, D), o) === 0, `changed ${diffN(o2, o)}`);
}
{
  const D = disc2(320, 180, 12);
  const o = run(GP, { gpMode: 3, gpHue: 50, gpHue2: 0 }, D);
  const n = at(o, 334, 180), f = at(o, 344, 180);
  const rn = (n[0] - 0.05) / Math.max(n[1] - 0.05, 1e-4), rf = (f[0] - 0.05) / Math.max(f[1] - 0.05, 1e-4);
  ok("Colorize: the rim takes Edge Hue, the core Tint Hue toward white", rf > rn * 1.2, `red over green near ${rn.toFixed(2)}, far ${rf.toFixed(2)}`);
}
{
  const sq = img(W, H, (x, y) => (x >= 100 && x < 220 && y > 30 && y < 150 ? [0.95, 0.95, 0.95] : [0.05, 0.05, 0.05]));
  const o0 = run(GP, { gpMode: 4, gpBalance: 0 }, sq), o1 = run(GP, { gpMode: 4, gpBalance: 100 }, sq);
  const out0 = L(at(o0, 96, 90)) - L(at(sq, 96, 90)), in0 = L(at(o0, 104, 90)) - L(at(sq, 104, 90));
  const out1 = L(at(o1, 96, 90)) - L(at(sq, 96, 90)), in1 = L(at(o1, 104, 90)) - L(at(sq, 104, 90));
  const mid = Math.abs(L(at(o0, 160, 90)) - L(at(sq, 160, 90))) + Math.abs(L(at(o0, 40, 90)) - L(at(sq, 40, 90)));
  ok("Edges: outside at Balance 0, inside at 100, nothing far from the outline", out0 > 0.02 && in0 < 0.2 * out0 && in1 > 0.005 && out1 < 0.2 * in1 && mid < 1e-3,
     `B0 out ${out0.toFixed(3)} in ${in0.toFixed(4)}; B100 out ${out1.toFixed(4)} in ${in1.toFixed(3)}; far ${mid.toExponential(1)}`);
}
{
  const R = img(W, H, x => { const v = x / (W - 1); return [v, v, v]; });
  const o0 = run(GP, { gpMode: 5, gpBalance: 0, gpTint: 100, gpHue: 210 }, R), o1 = run(GP, { gpMode: 5, gpBalance: 100 }, R);
  const k0 = at(o0, 0, 50), w0 = at(o0, W - 1, 50), k1 = at(o1, 0, 50), w1 = at(o1, W - 1, 50);
  ok("Flashing: shadows lifted and tinted, white kept (Balance 0)", L(k0) > 0.05 && k0[2] > k0[0] && L(w0) > 0.98, `black ${k0.map(v => v.toFixed(3))}, white ${L(w0).toFixed(3)}`);
  ok("Flashing: whites dulled, black kept (Balance 100)", L(w1) < 0.97 && L(k1) < 0.01, `black ${L(k1).toFixed(3)}, white ${L(w1).toFixed(3)}`);
  let mono = true; for (let x = 1; x < W; x++) if (L(at(o0, x, 50)) < L(at(o0, x - 1, 50)) - 1e-9 || L(at(o1, x, 50)) < L(at(o1, x - 1, 50)) - 1e-9) mono = false;
  ok("Flashing: tones keep their order", mono, "");
}
{
  const N = img(W, H, (x, y) => { const v = ((x * 7 + y * 13) % 5) / 5 * 0.6 + 0.2; return [v, v, v]; });
  const o = run(GP, { gpMode: 6, gpAngle: 0, gpPos: 50, gpBalance: 0, gpRate: 0, gpSize: 60 }, N);
  const dev = y0 => { let d = 0; for (let x = 40; x < 280; x++) d += Math.abs(o.g[y0 * W + x] - N.g[y0 * W + x]); return d / 240; };
  ok("Free Lens: sharp in the band, blurred away from it", dev(90) < 0.01 && dev(10) > 0.05, `change in the band ${dev(90).toFixed(4)}, at the top ${dev(10).toFixed(3)}`);
  const ol = run(GP, { gpMode: 6, gpAngle: 0, gpPos: 50, gpBalance: 100, gpRate: 0 }, N), on = run(GP, { gpMode: 6, gpAngle: 0, gpPos: 50, gpBalance: 0, gpRate: 0 }, N);
  const top = L(at(ol, 160, 2)) - L(at(on, 160, 2)), bot = L(at(ol, 160, H - 3)) - L(at(on, 160, H - 3));
  ok("Free Lens: light leaks in at one side", Math.max(top, bot) > 0.03 && Math.min(top, bot) < 0.3 * Math.max(top, bot), `top ${top.toFixed(3)}, bottom ${bot.toFixed(3)}`);
}
{
  const B = img(W, H, () => [0.04, 0.04, 0.05]);
  let pops = 0, same = 0, outside = 0;
  for (let f = 0; f < 40; f++) {
    const o = run(GP, { gpMode: 7, gpRate: 100, gpPos: 30, gpSpread: 0 }, B, 1000 + f);
    const d = diffN(o, B);
    if (d > 0) pops++; else same++;
    for (let y = 120; y < H; y++) for (let x = 0; x < W; x++) if (Math.abs(o.g[y * W + x] - B.g[y * W + x]) > 1e-9) outside++;
  }
  ok("Flashbulbs: frames pop and frames rest", pops > 3 && same > 3, `popped ${pops}, at rest ${same} of 40`);
  ok("Flashbulbs: none outside the band", outside === 0, `pixels lit below the band ${outside}`);
}
for (const F of [GL, GP]) {
  const { sliders } = compile(F, {}, { frame: 1 });
  const small = img(120, 68, (x, y) => { const v = rnd(); return [v, v * 0.9, Math.min(1, v * 0.8 + 0.2 * rnd())]; });
  let bad = 0;
  for (let k = 0; k < 30; k++) {
    const P = {};
    for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd();
    const o = run(F, P, small, Math.floor(rnd() * 2000));
    for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; }
  }
  ok(`${F.split("/")[1]}: range over 30 slider sets`, bad === 0, `bad ${bad}`);
}
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
