import { compile, runTransition, run } from "../../tests/cpu/dctl.mjs";

const F = "build/Develop Blur Dissolve.dctl", KP = "build/Develop Kaleido Polar.dctl", W = 320, H = 180, n = W * H;
let s = 31;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function img(fn) {
  const o = { w: W, h: H, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const c = fn(x, y), i = y * W + x; o.r[i] = c[0]; o.g[i] = c[1]; o.b[i] = c[2]; }
  return o;
}
const cx = W / 2 - 0.5, cy = H / 2 - 0.5, cl = v => Math.min(Math.max(v, 0), 1);
const A = img((x, y) => { const v = 0.35 + 0.25 * Math.sin(x / 7) * Math.cos(y / 11) + (y < 40 ? 0.4 : 0) + (rnd() < 0.004 ? 0.5 : 0); return [cl(v), cl(0.9 * v), cl(0.7 * v + 0.05 * rnd())]; });
const B = img((x, y) => { const r = Math.hypot(x - W / 2, y - H / 3), v = 0.3 + 0.3 * Math.sin(r / 6) + (r < 25 ? 0.5 : 0); return [cl(0.5 * v), cl(0.8 * v), cl(v)]; });
const K = img(() => [0, 0, 0]), Wt = img(() => [1, 1, 1]);
const RINGS = img((x, y) => { const v = 0.5 + 0.4 * Math.sin(Math.hypot(x - cx, y - cy) / 2.2); return [v, v, v]; });
const SPOKES = img((x, y) => { const v = 0.5 + 0.4 * Math.sin(24 * Math.atan2(y - cy, x - cx)); return [v, v, v]; });
const VSTR = img(x => { const v = 0.5 + 0.4 * Math.sin(x / 2.5); return [v, v, v]; });
const HSTR = img((x, y) => { const v = 0.5 + 0.4 * Math.sin(y / 2.5); return [v, v, v]; });
const NOISE = img(() => { const v = 0.2 + 0.6 * rnd(); return [v, v, v]; });
const diff = (o, q) => { let d = 0, m = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < n; i++) { const e = Math.abs(o[k][i] - q[k][i]); if (e > 1e-9) d++; m += e; } return { n: d, mean: +(m / (3 * n)).toFixed(4) }; };
const mean = (o, k = "g") => { let m = 0; for (let i = 0; i < n; i++) m += o[k][i]; return m / n; };
const contrast = (o, r0 = 20, r1 = 80, px = cx, py = cy) => { let m = 0, c = 0; for (let y = 1; y < H - 1; y++) for (let x = 1; x < W - 1; x++) {
  const d = Math.hypot(x - px, y - py); if (d < r0 || d > r1) continue; const i = y * W + x;
  m += Math.abs(o.g[i] - o.g[i + 1]) + Math.abs(o.g[i] - o.g[i + W]); c++; } return m / c; };
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const NAMES = ["Bubble", "Shake", "Sphere", "Crash Zoom", "Cross Zoom", "Directional", "Spin", "Vector", "Curl", "Kaleida"];
const at = (st, p, a = A, b = B, P = {}) => runTransition(F, { bdStyle: st, ...P }, { progress: p, frame: 1 }, a, b);

for (let st = 0; st < 10; st++) {
  const N = NAMES[st];
  ok(`${N} starts exactly on the outgoing shot`, diff(at(st, 0), A).n === 0, JSON.stringify(diff(at(st, 0), A)));
  ok(`${N} ends exactly on the incoming shot`, diff(at(st, 1), B).n === 0, JSON.stringify(diff(at(st, 1), B)));
  const e0 = diff(at(st, 0.02), A).mean, e1 = diff(at(st, 0.98), B).mean;
  ok(`${N} eases out and in (within 0.005 at progress 0.02 and 0.98)`, e0 < 0.005 && e1 < 0.005, `${e0} ${e1}`);
  if (st !== 2) {
    const o = at(st, 0.5, Wt, Wt, { bdGlow: 0 });
    let lo = 1; for (let i = 0; i < n; i++) lo = Math.min(lo, o.g[i]);
    ok(`${N} keeps a white frame white`, lo > 0.999, `lowest ${lo.toFixed(4)}`);
  }
}
{
  const share = o => { let c = 0; for (let i = 0; i < n; i++) if (o.g[i] > 0.5) c++; return c / n; };
  const s1 = share(at(0, 0.25, K, Wt)), s0 = share(at(0, 0.02, K, Wt));
  ok("Bubble carries the incoming shot in bubbles first", s1 > 0.05 && s1 < 0.6 && s0 === 0, `share lit at 0.25 ${s1.toFixed(3)}, at 0.02 ${s0}`);
  const m1 = at(0, 0.40, K, Wt), m2 = at(0, 0.42, K, Wt);
  let bs = 0, bo = -1;
  for (let sh = -8; sh <= 4; sh++) { let o = 0; for (let y = 10; y < H - 10; y++) for (let x = 0; x < W; x++) if (m1.g[y * W + x] > 0.5 && m2.g[(y + sh) * W + x] > 0.5) o++; if (o > bo) { bo = o; bs = sh; } }
  ok("Bubble's bubbles rise", bs < 0, `best match shifted ${bs} px`);
}
{
  const dot = img((x, y) => (Math.hypot(x - 160, y - 90) < 1.5 ? [1, 1, 1] : [0, 0, 0]));
  const o = at(1, 0.45, dot, dot, { bdShutter: 360 }), z = at(1, 0.45, dot, dot, { bdShutter: 0 });
  let lit = 0, lit0 = 0; for (let i = 0; i < n; i++) { if (o.g[i] > 0.01) lit++; if (z.g[i] > 0.01) lit0++; }
  ok("Shake blurs along its jolt (Shutter 360 against Shutter 0)", lit > 3 * lit0 && lit0 > 0, `lit pixels ${lit} against ${lit0}`);
  const d = diff(at(1, 0.3, A, A, { bdShutter: 0 }), A).mean;
  ok("Shake moves the frame", d > 0.01, `mean change ${d}`);
}
{
  const red = img(() => [0.8, 0.1, 0.1]), blue = img(() => [0.1, 0.1, 0.8]);
  const o = at(2, 0.5, red, blue, { bdGlow: 0 });
  const L = (150) * W + 120, R = 90 * W + 200, C0 = 2 * W + 2;
  const lr = o.r[90 * W + 125], lb = o.b[90 * W + 125], rr = o.r[90 * W + 195], rb = o.b[90 * W + 195];
  ok("Sphere shows the outgoing shot on one half of the ball, the incoming on the other", (lr - lb) * (rr - rb) < 0 && Math.abs(lr - lb) > 0.2 && Math.abs(rr - rb) > 0.2, `left r-b ${(lr - lb).toFixed(2)}, right r-b ${(rr - rb).toFixed(2)}`);
  const corner = o.r[C0] + o.b[C0];
  ok("Sphere sits over a dimmed backdrop", corner < 0.85 * 0.9, `corner r+b ${corner.toFixed(3)}`);
  void L; void R;
}
{
  const drop = (st, pat, p, P = {}) => contrast(at(st, p, pat, pat, P)) / contrast(pat);
  for (const st of [3, 4]) {
    const r = drop(st, RINGS, 0.45), k = drop(st, SPOKES, 0.45);
    ok(`${NAMES[st]} blurs along the radius (rings lose more than spokes)`, r < 0.6 && k > r + 0.2, `rings kept ${r.toFixed(2)}, spokes ${k.toFixed(2)}`);
  }
  const r = drop(6, RINGS, 0.45), k = drop(6, SPOKES, 0.45);
  ok("Spin blurs round the centre (spokes lose more than rings)", k < 0.6 && r > k + 0.2, `rings kept ${r.toFixed(2)}, spokes ${k.toFixed(2)}`);
  const v = drop(5, VSTR, 0.5, { bdAngle: 0 }), h = drop(5, HSTR, 0.5, { bdAngle: 0 });
  ok("Directional blurs along Angle (vertical stripes lose, horizontal keep, at 0 degrees)", v < 0.4 && h > 0.85, `vertical kept ${v.toFixed(2)}, horizontal ${h.toFixed(2)}`);
  const sh0 = at(3, 0.3, NOISE, NOISE, { bdCX: 25, bdCY: 50, bdShutter: 0 }), sh1 = at(3, 0.3, NOISE, NOISE, { bdCX: 25, bdCY: 50 });
  const kept = (px, py) => contrast(sh1, 0, 8, px, py) / contrast(sh0, 0, 8, px, py);
  const ka = kept(0.25 * W - 0.5, cy), kc = kept(0.25 * W - 0.5 + 60, cy);
  ok("Crash Zoom aims at Center X, Y", ka > 0.8 && kc < 0.6, `detail kept at the aim ${ka.toFixed(2)}, 60 px off ${kc.toFixed(2)}`);
  const sharpX = o2 => { let best = -1, bx = 0; for (let x = 20; x < W - 20; x += 4) { const c = contrast(o2, 0, 10, x, cy); if (c > best) { best = c; bx = x; } } return bx; };
  const x1 = sharpX(at(4, 0.4, NOISE, NOISE, { bdAngle: 0 })), x2 = sharpX(at(4, 0.6, NOISE, NOISE, { bdAngle: 0 }));
  ok("Cross Zoom's centre crosses along Angle", x2 > x1 + 10, `sharpest at x ${x1}, then ${x2}`);
}
{
  const r = contrast(at(7, 0.5, RINGS, RINGS)) / contrast(RINGS), nz = contrast(at(7, 0.5, NOISE, NOISE), 0, 999) / contrast(NOISE, 0, 999);
  ok("Vector follows the picture's contours (rings keep, noise smooths)", r > 0.6 && nz < 0.7, `rings kept ${r.toFixed(2)}, noise ${nz.toFixed(2)}`);
}
{
  const o = at(8, 0.5, A, A), d = diff(o, A).mean, m0 = mean(A), m1 = mean(o);
  ok("Curl swirls the picture and keeps its light", d > 0.02 && Math.abs(m1 - m0) / m0 < 0.03, `mean change ${d}, mean ${m1.toFixed(4)} against ${m0.toFixed(4)}`);
}
{
  const o = at(9, 0.5, A, B, { bdShutter: 0 });
  let m = 0; for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const y2 = H - 1 - y; m = Math.max(m, Math.abs(o.g[y * W + x] - o.g[y2 * W + x])); }
  ok("Kaleida mirrors the picture about its slices", m < 1e-5, `max asymmetry ${m.toExponential(2)}`);
  const d = diff(at(9, 0.5, A, B, { bdSlices: 4 }), at(9, 0.5, A, B, { bdSlices: 8 })).mean;
  ok("Kaleida's Slices changes the pattern", d > 0.02, `mean change ${d}`);
}
{
  const { sliders } = compile(F, {}, { progress: 0.5 });
  let bad = 0;
  for (let k = 0; k < 30; k++) {
    const P = {};
    for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd();
    const o = runTransition(F, P, { progress: rnd(), frame: 1 }, A, B);
    for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; }
  }
  ok("Blur Dissolve range over 30 slider sets", bad === 0, `bad ${bad}`);
}

const kp = (P, im = A, frame = 0) => run(compile(KP, P, { frame }).transform, im);
ok("Kaleido Polar at Mix 0 returns the picture exactly", diff(kp({ kpMix: 0 }), A).n === 0 && diff(kp({ kpMix: 0, kpMode: 1 }), A).n === 0, "");
{
  const o = kp({ kpSpin: 0, kpFlow: 0 });
  let m = 0, c = 0; for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { m += Math.abs(o.g[y * W + x] - o.g[(H - 1 - y) * W + x]); c++; }
  const asym = m / c, ref = diff(o, img((x, y) => [o.r[(H - 1 - y) * W + ((x + 37) % W)], o.g[(H - 1 - y) * W + ((x + 37) % W)], o.b[(H - 1 - y) * W + ((x + 37) % W)]])).mean;
  ok("Polar mirrors the picture across its slices", asym < 0.2 * ref, `mean asymmetry ${asym.toFixed(4)} against ${ref.toFixed(4)} for an unrelated pair`);
  const q = Math.pow(20, 2 / 3), a0 = 0.3;
  const P1 = [cx + 10 * Math.cos(a0), cy + 10 * Math.sin(a0)], P2 = [cx + 10 * q * Math.cos(a0), cy + 10 * q * Math.sin(a0)];
  const SM = img((x, y) => { const v = 0.5 + 0.3 * Math.sin(x / 40) * Math.cos(y / 30); return [v, v, v]; });
  const o2 = kp({ kpSpin: 0, kpFlow: 0 }, SM);
  const v1 = o2.g[Math.round(P1[1]) * W + Math.round(P1[0])], v2 = o2.g[Math.round(P2[1]) * W + Math.round(P2[0])];
  ok("Polar repeats in rings out from the centre", Math.abs(v1 - v2) < 0.03, `${v1.toFixed(3)} and ${v2.toFixed(3)}`);
  const f1 = kp({ kpSpin: 0, kpFlow: 50 }, A, 0), f2 = kp({ kpSpin: 0, kpFlow: 50 }, A, 12);
  ok("Polar's rings flow", diff(f1, f2).mean > 0.01, `mean change over 12 frames ${diff(f1, f2).mean}`);
}
{
  const o = kp({ kpMode: 1, kpGap: 100, kpCell: 40, kpGlint: 0 }, A);
  const g = o.g[Math.round(cy + 0.22 * H) * W + Math.round(cx)];
  ok("Fly's Eye is dark between the lenses at Gap 100", g < 0.02, `gap ${g.toFixed(4)}`);
  const o0 = kp({ kpMode: 1, kpView: 0, kpGlint: 0, kpCell: 40 }, A), i = Math.round(cy) * W + Math.round(cx);
  ok("Fly's Eye at View 0: the lens in the middle holds the picture there", Math.abs(o0.g[i] - A.g[i]) < 0.05, `${o0.g[i].toFixed(3)} against ${A.g[i].toFixed(3)}`);
  const o1 = kp({ kpMode: 1, kpView: 100, kpGlint: 0, kpCell: 40 }, A);
  ok("Fly's Eye's View widens what each lens holds", diff(o0, o1).mean > 0.02, `mean change ${diff(o0, o1).mean}`);
}
{
  const { sliders } = compile(KP, {}, { frame: 1 });
  let bad = 0;
  for (let k = 0; k < 30; k++) {
    const P = {};
    for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd();
    const o = kp(P, A, Math.floor(rnd() * 500));
    for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; }
  }
  ok("Kaleido Polar range over 30 slider sets", bad === 0, `bad ${bad}`);
}
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
