import { compile } from "../../tests/cpu/dctl.mjs";

const SL = "build/Develop Stage Light.dctl", LZ = "build/Develop Laser.dctl";
let s = 31;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function image(W, H, fill) {
  const n = W * H, A = { W, H, n, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let i = 0; i < n; i++) { const c = fill(i, i % W, (i / W) | 0); A.r[i] = c[0]; A.g[i] = c[1]; A.b[i] = c[2]; }
  return A;
}
function run(file, P, frame, A) {
  const T = compile(file, P, { frame }).transform;
  const o = { r: new Float32Array(A.n), g: new Float32Array(A.n), b: new Float32Array(A.n) };
  const R = { d: A.r, w: A.W }, G = { d: A.g, w: A.W }, Bt = { d: A.b, w: A.W };
  for (let y = 0; y < A.H; y++) for (let x = 0; x < A.W; x++) { const c = T(A.W, A.H, x, y, R, G, Bt), i = y * A.W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z; }
  return o;
}
let fails = 0, count = 0;
const ok = (name, pass, info) => { count++; console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const Y = (o, i) => 0.2126 * o.r[i] + 0.7152 * o.g[i] + 0.0722 * o.b[i];
const lin = v => Math.pow(Math.max(v, 0), 2.4);
const stops = (a, b) => Math.log2(lin(b) / lin(a));
const flat = (W, H, c) => image(W, H, () => c);
const A = image(240, 135, (i, x, y) => { const v = 0.3 + 0.25 * Math.sin(x / 9) * Math.cos(y / 7) + 0.1 * rnd(); return [Math.min(1, v * 1.1), Math.min(1, v), Math.min(1, 0.8 * v)]; });
const W = 480, H = 270, at = (x, y) => y * W + x;
const black = flat(W, H, [0, 0, 0]), grey = flat(W, H, [0.5, 0.5, 0.5]);

for (const [file, amt, modes, key, names] of [[SL, "slAmount", 3, "slMode", ["Spotlight", "Reverse Spotlight", "Stage Light"]],
  [LZ, "lzAmount", 4, "lzMode", ["Laser Beam", "Zap To", "Zap From", "Muzzle Flash"]]]) {
  for (let m = 0; m < modes; m++) {
    const P = {}; for (const [nm, v] of Object.entries(compile(file, {}, { frame: 1 }).sliders)) if (nm !== amt) P[nm] = v.hi;
    P[amt] = 0; P[key] = m;
    const o = run(file, P, 240, A); let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < A.n; i++) if (o[k][i] !== A[k][i]) d++;
    ok(`${names[m]}: off is identity`, d === 0, `differ ${d}`);
  }
}

{ const o = run(SL, { slMode: 0, slX: 50, slY: 50, slGel: 0 }, 1, grey);
  const c = stops(0.5, Y(o, at(240, 135))), corner = stops(0.5, Y(o, at(3, 3)));
  ok("Spotlight: the middle gains Light (0.7 stops, 0.9 with the hot centre), the corner takes Ambient (-2)", c > 0.6 && c < 1.0 && Math.abs(corner + 2) < 0.05, `middle ${c.toFixed(2)} stops, corner ${corner.toFixed(2)}`);
  const ob = run(SL, { slMode: 0, slLight: 3 }, 1, black); let mx = 0; for (let i = 0; i < ob.g.length; i++) mx = Math.max(mx, ob.r[i], ob.g[i], ob.b[i]);
  ok("Spotlight: black stays black (it relights, nothing is added)", mx === 0, `most ${mx}`);
  const ow = run(SL, { slMode: 0, slX: 50, slY: 50, slGel: 80 }, 1, grey), oc = run(SL, { slMode: 0, slX: 50, slY: 50, slGel: -80 }, 1, grey), i = at(240, 135);
  ok("Spotlight: Gel warms the pool above 0, cools it below", ow.r[i] > ow.b[i] + 0.05 && oc.b[i] > oc.r[i] + 0.05, `warm r ${ow.r[i].toFixed(3)} b ${ow.b[i].toFixed(3)}, cold r ${oc.r[i].toFixed(3)} b ${oc.b[i].toFixed(3)}`);
  const hd = run(SL, { slMode: 0, slX: 50, slY: 50, slGel: 0, slSoft: 0, slAspect: 50 }, 1, grey), sf = run(SL, { slMode: 0, slX: 50, slY: 50, slGel: 0, slSoft: 100, slAspect: 50 }, 1, grey);
  const R = (0.06 + 0.0065 * 40) * H, e1 = Math.round(240 + 0.8 * R), e2 = Math.round(240 + 1.2 * R);
  ok("Spotlight: Softness widens the penumbra (hard: in and out of the edge differ by Light - Ambient; soft: less)", stops(Y(hd, at(e2, 135)), Y(hd, at(e1, 135))) > 2.4 && stops(Y(sf, at(e2, 135)), Y(sf, at(e1, 135))) < 1.6,
     `hard ${stops(Y(hd, at(e2, 135)), Y(hd, at(e1, 135))).toFixed(2)} stops, soft ${stops(Y(sf, at(e2, 135)), Y(sf, at(e1, 135))).toFixed(2)}`); }
{ const o = run(SL, { slMode: 1, slX: 50, slY: 50, slLight: 0, slGel: 0 }, 1, grey);
  ok("Reverse Spotlight: the pool takes Ambient, the corner is unchanged", Math.abs(stops(0.5, Y(o, at(240, 135))) + 2) < 0.05 && Math.abs(Y(o, at(3, 3)) - 0.5) < 1e-6,
     `middle ${stops(0.5, Y(o, at(240, 135))).toFixed(2)} stops, corner ${Y(o, at(3, 3)).toFixed(4)}`); }
{ const P = { slMode: 2, slBeams: 3, slFan: 0, slAngle: 0, slRig: 50, slSize: 30, slLand: 150 };
  const o = run(SL, P, 1, black), cx = [240 - 0.25 * W, 240, 240 + 0.25 * W].map(Math.round);
  let inn = 0, out = 0; for (let y = 60; y < 220; y++) { for (const x of cx) inn += Y(o, at(x, y)) / 3; out += (Y(o, at(Math.round(cx[0] / 2 + cx[1] / 2), y)) + Y(o, at(Math.round(cx[1] / 2 + cx[2] / 2), y))) / 2; }
  inn /= 160; out /= 160;
  ok("Stage Light: on black the haze lights inside the beams, black between them", inn > 0.12 && out < 0.01, `inside ${inn.toFixed(3)}, between ${out.toFixed(4)}`);
  const top = Y(o, at(240, 30)), low = Y(o, at(240, 250));
  ok("Stage Light: a beam is brighter near its lamp than far from it", top > low * 1.3, `near ${top.toFixed(3)}, far ${low.toFixed(3)}`);
  const o2 = run(SL, P, 260, black); let mv = 0; for (let y = 60; y < 220; y++) if (o2.g[at(240, y)] !== o.g[at(240, y)]) mv++;
  ok("Stage Light: the smoke in the beam drifts frame to frame", mv > 100, `moved ${mv} of 160`);
  const g = run(SL, { slMode: 2, slBeams: 1, slAngle: 0, slLand: 80, slHaze: 0 }, 1, grey);
  const pool = stops(0.5, Y(g, at(240, Math.round(0.8 * H)))), side = stops(0.5, Y(g, at(20, Math.round(0.8 * H))));
  ok("Stage Light: where the beam lands the floor is lit (Light + half a stop), the stage round it at Ambient", pool > 1.0 && Math.abs(side + 2) < 0.05, `pool ${pool.toFixed(2)} stops, side ${side.toFixed(2)}`);
  const tr = image(W, H, (i, x) => (Math.abs(x - 240) < 6 ? [0.04, 0.04, 0.04] : [0.4, 0.4, 0.4]));
  const P1 = { slMode: 2, slBeams: 1, slAmb: 0, slLight: 0, slLand: 150 }, d1 = run(SL, { ...P1, slDepth: 100 }, 1, tr), d0 = run(SL, { ...P1, slDepth: 0 }, 1, tr), j = at(240, 120);
  ok("Stage Light: Depth puts the haze behind a dark silhouette", Y(d1, j) < 0.04 + 0.6 * (Y(d0, j) - 0.04) && Y(d0, j) > 0.1, `trunk at Depth 100 ${Y(d1, j).toFixed(3)}, at Depth 0 ${Y(d0, j).toFixed(3)}`); }

{ const P = { lzMode: 0, lzX0: 10, lzY0: 50, lzX1: 90, lzY1: 50, lzHue: 130, lzFlick: 0 };
  const tall = flat(600, 1080, [0, 0, 0]), ot = run(LZ, P, 240, tall), tc = 540 * 600 + 300, toff = 660 * 600 + 300;
  ok("Laser Beam: a white core on the line (1080 rows), dark 120 px off it", Y(ot, tc) > 0.9 && ot.r[tc] > 0.8 && ot.b[tc] > 0.8 && Y(ot, toff) < 0.12, `core ${Y(ot, tc).toFixed(3)} (r ${ot.r[tc].toFixed(2)} b ${ot.b[tc].toFixed(2)}), off ${Y(ot, toff).toFixed(3)}`);
  const o = run(LZ, P, 240, black), near = at(240, 138);
  ok("Laser Beam: its glow takes Hue (green round a hue 130 beam)", o.g[near] > 1.5 * o.r[near] && o.g[near] > 1.5 * o.b[near], `3 px off r ${o.r[near].toFixed(3)} g ${o.g[near].toFixed(3)} b ${o.b[near].toFixed(3)}`);
  const ob = run(LZ, { ...P, lzLength: 20, lzRate: 2 }, 6, black); let lit = 0, n = 0;
  for (let x = Math.round(0.12 * W); x < Math.round(0.88 * W); x++) { n++; if (Y(ob, at(x, 135)) > 0.5) lit++; }
  ok("Laser Beam: under Length 100 a bolt lights only its share of the path", lit > 0.08 * n && lit < 0.35 * n, `lit ${lit} of ${n} px along the path`);
  const ob2 = run(LZ, { ...P, lzLength: 20, lzRate: 2 }, 9, black); let mx1 = 0, mx2 = 0, s1 = 0, s2 = 0;
  for (let x = 0; x < W; x++) { const a = Y(ob, at(x, 135)), b2 = Y(ob2, at(x, 135)); s1 += a * x; mx1 += a; s2 += b2 * x; mx2 += b2; }
  ok("Laser Beam: the bolt travels from Start toward End", s2 / mx2 > s1 / mx1 + 10, `centre of light ${(s1 / mx1).toFixed(0)} px at frame 6, ${(s2 / mx2).toFixed(0)} at 9`); }

{ const P = { lzMode: 1, lzX0: 20, lzY0: 50, lzX1: 80, lzY1: 50, lzRate: 6, lzFlick: 0 };
  const o = run(LZ, P, 241, black), o2 = run(LZ, P, 245, black);
  const colMax = (o, x) => { let m = 0; for (let y = 60; y < 210; y++) m = Math.max(m, Y(o, at(x, y))); return m; };
  ok("Zap To: the arc crosses between the points (every column lit), white where it leaves and strikes", colMax(o, 200) > 0.8 && colMax(o, 280) > 0.8 && Y(o, at(Math.round(0.2 * W), 135)) > 0.9 && Y(o, at(Math.round(0.8 * W), 135)) > 0.9,
     `column 200 ${colMax(o, 200).toFixed(2)}, 280 ${colMax(o, 280).toFixed(2)}, contacts ${Y(o, at(96, 135)).toFixed(2)} ${Y(o, at(384, 135)).toFixed(2)}`);
  let df = 0; for (let i = 0; i < o.g.length; i++) if (Math.abs(o.g[i] - o2.g[i]) > 0.2) df++;
  ok("Zap To: a new strike takes a new path", df > 300, `${df} px changed by over 0.2`);
  const ol = run(LZ, P, 240, black);
  ok("Zap To: on a strike's first frame the leader has not landed", Y(ol, at(384, 135)) < 0.5 * Y(o, at(384, 135)), `end at the first frame ${Y(ol, at(384, 135)).toFixed(2)}, the next ${Y(o, at(384, 135)).toFixed(2)}`); }
{ const P = { lzMode: 2, lzX0: 50, lzY0: 50, lzSize: 30, lzCount: 6, lzFlick: 0, lzGlow: 0 };
  const o = run(LZ, P, 240, black), R = (0.08 + 0.0062 * 30) * H, cx = 240, cy = 135;
  let ring1 = 0, ring2 = 0, far = 0;
  for (let a = 0; a < 720; a++) { const t = a / 720 * 2 * Math.PI; const p = r => Math.max(0, Math.min(W * H - 1, at(Math.round(cx + r * Math.cos(t)), Math.round(cy + r * Math.sin(t)))));
    ring1 = Math.max(ring1, Y(o, p(0.3 * R))); ring2 = Math.max(ring2, Y(o, p(0.85 * R))); far = Math.max(far, Y(o, p(1.6 * R))); }
  ok("Zap From: arcs out of Start, fainter toward the reach, nothing past it", ring1 > 0.8 && ring2 < ring1 && far < 0.15, `at 0.3 reach ${ring1.toFixed(2)}, 0.85 ${ring2.toFixed(2)}, 1.6 ${far.toFixed(3)}`); }

{ const P = { lzMode: 3, lzX0: 50, lzY0: 50, lzAngle: 0, lzEvery: 4, lzLife: 3 };
  const fr = [240, 241, 242, 243].map(f => run(LZ, P, f, grey)), S = (0.03 + 0.0012 * 50) * H;
  const sum = o => { let m = 0; for (let i = 0; i < o.g.length; i++) m += Y(o, i) - 0.5; return m; };
  const e = fr.map(sum);
  let d3 = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < grey.n; i++) if (fr[3][k][i] !== grey[k][i]) d3++;
  ok("Muzzle Flash: fires on the Interval, brightest on its first frame, fading over Life, then exactly the picture", e[0] > 2 * e[1] && e[1] > 1.5 * e[2] && e[2] > 0 && d3 === 0, `light ${e.map(v => v.toFixed(0)).join(", ")}; frame 243 differs at ${d3}`);
  const o = fr[0], fwd = Y(o, at(Math.round(240 + 0.7 * S), 135)), back = Y(o, at(Math.round(240 - 0.7 * S), 135));
  ok("Muzzle Flash: the flame runs along Angle (forward hotter than behind)", fwd > back + 0.1, `forward ${fwd.toFixed(3)}, behind ${back.toFixed(3)}`);
  const ob = run(LZ, P, 240, black); let mxb = 0; for (let y = 0; y < H; y++) for (let x = 0; x < 40; x++) mxb = Math.max(mxb, Y(ob, at(x, y)));
  ok("Muzzle Flash: its light falls on the scene, black far from it stays black", Y(o, at(240, 135 + Math.round(2 * S))) > 0.52 && mxb < 0.02, `grey 2 sizes below ${Y(o, at(240, 135 + Math.round(2 * S))).toFixed(3)}, far edge on black ${mxb.toFixed(4)}`);
  const a = run(LZ, { ...P, lzEvery: 0 }, 241, grey), b = run(LZ, { ...P, lzEvery: 0 }, 299, grey); let hd = 0; for (let i = 0; i < a.g.length; i++) if (a.g[i] !== b.g[i]) hd++;
  ok("Muzzle Flash: Interval 0 holds one first frame", hd === 0 && sum(a) > 0.9 * e[0], `differ ${hd}, light ${sum(a).toFixed(0)}`); }

for (const [file, key, modes] of [[SL, "slMode", 3], [LZ, "lzMode", 4]]) {
  const { sliders } = compile(file, {}, { frame: 1 }); let bad = 0; const sm = image(96, 54, () => [rnd(), rnd(), rnd()]);
  for (let k = 0; k < 30; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd(); P[key] = k % modes;
    const o = run(file, P, Math.floor(rnd() * 999), sm); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok(`${file.split("/").pop()}: range over 30 slider sets`, bad === 0, `bad ${bad}`);
}
console.log(fails ? `${fails} of ${count} FAILED` : `all ${count} pass`);
process.exit(fails ? 1 : 0);
