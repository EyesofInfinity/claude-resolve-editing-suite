import { compile, runTransition } from "../../tests/cpu/dctl.mjs";

const GX = "build/Develop Glitch Dissolve.dctl", FD = "build/Develop Film Dissolve.dctl";
const W = 320, H = 180, n = W * H;
let s = 31;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function img(fn) {
  const o = { w: W, h: H, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const c = fn(x, y), i = y * W + x; o.r[i] = c[0]; o.g[i] = c[1]; o.b[i] = c[2]; }
  return o;
}
const cl = v => Math.min(Math.max(v, 0), 1);
const A = img((x, y) => { const v = 0.35 + 0.25 * Math.sin(x / 7) * Math.cos(y / 11) + (y < 40 ? 0.45 : 0) + (rnd() < 0.004 ? 0.6 : 0); return [cl(v), cl(0.9 * v), cl(0.7 * v + 0.05 * rnd())]; });
const B = img((x, y) => { const r = Math.hypot(x - W / 2, y - H / 3), v = 0.3 + 0.3 * Math.sin(r / 6) + (r < 25 ? 0.5 : 0); return [cl(0.5 * v), cl(0.8 * v), cl(v)]; });
const RED = img(() => [0.8, 0.1, 0.1]), BLUE = img(() => [0.1, 0.2, 0.9]), K = img(() => [0, 0, 0]);
const GREY = img((x, y) => { const v = 0.5 + 0.4 * Math.sin(x / 5 + y / 9); return [v, v, v]; });
const diff = (o, q) => { let d = 0, m = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < n; i++) { const e = Math.abs(o[k][i] - q[k][i]); if (e > 1e-9) d++; m += e; } return { n: d, mean: +(m / (3 * n)).toFixed(4) }; };
const L = (o, i) => 0.2126 * o.r[i] + 0.7152 * o.g[i] + 0.0722 * o.b[i];
let fails = 0, count = 0;
const ok = (name, pass, info) => { count++; console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const same = (o, q, i) => Math.abs(o.r[i] - q.r[i]) < 1e-9 && Math.abs(o.g[i] - q.g[i]) < 1e-9 && Math.abs(o.b[i] - q.b[i]) < 1e-9;

const GN = ["Pixel Sort", "Diffuse", "Diffuse Wipe", "Pixelate Wipe", "RGB Displacement"];
const gx = (st, p, a = A, b = B, P = {}) => runTransition(GX, { gxStyle: st, ...P }, { progress: p, frame: 1 }, a, b);
for (let st = 0; st < 5; st++) {
  const N = GN[st];
  ok(`${N} starts exactly on the outgoing shot`, diff(gx(st, 0), A).n === 0, JSON.stringify(diff(gx(st, 0), A)));
  ok(`${N} ends exactly on the incoming shot`, diff(gx(st, 1), B).n === 0, JSON.stringify(diff(gx(st, 1), B)));
  const e0 = diff(gx(st, 0.02), A).mean, e1 = diff(gx(st, 0.98), B).mean;
  ok(`${N} eases out and in (within 0.005 at progress 0.02 and 0.98)`, e0 < 0.005 && e1 < 0.005, `${e0} ${e1}`);
  const o = gx(st, 0.48), q = gx(st, 0.48, A, B, { gxAmount: 0 });
  const need = st === 2 || st === 3 ? 0.005 : 0.01;
  ok(`${N} glitches the hand-over`, diff(o, q).mean > need, `mean off the clean shape ${diff(o, q).mean}`);
}
for (const st of [0, 4]) {
  const o = gx(st, 0.5, A, B, { gxAmount: 0 });
  let m = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < n; i++) m = Math.max(m, Math.abs(o[k][i] - 0.5 * (A[k][i] + B[k][i])));
  ok(`${GN[st]} at Glitch 0 is a plain dissolve`, m < 1e-6, `max ${m.toExponential(2)}`);
}
for (const st of [1, 2, 3]) {
  const o = gx(st, 0.5, A, B, { gxAmount: 0 });
  let bad = 0, nb = 0; for (let i = 0; i < n; i++) { if (same(o, B, i)) nb++; else if (!same(o, A, i)) bad++; }
  ok(`${GN[st]} at Glitch 0 takes each pixel whole from one shot`, bad === 0 && nb > 0.2 * n && nb < 0.8 * n, `neither ${bad}, from the incoming ${(nb / n).toFixed(2)}`);
}
{
  const N = img((x, y) => { const v = 0.55 + 0.45 * rnd(); return [v, v, v]; });
  const P = { gxGrit: 0, gxDither: 0, gxThresh: 50 };
  const climb = o => { let up = 0, dn = 0; for (let y = 0; y < H; y++) for (let x = 0; x < W - 1; x++) { const a = L(o, y * W + x), b = L(o, y * W + x + 1); if (b > a + 1e-6) up++; else if (b < a - 1e-6) dn++; } return up / Math.max(up + dn, 1); };
  const r0 = climb(gx(0, 0.4, N, N, { ...P, gxAngle: 0 })), r1 = climb(gx(0, 0.4, N, N, { ...P, gxAngle: 180 })), r2 = climb(N);
  ok("Pixel Sort climbs toward Angle", r0 > 0.8 && r1 < 0.2 && r2 > 0.4 && r2 < 0.6, `rising pairs at 0 deg ${r0.toFixed(2)}, 180 deg ${r1.toFixed(2)}, unsorted ${r2.toFixed(2)}`);
  const m2 = diff(gx(0, 0.2, N, N, P), N).n, m4 = diff(gx(0, 0.4, N, N, P), N).n;
  ok("Pixel Sort grows toward the cut", m4 > 1.5 * m2, `moved at 0.2 ${m2}, at 0.4 ${m4}`);
}
{
  const P = { gxGrit: 0, gxDither: 0 };
  const share = p => { const o = gx(1, p, RED, BLUE, P); let c = 0; for (let i = 0; i < n; i++) if (o.b[i] > 0.5) c++; return c / n; };
  const s3 = share(0.3), s5 = share(0.5), s7 = share(0.7);
  ok("Diffuse trades grains, about half at the middle", s3 < s5 && s5 < s7 && Math.abs(s5 - 0.5) < 0.1, `incoming share ${s3.toFixed(2)} ${s5.toFixed(2)} ${s7.toFixed(2)}`);
  const o = gx(1, 0.5, A, A, P); let moved = 0; for (let i = 0; i < n; i++) if (!same(o, A, i)) moved++;
  ok("Diffuse throws the grains from their places", moved > 0.3 * n, `moved ${(moved / n).toFixed(2)}`);
}
{
  const o = gx(2, 0.5, RED, BLUE, { gxGrit: 0, gxDither: 0, gxSoft: 20 });
  const col = x => { let c = 0; for (let y = 0; y < H; y++) if (o.b[y * W + x] > 0.5) c++; return c / H; };
  const l = col(10), m = col(W / 2), r = col(W - 10);
  ok("Diffuse Wipe crosses at Angle", l === 1 && r === 0 && m > 0.2 && m < 0.8, `incoming share left ${l}, middle ${m.toFixed(2)}, right ${r}`);
}
{
  const o = gx(3, 0.5, A, B, { gxGrit: 0, gxDither: 0 });
  let eq = 0, tot = 0;
  const nb = (q, i) => Math.abs(q.r[i] - q.r[i + 1]) < 1e-9 && Math.abs(q.g[i] - q.g[i + 1]) < 1e-9 && Math.abs(q.b[i] - q.b[i + 1]) < 1e-9;
  for (let y = 0; y < H; y++) for (let x = W / 2 - 20; x < W / 2 + 20; x++) { tot++; if (nb(o, y * W + x)) eq++; }
  let eqA = 0; for (let y = 0; y < H; y++) for (let x = W / 2 - 20; x < W / 2 + 20; x++) if (Math.abs(A.g[y * W + x] - A.g[y * W + x + 1]) < 1e-9) eqA++;
  let l = 0, r = 0; for (let y = 0; y < H; y++) { for (let x = 0; x < 6; x++) if (same(o, B, y * W + x)) l++; for (let x = W - 6; x < W; x++) if (same(o, A, y * W + x)) r++; }
  ok("Pixelate Wipe breaks the front into blocks", eq / tot > 0.75 && eqA / tot < 0.2, `equal neighbours on the front ${(eq / tot).toFixed(2)}, in the shot ${(eqA / tot).toFixed(2)}`);
  ok("Pixelate Wipe leaves the incoming shot behind and the outgoing ahead", l === 6 * H && r === 6 * H, `left on B ${l}, right on A ${r} of ${6 * H}`);
}
{
  const o = gx(4, 0.3, GREY, GREY, { gxGrit: 0, gxDither: 0 });
  let fr = 0; for (let i = 0; i < n; i++) if (Math.abs(o.r[i] - o.g[i]) > 0.02 || Math.abs(o.b[i] - o.g[i]) > 0.02) fr++;
  ok("RGB Displacement pulls the channels apart", fr > 0.2 * n, `fringed ${(fr / n).toFixed(2)}`);
  const q = gx(4, 0.5, A, B, { gxGrit: 0, gxDither: 100 });
  let off = 0; for (const k of ["r", "g", "b"]) for (const v of q[k]) if (Math.min(Math.abs(v), Math.abs(v - 0.5), Math.abs(v - 1)) > 1e-6) off++;
  ok("Dither 100 crushes the peak to 3 levels a channel", off === 0, `values off the levels ${off}`);
}

const FN = ["Film Dissolve", "Film Roll", "TV Roll"];
const fd = (st, p, a = A, b = B, P = {}) => runTransition(FD, { fdStyle: st, ...P }, { progress: p, frame: 1 }, a, b);
for (let st = 0; st < 3; st++) {
  const N = FN[st];
  ok(`${N} starts exactly on the outgoing shot`, diff(fd(st, 0), A).n === 0, JSON.stringify(diff(fd(st, 0), A)));
  ok(`${N} ends exactly on the incoming shot`, diff(fd(st, 1), B).n === 0, JSON.stringify(diff(fd(st, 1), B)));
  const e0 = diff(fd(st, 0.02), A).mean, e1 = diff(fd(st, 0.98), B).mean;
  ok(`${N} eases out and in (within 0.005 at progress 0.02 and 0.98)`, e0 < 0.005 && e1 < 0.005, `${e0} ${e1}`);
}
{
  const HA = img((x) => (x < W / 2 ? [1, 1, 1] : [0, 0, 0])), HB = img(() => [0.1, 0.1, 0.1]);
  const HB2 = img((x) => (x < W / 2 ? [0.1, 0.1, 0.1] : [0, 0, 0]));
  const P = { fdGrain: 0 };
  const hi = fd(0, 0.5, HA, HB, P).g[90 * W + 40], lo0 = fd(0, 0.5, HA, HB, { ...P, fdHold: 0 }).g[90 * W + 40];
  ok("Film Dissolve holds the highlights", hi > 0.85 && hi > lo0 + 0.03, `highlight at the middle ${hi.toFixed(3)} (Hold 0 ${lo0.toFixed(3)}, a video dissolve 0.550)`);
  const bk = fd(0, 0.5, HA, HB2, P).g[90 * W + 280];
  ok("Film Dissolve keeps black over black", bk === 0, `black ${bk}`);
  const p = 0.4, t = p ** 3 / (p ** 3 + (1 - p) ** 3), o = fd(0, p, A, B, { ...P, fdHold: 0 });
  let m = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < n; i++) m = Math.max(m, Math.abs(o[k][i] - cl(((1 - t) * A[k][i] ** 2.4 + t * B[k][i] ** 2.4) ** (1 / 2.4))));
  ok("Film Dissolve at Hold 0 is a dissolve in linear light", m < 1e-5, `max ${m.toExponential(2)}`);
}
{
  const P = { fdBlur: 0, fdWeave: 0, fdFlicker: 0, fdGrain: 0 };
  const barRow = o => { let best = -1, bv = 9; for (let y = 0; y < H; y++) { let m = 0; for (let x = 0; x < W; x++) m += o.g[y * W + x]; if (m / W < bv) { bv = m / W; best = y; } } return [best, bv]; };
  const o4 = fd(1, 0.45, RED, BLUE, P), o6 = fd(1, 0.55, RED, BLUE, P);
  const [y4, v4] = barRow(o4), [y6] = barRow(o6);
  ok("Film Roll shows the black frame line", v4 < 0.01, `darkest row ${y4} at ${v4.toFixed(4)}`);
  ok("Film Roll rolls the line up", y6 < y4 - 10, `line at row ${y4}, then ${y6}`);
  const top = o4.r[2 * W + 160], bot = o4.b[(H - 3) * W + 160];
  ok("Film Roll has the outgoing frame above the line and the incoming below", y4 > 3 && y4 < H - 3 && top > 0.7 && bot > 0.8, `top red ${top.toFixed(2)}, bottom blue ${bot.toFixed(2)}`);
  const od = fd(1, 0.45, RED, BLUE, { ...P, fdDir: 1 }), [yd] = barRow(od), od6 = fd(1, 0.55, RED, BLUE, { ...P, fdDir: 1 }), [yd6] = barRow(od6);
  ok("Film Roll Direction 1 rolls down", yd6 > yd + 10, `line at row ${yd}, then ${yd6}`);
  const soft = o => { let c = 0; for (let y = 0; y < H; y++) { const v = o.r[y * W + 160] + o.b[y * W + 160]; if (v > 0.05 && v < 0.75) c++; } return c; };
  const sb = soft(fd(1, 0.5, RED, BLUE, { ...P, fdBlur: 100 })), s0 = soft(fd(1, 0.5, RED, BLUE, P));
  ok("Film Roll streaks with the strip's speed", sb > s0 + 6, `rows in the line's edges ${s0} sharp, ${sb} streaked`);
}
{
  const WH = img(() => [0.8, 0.8, 0.8]);
  const P = { fdTear: 0, fdSnow: 0 };
  const o = fd(2, 0.35, WH, WH, P);
  let dark = 0; for (let y = 0; y < H; y++) { let m = 0; for (let x = 0; x < W; x++) m += o.g[y * W + x]; if (m / W < 0.02) dark++; }
  ok("TV Roll shows the blanking bar", dark >= 4, `black rows ${dark}`);
  const t = fd(2, 0.42, WH, WH, { fdTear: 100, fdSnow: 0 });
  const firstDark = y => { for (let x = 0; x < W; x++) if (t.g[y * W + x] < 0.05) return x; return -1; };
  const xs = [30, 60, 90, 120, 150].map(firstDark).filter(v => v >= 0);
  ok("TV Roll slips the lines into diagonal bands", new Set(xs).size >= 3, `the horizontal blanking starts at ${xs.join(", ")}`);
  const sn = fd(2, 0.5, WH, WH, { fdTear: 0, fdSnow: 100 });
  let m = 0, v = 0; for (let i = 0; i < n; i++) m += sn.g[i]; m /= n; for (let i = 0; i < n; i++) v += (sn.g[i] - m) ** 2;
  ok("TV Roll brings up snow at the change", Math.sqrt(v / n) > 0.08, `spread ${Math.sqrt(v / n).toFixed(3)}`);
  const c = fd(2, 0.3, RED, RED, P); let sat = 0; for (let i = 0; i < n; i++) sat += c.r[i] - c.g[i];
  ok("TV Roll loses colour as sync goes", sat / n < 0.6, `red over green ${(sat / n).toFixed(3)} (0.7 in the shot)`);
}
for (const F of [GX, FD]) {
  const { sliders } = compile(F, {}, { progress: 0.5 });
  let bad = 0;
  for (let k = 0; k < 30; k++) {
    const P = {};
    for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd();
    const o = runTransition(F, P, { progress: rnd(), frame: 1 }, A, B);
    for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; }
  }
  ok(`${F.split("/")[1]} range over 30 slider sets`, bad === 0, `bad ${bad}`);
}
console.log(fails ? `${fails} of ${count} FAILED` : `all ${count} pass`);
process.exit(fails ? 1 : 0);
