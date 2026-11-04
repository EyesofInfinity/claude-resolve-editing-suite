import fs from "node:fs";
import { execFileSync } from "node:child_process";
import { compile } from "../../tests/cpu/dctl.mjs";

const F = "build/Develop Particles.dctl", FD = "build/Develop Particles Depth.dctl";
let s = 33;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function image(W, H, fill) {
  const n = W * H, A = { W, H, n, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n), a: new Float32Array(n) };
  for (let i = 0; i < n; i++) { const c = fill(i, i % W, (i / W) | 0); A.r[i] = c[0]; A.g[i] = c[1]; A.b[i] = c[2]; A.a[i] = c[3] === undefined ? 0 : c[3]; }
  return A;
}
function run(P, frame, A, file = F) {
  const T = compile(file, P, { frame }).transform;
  const o = { r: new Float32Array(A.n), g: new Float32Array(A.n), b: new Float32Array(A.n) };
  const R = { d: A.r, w: A.W }, G = { d: A.g, w: A.W }, B = { d: A.b, w: A.W }, AL = { d: A.a, w: A.W };
  for (let y = 0; y < A.H; y++) for (let x = 0; x < A.W; x++) { const c = T(A.W, A.H, x, y, R, G, B, AL), i = y * A.W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z; }
  return o;
}
let fails = 0, count = 0;
const ok = (name, pass, info) => { count++; console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const NAMES = ["Dust", "Embers", "Sparks", "Snow", "Fireflies", "Orbs"];
const W = 360, H = 540;
const night = image(W, H, (i, x, y) => [0.06, 0.08, 0.14]);
const grey = image(W, H, () => [0.45, 0.45, 0.45]);
const bright = image(W, H, (i, x, y) => { const v = 0.6 + 0.35 * Math.sin(x / 11) * Math.sin(y / 17); return [v, 0.96 * v, 0.85 * v]; });
const diff = (o, A, th) => { let d = 0; for (let i = 0; i < o.r.length; i++) if (Math.abs(o.g[i] - A.g[i]) > th || Math.abs(o.r[i] - A.r[i]) > th || Math.abs(o.b[i] - A.b[i]) > th) d++; return d; };
const exact = (o, A) => { let d = 0; for (let i = 0; i < o.r.length; i++) if (o.r[i] !== A.r[i] || o.g[i] !== A.g[i] || o.b[i] !== A.b[i]) d++; return d; };
const added = (o, A, ch, y0 = 0, y1 = H) => { let m = 0; for (let y = y0; y < y1; y++) for (let x = 0; x < W; x++) { const i = y * W + x; m += o[ch][i] - A[ch][i]; } return m; };
const lit = st => (st === 0 || st === 3 ? bright : night);

for (const file of [F, FD]) {
  const P = { ptAmount: 0 }; for (const [nm, v] of Object.entries(compile(file, {}, { frame: 1 }).sliders)) if (nm !== "ptAmount") P[nm] = v.hi;
  ok(`${file.slice(6)}: Particles 0 is the input exactly`, exact(run(P, 40, bright, file), bright) === 0, "");
}
for (let st = 0; st < 6; st++) {
  const A = lit(st), P = { ptStyle: st, ptDensity: 70 };
  const a1 = run(P, 120, A), b1 = run(P, 126, A), c1 = run(P, 7, A), a2 = run(P, 120, A);
  const mov = diff(a1, b1, 0.01), shown = diff(a1, A, 0.01);
  ok(`${NAMES[st]}: shows, moves in 6 frames, the same frame again is identical`, exact(a1, a2) === 0 && mov > 20 && shown > 20 && diff(a1, c1, 0.01) > 20,
     `shown ${shown}, moved ${mov}, repeat differs ${exact(a1, a2)}`);
  const a3 = run({ ...P, ptGlow: 0, ...(st === 3 ? { ptBlur: 0, ptDensity: 40 } : {}) }, 120, A);
  let ex = 0, tiny = 0;
  for (let i = 0; i < A.n; i++) { const d = Math.max(Math.abs(a3.r[i] - A.r[i]), Math.abs(a3.g[i] - A.g[i]), Math.abs(a3.b[i] - A.b[i]));
    if (d === 0) ex++; else if (d < 1e-5) tiny++; }
  ok(`${NAMES[st]}: where nothing is drawn the picture is exact`, ex > 0.2 * A.n, `${ex} of ${A.n} exact, ${tiny} moved under 1e-5`);
}
{ const dk = image(W, H, () => [0.05, 0.05, 0.05]);
  const o = run({ ptStyle: 0, ptDensity: 80 }, 120, dk), o2 = run({ ptStyle: 0, ptDensity: 80 }, 120, bright);
  ok("Dust: none in the dark, motes in the light", diff(o, dk, 1 / 255) === 0 && diff(o2, bright, 2 / 255) > 50, `dark ${diff(o, dk, 1 / 255)}, light ${diff(o2, bright, 2 / 255)}`);
  const o3 = run({ ptStyle: 0, ptDensity: 80, ptLit: 0 }, 120, dk);
  ok("Dust: Scene Light 0 shows them in the dark too", diff(o3, dk, 2 / 255) > 50, `${diff(o3, dk, 2 / 255)}`); }
{ const P = { ptStyle: 1, ptDensity: 80, ptSpread: 100 }; let lo = 0, hi = 0, rl = 0, gl = 0, rh = 0, gh = 0;
  for (const f of [100, 137, 171]) { const o = run(P, f, night);
    rl += added(o, night, "r", H * 2 / 3, H); gl += added(o, night, "g", H * 2 / 3, H); rh += added(o, night, "r", 0, H / 3); gh += added(o, night, "g", 0, H / 3); }
  const bsum = added(run(P, 100, night), night, "b");
  ok("Embers: red over green over blue", rl > gl && gl > bsum && rl > 0, `r ${rl.toFixed(1)} g ${gl.toFixed(1)} b ${bsum.toFixed(1)}`);
  ok("Embers: more light near the fire than at the top, and cooler (less green to red) up high", rl > 1.3 * rh && gh / rh < gl / rl,
     `low r ${rl.toFixed(1)} high r ${rh.toFixed(1)}, g/r low ${(gl / rl).toFixed(3)} high ${(gh / rh).toFixed(3)}`); }
{ const o = run({ ptStyle: 1, ptSrcY: -20 }, 120, night);
  ok("Embers: none when the fire is above the frame", added(o, night, "r") < 0.5, `added ${added(o, night, "r").toFixed(3)}`); }
{ const P = { ptStyle: 2, ptSrcX: 50, ptSrcY: 80, ptDir: 0, ptSpread: 20, ptDensity: 90 }; let near = 0, far = 0;
  for (const f of [100, 113, 129, 151]) { const o = run(P, f, night); for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const i = y * W + x, d = o.r[i] - night.r[i];
    if (Math.abs(x - W / 2) < W / 4 && y < 0.8 * H) near += d; if (x < 20 || x > W - 20) far += d; } }
  ok("Sparks: light above their source, none at the frame's sides", near > 5 && far < 0.01 * near, `near ${near.toFixed(1)}, sides ${far.toFixed(3)}`);
  const o = run(P, 100, night); ok("Sparks: white hot to orange (red over green over blue)", added(o, night, "r") > added(o, night, "g") && added(o, night, "g") > added(o, night, "b"),
    `r ${added(o, night, "r").toFixed(1)} g ${added(o, night, "g").toFixed(1)} b ${added(o, night, "b").toFixed(1)}`); }
{ const red = image(W, H, () => [0.6, 0.1, 0.1]), o = run({ ptStyle: 3, ptDensity: 80 }, 120, red);
  let up = 0; for (let i = 0; i < red.n; i++) if (o.g[i] > red.g[i] + 0.02 && o.r[i] <= red.r[i] + 0.2) up++;
  ok("Snow: covers (a red picture pulled toward white)", up > 100, `${up} pixels`);
  const blk = image(W, H, () => [0.0, 0.0, 0.0, 0]), blk2 = image(W, H, () => [0.01, 0.01, 0.01]);
  const o2 = run({ ptStyle: 3, ptDensity: 80 }, 120, blk2), o3 = run({ ptStyle: 3, ptDensity: 80, ptLit: 0 }, 120, blk2);
  ok("Snow: lit by the scene (dark scene, dark flakes; Scene Light 0, white flakes)", diff(o2, blk2, 0.05) < 0.1 * diff(o3, blk2, 0.05) && diff(o3, blk2, 0.05) > 200,
     `lit ${diff(o2, blk2, 0.05)}, unlit ${diff(o3, blk2, 0.05)}`); }
{ const P = { ptStyle: 0, ptDensity: 60, ptLit: 0, ptFocus: 0 }, A = image(W, H, () => [0.02, 0.02, 0.02]);
  const o0 = run({ ...P, ptBlur: 0 }, 120, A), o1 = run({ ...P, ptBlur: 100 }, 120, A);
  ok("Blur spreads particles away from Focus", diff(o1, A, 0.004) > 1.3 * diff(o0, A, 0.004) && diff(o1, A, 0.3) < diff(o0, A, 0.3),
     `touched ${diff(o0, A, 0.004)} to ${diff(o1, A, 0.004)}, strong ${diff(o0, A, 0.3)} to ${diff(o1, A, 0.3)}`); }
{ const P = { ptStyle: 1, ptDensity: 70, ptSpread: 100, ptGlow: 0 };
  const o0 = run({ ...P, ptShutter: 0 }, 120, night), o1 = run({ ...P, ptShutter: 360 }, 120, night);
  ok("Shutter streaks moving particles", diff(o1, night, 0.01) > 1.4 * diff(o0, night, 0.01), `${diff(o0, night, 0.01)} at 0, ${diff(o1, night, 0.01)} at 360`); }
{ const P = { ptStyle: 4, ptDensity: 80 };
  const o = run(P, 100, night), o2 = run(P, 108, night); let on = 0, off = 0;
  for (let i = 0; i < night.n; i++) { const a = o.g[i] - night.g[i], b2 = o2.g[i] - night.g[i]; if (a > 0.03) { on++; if (b2 < 0.3 * a) off++; } }
  ok("Fireflies: flash and go dark, green over red over blue", on > 50 && off > 0.4 * on &&
     added(o, night, "g") > added(o, night, "r") && added(o, night, "r") > added(o, night, "b"), `lit ${on}, dark 8 frames on ${off}`);
  const o3 = run({ ...P, ptTemp: 100 }, 100, night);
  ok("Fireflies: Colour 100 turns them amber", added(o3, night, "r") > added(o3, night, "g"), `r ${added(o3, night, "r").toFixed(1)} g ${added(o3, night, "g").toFixed(1)}`); }
{ const o = run({ ptStyle: 5, ptDensity: 90 }, 100, night);
  ok("Orbs: warm (red over green over blue)", added(o, night, "r") > added(o, night, "g") && added(o, night, "g") > added(o, night, "b") && added(o, night, "r") > 1,
     `r ${added(o, night, "r").toFixed(1)} g ${added(o, night, "g").toFixed(1)} b ${added(o, night, "b").toFixed(1)}`); }
{ const box = image(W, H, (i, x, y) => (y < 50 || y >= H - 50 ? [0, 0, 0] : [0.06, 0.08, 0.14]));
  const o = run({ ptStyle: 1, ptDensity: 100, ptSpread: 100 }, 120, box); let bar = 0;
  for (let y = 0; y < H; y++) if (y < 50 || y >= H - 50) for (let x = 0; x < W; x++) { const i = y * W + x; if (o.r[i] !== 0 || o.g[i] !== 0 || o.b[i] !== 0) bar++; }
  ok("Letterbox bars stay black", bar === 0 && diff(o, box, 0.01) > 50, `bar pixels touched ${bar}`); }
for (const st of [0, 1, 3, 4]) {
  const A = lit(st), Aw = image(W, H, (i, x, y) => [A.r[i], A.g[i], A.b[i], x < W / 2 ? 1.0 : 0.0]);
  const P = { ptStyle: st, ptDensity: 80, ptGlow: 0 };
  const o = run(P, 120, A), o0 = run({ ...P, ptDepthIn: 0 }, 120, Aw, FD), o1 = run(P, 120, Aw, FD);
  let l = 0, r = 0, lp = 0, rp = 0;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const i = y * W + x, d = Math.abs(o1.r[i] - A.r[i]) + Math.abs(o1.g[i] - A.g[i]), dp = Math.abs(o.r[i] - A.r[i]) + Math.abs(o.g[i] - A.g[i]);
    if (x < W / 2 - 40) { l += d; lp += dp; } else if (x > W / 2 + 40) { r += d; rp += dp; } }
  ok(`Depth (${NAMES[st]}): Depth In 0 is Develop Particles exactly; a near wall hides most of them`, exact(o0, o) === 0 && l < 0.5 * lp && r > 0.9 * rp,
     `behind the wall ${l.toFixed(1)} of ${lp.toFixed(1)}, open side ${r.toFixed(1)} of ${rp.toFixed(1)}`);
}
for (const file of [F, FD]) {
  const { sliders } = compile(file, {}, { frame: 1 }); let bad = 0; const small = image(160, 270, () => [rnd(), rnd(), rnd(), rnd()]);
  for (let k = 0; k < 30; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd(); P.ptStyle = Math.round(P.ptStyle);
    const o = run(P, Math.floor(rnd() * 5000), small, file); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok(`${file.slice(6)}: range over 30 slider sets`, bad === 0, `bad ${bad}`);
}

const sumAdd = (o, A, ch, keep) => { let m = 0; for (let y = 0; y < A.H; y++) for (let x = 0; x < A.W; x++) if (!keep || keep(x, y)) { const i = y * A.W + x; m += o[ch][i] - A[ch][i]; } return m; };
const SPK = { ptStyle: 2, ptSrcX: 50, ptSrcY: 60, ptDir: 0, ptSpread: 60, ptDensity: 80 };
{ const half = image(W, H, (i, x) => (x < W / 2 ? [0, 0, 0] : [0.25, 0.25, 0.25]));
  for (const st of [1, 2, 4, 5]) {
    const P = st === 2 ? SPK : { ptStyle: st, ptDensity: 80 };
    const o0 = run({ ...P, ptGlow: 0 }, 120, half), o1 = run({ ...P, ptGlow: 100 }, 120, half);
    let blk = 0, lit2 = 0, darker = 0; const s = [0, 0, 0];
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const i = y * W + x;
      const d = [o1.r[i] - o0.r[i], o1.g[i] - o0.g[i], o1.b[i] - o0.b[i]];
      if (x < W / 2) { if (d[0] !== 0 || d[1] !== 0 || d[2] !== 0) blk++; continue; }
      if (Math.max(...d) > 1 / 255) lit2++;
      if (Math.min(...d) < -1e-6 && Math.max(o1.r[i], o1.g[i], o1.b[i]) < 0.911) darker++;
      for (let c = 0; c < 3; c++) s[c] += d[c]; }
    const hue = st === 4 ? s[1] > s[0] && s[0] > s[2] : s[0] > s[1] && s[1] > s[2];
    ok(`Scene Glow (${NAMES[st]}): black lit by nothing, grey lit, never darker, in the particles' colour`,
       blk === 0 && lit2 > 0.03 * W * H / 2 && darker === 0 && hue,
       `black half changed ${blk}, grey half lit ${lit2} of ${W * H / 2}, darker ${darker}, added r ${s[0].toFixed(1)} g ${s[1].toFixed(1)} b ${s[2].toFixed(1)}`);
  }
  const grey25 = image(W, H, () => [0.25, 0.25, 0.25]), sx = W / 2, sy = 0.5 * H;
  const P = { ...SPK, ptSrcY: 50, ptDensity: 0, ptSrcGlow: 100 };
  const o0 = run({ ...P, ptGlow: 0 }, 120, grey25), o1 = run({ ...P, ptGlow: 100 }, 120, grey25);
  const ring = (r0, r1) => { let m = 0, n = 0; for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const d = Math.hypot(x + 0.5 - sx, y + 0.5 - sy);
    if (d >= r0 && d < r1) { const i = y * W + x; m += o1.r[i] - o0.r[i]; n++; } } return m / Math.max(n, 1); };
  const nr = ring(20, 40), fr = ring(110, 150);
  ok("Scene Glow: the source's light on the scene falls off with distance and reaches", nr > 3 * fr && fr > 1e-4,
     `added red a pixel 20 to 40 px out ${nr.toFixed(4)}, 110 to 150 px out ${fr.toFixed(5)}`); }
{ const P = { ...SPK, ptSrcY: 50, ptDensity: 0, ptGlow: 0 }, sx = W / 2, sy = 0.5 * H;
  const o0 = run({ ...P, ptSrcGlow: 0 }, 120, night), o1 = run({ ...P, ptSrcGlow: 100 }, 120, night);
  let tot = 0, near = 0, best = -1, bx = 0, by = 0; const s = [0, 0, 0];
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const i = y * W + x, d = o1.r[i] - o0.r[i];
    tot += d; if (Math.hypot(x + 0.5 - sx, y + 0.5 - sy) < 30) near += d; if (d > best) { best = d; bx = x; by = y; }
    s[0] += d; s[1] += o1.g[i] - o0.g[i]; s[2] += o1.b[i] - o0.b[i]; }
  const off = Math.hypot(bx + 0.5 - sx, by + 0.5 - sy);
  ok("Source Glow: a hot point on the source, orange", tot > 1 && near > 0.6 * tot && off < 4 && s[0] > s[1] && s[1] > s[2],
     `added ${tot.toFixed(2)}, within 30 px ${(100 * near / tot).toFixed(1)}%, brightest ${off.toFixed(1)} px from the source, r ${s[0].toFixed(1)} g ${s[1].toFixed(1)} b ${s[2].toFixed(1)}`); }
{ const sm = image(180, 270, () => [0.06, 0.08, 0.14]);
  const cv = b => { const v = []; for (let f = 0; f < 72; f += 2) v.push(sumAdd(run({ ...SPK, ptSrcY: 70, ptDensity: 50, ptGlow: 0, ptSrcGlow: 0, ptBursts: b, ptFps: 24 }, f, sm), sm, "r"));
    const m = v.reduce((a, b2) => a + b2, 0) / v.length; return [Math.sqrt(v.reduce((a, b2) => a + (b2 - m) * (b2 - m), 0) / v.length) / Math.max(m, 1e-9), Math.min(...v) / Math.max(m, 1e-9)]; };
  const [c0, lo0] = cv(0), [c1, lo1] = cv(100);
  ok("Bursts: at 100 the light comes and goes, at 0 it is steady", c1 > 2 * c0 && lo1 < 0.1 && lo0 > 0.3,
     `spread over mean: ${c0.toFixed(2)} at 0, ${c1.toFixed(2)} at 100; the least frame over the mean ${lo0.toFixed(2)} at 0, ${lo1.toFixed(2)} at 100`); }
{ const P = { ptStyle: 2, ptDensity: 60, ptSrcX: 50, ptSrcY: 40, ptDir: 180, ptSpread: 30, ptBlur: 0, ptGlow: 0, ptSrcGlow: 0, ptBursts: 0 };
  const yF = 0.8 * H; let bF = 0, bN = 0, aF = 0, aN = 0;
  for (const f of [100, 113, 129, 151]) {
    const oF = run({ ...P, ptFloor: 80 }, f, night), oN = run({ ...P, ptFloor: 150 }, f, night);
    bF += sumAdd(oF, night, "r", (x, y) => y >= yF + 10); bN += sumAdd(oN, night, "r", (x, y) => y >= yF + 10);
    aF += sumAdd(oF, night, "r", (x, y) => y >= yF - 40 && y < yF); aN += sumAdd(oN, night, "r", (x, y) => y >= yF - 40 && y < yF); }
  ok("Bounce: sparks stay above the floor and hop along it; with no floor they fall through", bN > 5 && bF < 0.15 * bN && aF > aN,
     `below the floor ${bF.toFixed(1)} (none: ${bN.toFixed(1)}), the 40 rows above it ${aF.toFixed(1)} (none: ${aN.toFixed(1)})`); }

const OUT = "../../tests/out/particles/checks";
fs.mkdirSync(OUT, { recursive: true });
const ZQ = ["zqM", "zqT", "zqQ", "zqA", "zqR", "zqL", "zqS", "zqOU", "zqOV", "zqRing", "zqPh", "zqMott", "zqMa", "zqMb", "zqK"];
const PROBE_MAIN = `__DEVICE__ float3 transform(int p_Width, int p_Height, int p_X, int p_Y, __TEXTURE__ p_TexR, __TEXTURE__ p_TexG, __TEXTURE__ p_TexB)
{
    float3 o = make_float3(0.0f, 0.0f, 0.0f);
    if (zqM < 0.5f) {
        float4 c = camAt(zqT, zqQ, zqA);
        float px = p_Y == 0 ? 100.0f : (p_Y == 1 ? 960.0f : 1700.0f);
        float py = p_Y == 0 ? 80.0f : (p_Y == 1 ? 540.0f : 1000.0f);
        float2 f = camFwd(c, px, py, 960.0f, 540.0f, 1.0f);
        float2 v = camInv(c, px, py, 960.0f, 540.0f, 1.0f);
        float2 rc = camReach(zqQ, zqA);
        if (p_X == 0) o = make_float3(c.x, c.y, c.z);
        if (p_X == 1) o = make_float3(c.w, camG(zqQ), rc.x);
        if (p_X == 2) o = make_float3(f.x, f.y, rc.y);
        if (p_X == 3) o = make_float3(v.x, v.y, 0.0f);
    } else if (zqM < 1.5f) {
        float u = ((float)(p_X) - 0.5f * (float)(p_Width) + 0.5f) * zqK;
        float v = ((float)(p_Y) - 0.5f * (float)(p_Height) + 0.5f) * zqK;
        o = make_float3(lensSpot(u, v, zqR, zqL, zqS, zqOU, zqOV, zqRing, zqPh, zqMott, zqMa, zqMb), spot(u, _fabs(v), zqR, zqL, zqS), 0.0f);
    } else {
        o = make_float3(poolLight((float)(p_X) * zqK, zqR, zqL), 0.0f, 0.0f);
    }
    return make_float3(o.x, o.y, o.z);
}
`;
function probeFile(file, name) {
  const t = fs.readFileSync(file, "utf8"), i = t.indexOf("__DEVICE__ float3 transform(");
  const ui = ZQ.map(n => `DEFINE_UI_PARAMS(${n}, ${n}, DCTLUI_SLIDER_FLOAT, 0.0, -100000.0, 100000.0, 0.001)`).join("\n");
  const p = `${OUT}/probe_${name}.dctl`;
  fs.writeFileSync(p, ui + "\n" + t.slice(0, i) + PROBE_MAIN);
  return p;
}
const D1 = { d: new Float32Array(1), w: 1 };
const probe = (pf, P, w, h) => { const T = compile(pf, P, { frame: 1 }).transform, o = [];
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) o.push(T(w, h, x, y, D1, D1, D1)); return o; };
const PB = probeFile(F, "build");
{ // no NaN, no infinity, nothing below 0, over extreme settings and a grid round the disc
  let bad = 0, n = 0;
  for (const R of [0, 0.3, 3, 60, 200]) for (const L of [0, 40, 300]) for (const s0 of [0.375, 3]) for (const [ou, ov] of [[0, 0], [5, -3], [300, 300]]) for (const rm of [0, 1]) {
    const v = probe(PB, { zqM: 1, zqR: R, zqL: L, zqS: s0, zqOU: ou, zqOV: ov, zqRing: rm, zqPh: 2.1, zqMott: rm, zqMa: 0.4, zqMb: 5.9, zqK: (R + L + 6) / 4 }, 11, 11);
    for (const c of v) { n++; if (!Number.isFinite(c.x) || !Number.isFinite(c.y) || c.x < 0 || c.y < 0) bad++; } }
  ok("lensSpot and spot: no NaN, no infinity, none below 0", bad === 0, `${n} values, bad ${bad}`);
  const K = 0.5, GW = 128, GH = 64;
  const grid = P => probe(PB, { zqM: 1, zqS: 0.75, zqK: K, zqL: 0, zqOU: 0, zqOV: 0, zqRing: 0, zqMott: 0, zqPh: 1.3, zqMa: 0.7, zqMb: 2.2, ...P }, GW, GH);
  const tot = (v, k = "x") => v.reduce((a, c) => a + c[k], 0) * K * K;
  const cen = v => { let m = 0, s = 0; v.forEach((c, i) => { m += c.x * ((i % GW) - GW / 2 + 0.5) * K; s += c.x; }); return m / s; };
  const plain = grid({ zqR: 12 }), swept = grid({ zqR: 12, zqL: 30 }), rings = grid({ zqR: 12, zqRing: 1, zqMott: 0.3 }), cat = grid({ zqR: 12, zqOU: 9.6 });
  const e0 = tot(plain), e1 = tot(swept), e2 = tot(rings), e3 = tot(cat), es0 = tot(plain, "y"), es1 = tot(swept, "y");
  const at = (v, u) => v[(GH / 2) * GW + Math.round(u / K + GW / 2 - 0.5)].x;
  ok("lensSpot: the disc carries the light spot does, still and swept (within 5%)", Math.abs(e0 / es0 - 1) < 0.05 && Math.abs(e1 / es1 - 1) < 0.05 && es0 > 0.95 && es0 < 1.05,
     `still ${e0.toFixed(3)} against spot ${es0.toFixed(3)}, swept ${e1.toFixed(3)} against ${es1.toFixed(3)}`);
  ok("lensSpot: rings and mottle keep the light (within 5%)", Math.abs(e2 / e0 - 1) < 0.05, `${(e2 / e0).toFixed(3)} of the plain disc`);
  ok("lensSpot: the cat's eye only takes light away, toward the offset side", e3 < 0.9 * e0 && e3 > 0.3 * e0 && Math.max(...cat.map(c => c.x)) <= Math.max(...plain.map(c => c.x)) * 1.0001 && cen(cat) > 2,
     `${(e3 / e0).toFixed(3)} of the disc, its middle ${cen(cat).toFixed(2)} px toward the offset`);
  ok("lensSpot: the rim brighter than the middle", at(plain, 10.75) > 1.05 * at(plain, 0.25), `${at(plain, 10.75).toExponential(3)} at 0.9 R, ${at(plain, 0.25).toExponential(3)} at the middle`);
  const sm = grid({ zqR: 0.5, zqOU: 3, zqRing: 1, zqMott: 1 });
  ok("lensSpot: a spot too small to be a disc is spot exactly", sm.every(c => c.x === c.y), "");
  const pl = probe(PB, { zqM: 2, zqR: 10, zqL: 100, zqK: 0.25 }, 600, 1).map(c => c.x);
  let mono = true, e = 0; for (let k = 0; k < pl.length; k++) { if (k && pl[k] > pl[k - 1]) mono = false; e += 2 * Math.PI * (k * 0.25) * pl[k] * 0.25; }
  ok("poolLight: finite, falling, nothing past its reach, about unit light", pl.every(Number.isFinite) && mono && pl.slice(400).every(v => v === 0) && e > 0.8 && e < 1.0,
     `total ${e.toFixed(3)}, at 0 px ${pl[0].toExponential(3)}, at 99 px ${pl[396].toExponential(2)}`); }

const CAM = "../../tests/out/particles/cam", FB = n => `${CAM}/Develop Particles - ${n}.dctl`, FBD = n => `${CAM}/Develop Particles Depth - ${n}.dctl`;
const py = args => { try { return { out: execFileSync("python", ["-I", ...args], { encoding: "utf8" }), code: 0 }; } catch (e) { return { out: String(e.stdout || "") + String(e.stderr || ""), code: e.status || 1 }; } };
const SHOTS = ["bake_a", "bake_b", "bake_c"];
const HAVE = SHOTS.every(m => fs.existsSync(FB(m)) && fs.existsSync(FBD(m)) && fs.existsSync(`${CAM}/${m}.camera.json`));
if (!HAVE) console.log(`skip the checks on real baked shots: ${CAM} does not hold ${SHOTS.join(", ")} (bake them with camera.py)`);
if (HAVE) for (const m of SHOTS) for (const f of [FB(m), FBD(m)]) {
  const r = py(["camref.py", f, `${CAM}/${m}.camera.json`, `${OUT}/camref_${m}.json`]);
  const lines = r.out.trim().split("\n").filter(l => /^(pass|FAIL) /.test(l));
  ok(`Camera bake read back (${f.slice(CAM.length + 1)}): ${lines.length} checks in camref.py`, r.code === 0 && lines.length === 5 && lines.every(l => l.startsWith("pass")),
     lines.map(l => l.replace(/^(pass|FAIL) /, "")).filter(l => /worst|samples/.test(l)).join("; ") || r.out.slice(0, 400));
}
if (HAVE) for (const m of SHOTS) {
  const R = JSON.parse(fs.readFileSync(`${OUT}/camref_${m}.json`, "utf8")), pf = probeFile(FB(m), m);
  let worst = 0, worstP = 0, bad = 0;
  for (const row of R.rows) {
    for (const [amt, want] of [[0.7, row.cam07], [1.0, row.cam]]) {
      const v = probe(pf, { zqM: 0, zqT: row.ts, zqQ: row.q, zqA: amt }, 4, 3);
      const got = [v[0].x, v[0].y, v[0].z, v[1].x];
      for (let k = 0; k < 4; k++) { const d = Math.abs(got[k] - want[k]); if (!(d <= 1e-6)) bad++; worst = Math.max(worst, d); }
      if (!(Math.abs(v[1].y - row.g) <= 1e-9)) bad++;
      if (!Number.isFinite(v[1].z) || !Number.isFinite(v[2].z) || v[2].z > 1 || v[2].z <= 0) bad++;
      if (amt === 1.0) for (let p = 0; p < 3; p++) {
        const f2 = v[p * 4 + 2], i2 = v[p * 4 + 3];
        const d = Math.max(Math.abs(f2.x - row.fwd[p][0]), Math.abs(f2.y - row.fwd[p][1]), Math.abs(i2.x - row.inv[p][0]), Math.abs(i2.y - row.inv[p][1]));
        if (!(d <= 1e-3)) bad++; worstP = Math.max(worstP, d); }
    }
  }
  ok(`Camera decoder (${m}): the DCTL reads the path as camera.py does`, bad === 0,
     `${R.rows.length} times and depths, worst ${worst.toExponential(2)} in the path, ${worstP.toExponential(2)} px through fwd and inv; bad ${bad}`);
}
{ const r = py(["camref.py", "--synth", OUT]);
  ok("Camera: the made-up paths bake", r.code === 0, r.code ? r.out.slice(0, 300) : "");
  const G = image(W, H, () => [0.45, 0.45, 0.45]), pan = `${OUT}/Develop Particles - synth_pan.dctl`, par = `${OUT}/Develop Particles - synth_par.dctl`;
  const shifted = (a, b, dx, dy) => { let worst = 0, n = 0; for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const xs = x - dx, ys = y - dy;
    if (xs < 0 || xs >= W || ys < 0 || ys >= H) continue; const i = y * W + x, j = ys * W + xs; n++;
    worst = Math.max(worst, Math.abs(a.r[i] - b.r[j]), Math.abs(a.g[i] - b.g[j]), Math.abs(a.b[i] - b.b[j])); } return [worst, n]; };
  for (const st of [0, 3]) {
    const P = { ptStyle: st, ptDensity: 70, ptShutter: 0, ptFps: 24, ptShotStart: 10, ptLit: 0, ptBlur: st === 3 ? 0 : 50 };
    const L = run(P, 246, G), C = run(P, 246, G, pan), C5 = run({ ...P, ptCamera: 50 }, 246, G, pan), C0 = run({ ...P, ptCamera: 0 }, 246, G, pan);
    const [w1, n1] = shifted(C, L, 120, -60), [w5] = shifted(C5, L, 60, -30), [w0] = shifted(C, L, 0, 0);
    ok(`Camera (${NAMES[st]}): a pan moves the particles with it exactly; Camera Match 50 half; 0 none`,
       w1 < 1e-6 && w5 < 1e-6 && w0 > 0.01 && exact(C0, L) === 0 && n1 > 0.4 * W * H,
       `worst ${w1.toExponential(2)} over ${n1} pixels, at 50 ${w5.toExponential(2)}, unmoved ${w0.toFixed(3)}, Camera Match 0 differs from the plain build at ${exact(C0, L)} pixels`);
  }
  { const P = { ptStyle: 0, ptDensity: 70, ptFps: 24, ptShotStart: 10, ptLit: 0 }, th = (o) => diff(o, G, 0.004);
    const l0 = th(run({ ...P, ptShutter: 0 }, 246, G)), l1 = th(run({ ...P, ptShutter: 180 }, 246, G));
    const c0 = th(run({ ...P, ptShutter: 0 }, 246, G, pan)), c1 = th(run({ ...P, ptShutter: 180 }, 246, G, pan));
    ok("Camera: the pan streaks the particles over the shutter", c1 / c0 > 1.3 * (l1 / l0), `pixels touched, Shutter 0 to 180: ${c0} to ${c1} with the pan, ${l0} to ${l1} without`); }
  for (const q of [0.3, 0.8]) {
    const P = { ptStyle: 0, ptDensity: 80, ptDSpread: 0, ptDepth: q / 0.55 * 50, ptShutter: 0, ptFps: 24, ptShotStart: 0, ptLit: 0 };
    const L = run(P, 12, G), C = run(P, 12, G, par);
    let best = -1, bv = 1e9, v0 = 0;
    for (let s = 0; s <= 80; s++) { let m = 0, n = 0; for (let y = 0; y < H; y++) for (let x = 80; x < W; x++) { const i = y * W + x, j = i - s; m += Math.abs(C.g[i] - L.g[j]); n++; }
      m /= n; if (s === 0) v0 = m; if (m < bv) { bv = m; best = s; } }
    ok(`Camera parallax: a plane at disparity ${q} slides ${60 * q} px`, Math.abs(best - 60 * q) <= 1 && bv < 0.1 * v0,
       `best shift ${best} px, mismatch there ${bv.toExponential(2)} against ${v0.toExponential(2)} unmoved`);
  }
}
if (HAVE) { for (const file of [FB("bake_a"), FBD("bake_a")]) {
    const P = { ptAmount: 0 }; for (const [nm, v] of Object.entries(compile(file, {}, { frame: 1 }).sliders)) if (nm !== "ptAmount") P[nm] = v.hi;
    ok(`Camera bake ${file.slice(CAM.length + 1)}: Particles 0 is the input exactly`, exact(run(P, 40, bright, file), bright) === 0, ""); }
  const P = { ptStyle: 3, ptDensity: 70, ptFps: 25, ptShotStart: 0 };
  const c0 = run({ ...P, ptCamera: 0 }, 50, bright, FB("bake_a")), b0 = run(P, 50, bright);
  ok("Camera bake bake_a: Camera Match 0 is Develop Particles exactly", exact(c0, b0) === 0, `${exact(c0, b0)} pixels differ`);
  const c1 = run({ ...P, ptStyle: 0, ptGlow: 0 }, 50, bright, FB("bake_a")); let ex = 0; for (let i = 0; i < bright.n; i++) if (c1.r[i] === bright.r[i] && c1.g[i] === bright.g[i] && c1.b[i] === bright.b[i]) ex++;
  ok("Camera bake bake_a: where nothing is drawn the picture is exact (Dust, 2 s into the shot)", ex > 0.2 * bright.n && diff(c1, bright, 0.01) > 20, `${ex} of ${bright.n} exact`);
  for (const st of [3, 4]) { const A = lit(st), Aw = image(W, H, (i, x) => [A.r[i], A.g[i], A.b[i], x < W / 2 ? 1.0 : 0.0]);
    const Q = { ptStyle: st, ptDensity: 80, ptFps: 25, ptShotStart: 0 };
    const o = run(Q, 50, A, FB("bake_a")), o0 = run({ ...Q, ptDepthIn: 0 }, 50, Aw, FBD("bake_a"));
    ok(`Camera bake bake_a (${NAMES[st]}): Depth In 0 is the plain baked DCTL exactly`, exact(o0, o) === 0 && diff(o, A, 0.01) > 20, `${exact(o0, o)} pixels differ`); } }
if (HAVE) for (const file of [FB("bake_a"), FBD("bake_a"), FB("bake_b"), FB("bake_c")]) {
  const { sliders } = compile(file, {}, { frame: 1 }); let bad = 0; const small = image(160, 270, () => [rnd(), rnd(), rnd(), rnd()]);
  for (let k = 0; k < 30; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd(); P.ptStyle = Math.round(P.ptStyle);
    const fr = Math.floor(rnd() * 5000), t = fr / P.ptFps; P.ptShotStart = Math.max(0, t - (-1 + 7 * rnd()));
    const o = run(P, fr, small, file); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok(`Camera bake ${file.slice(CAM.length + 1)}: range over 30 slider sets, shot time -1 to 6 s`, bad === 0, `bad ${bad}`);
}
console.log(fails ? `${fails} of ${count} FAILED` : `all ${count} pass`);
process.exit(fails ? 1 : 0);
