import { compile } from "../../tests/cpu/dctl.mjs";

const F = "build/Develop Screen.dctl", E = "build/Develop Emboss.dctl";
let s = 41;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function image(W, H, fill) {
  const n = W * H, A = { W, H, n, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let i = 0; i < n; i++) { const c = fill(i, i % W, (i / W) | 0); A.r[i] = c[0]; A.g[i] = c[1]; A.b[i] = c[2]; }
  return A;
}
function run(P, frame, A, file = F) {
  const T = compile(file, P, { frame }).transform;
  const o = { W: A.W, H: A.H, n: A.n, r: new Float32Array(A.n), g: new Float32Array(A.n), b: new Float32Array(A.n) };
  const R = { d: A.r, w: A.W }, G = { d: A.g, w: A.W }, Bt = { d: A.b, w: A.W };
  for (let y = 0; y < A.H; y++) for (let x = 0; x < A.W; x++) { const c = T(A.W, A.H, x, y, R, G, Bt), i = y * A.W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z; }
  return o;
}
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const NAMES = ["JPEG Damage", "Digital Damage", "TV Damage", "Night Vision", "X-Ray", "LED Sign", "Misalignment", "Video Glitch"];
const Y = (o, i) => 0.2126 * o.r[i] + 0.7152 * o.g[i] + 0.0722 * o.b[i];
const meanOf = (o, fn, W, x0, y0, x1, y1) => { let m = 0, n = 0; for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) { m += fn(o, y * W + x); n++; } return m / n; };
const diff = (a, b, n, t) => { let c = 0; for (let i = 0; i < n; i++) if (Math.abs(a.g[i] - b.g[i]) > t || Math.abs(a.r[i] - b.r[i]) > t) c++; return c; };
const maxd = (a, b, n) => { let m = 0; for (let i = 0; i < n; i++) m = Math.max(m, Math.abs(a.r[i] - b.r[i]), Math.abs(a.g[i] - b.g[i]), Math.abs(a.b[i] - b.b[i])); return m; };
const A = image(192, 108, (i, x, y) => { if (Math.hypot(x - 50, y - 30) < 2) return [1, 1, 1]; const v = 0.3 + 0.25 * Math.sin(x / 9) * Math.cos(y / 7) + (x > 120 ? 0.2 : 0) + 0.05 * rnd(); return [Math.min(1, v * 1.1), Math.min(1, v), Math.min(1, 0.7 * v + 0.1)]; });

{ const all = compile(F, {}, { frame: 1 }).sliders;
  for (let m = 0; m < 8; m++) {
    const P = { scAmount: 0 }; for (const [nm, v] of Object.entries(all)) if (nm !== "scAmount") P[nm] = v.hi; P.scMode = m; P.scShape = m === 3 ? 1 : 0;
    const o = run(P, 10, A); let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < A.n; i++) if (o[k][i] !== A[k][i]) d++;
    ok(`${NAMES[m]}: off is identity`, d === 0, `differ ${d}`);
  } }
for (let m = 0; m < 8; m++) {
  const P = { scMode: m, scRate: 100, scStrength: 80 };
  let rep = 0, mov = 0;
  for (const f of [236, 33]) { const a1 = run(P, f, A), a2 = run(P, f, A), b1 = run(P, f + 1, A); rep += diff(a1, a2, A.n, 0); mov = Math.max(mov, diff(a1, b1, A.n, 0.06)); }
  let still = "";
  let pass = rep === 0 && mov > A.n * (m === 5 ? 0.004 : 0.01);
  if ([0, 4, 5, 6].includes(m)) {
    const z1 = run({ scMode: m, scRate: 0, scDither: 0 }, 236, A), z2 = run({ scMode: m, scRate: 0, scDither: 0 }, 237, A), md = maxd(z1, z2, A.n);
    still = `, at Rate 0 frame to frame at most ${md.toFixed(3)}`;
    pass = pass && md < 0.07;
  }
  ok(`${NAMES[m]}: repeats, moves by frame${[0, 4, 5, 6].includes(m) ? ", Rate 0 holds" : ""}`, pass, `repeat ${rep}, moved ${mov}${still}`);
}

{ const W = 96, H = 64, P = { scMode: 0, scRate: 0, scDither: 0, scSize: 0, scStrength: 70, scColour: 50 };
  const J = image(W, H, (i, x, y) => { const v = (x > 37 ? 0.75 : 0.2) + 0.15 * Math.sin(y / 5) + 0.05 * rnd(); return [Math.min(1, v), 0.6 * v + 0.2 * (y / H), 0.3 + 0.4 * (x / W)]; });
  const o = run(P, 236, J);
  const B = (n, k) => 0.5 * (k === 0 ? Math.SQRT1_2 : 1) * Math.cos((2 * n + 1) * k * Math.PI / 16);
  const QY = [16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92, 49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99];
  const QC = [17, 18, 24, 47, 99, 99, 99, 99, 18, 21, 26, 66, 99, 99, 99, 99, 24, 26, 56, 99, 99, 99, 99, 99, 47, 66, 99, 99, 99, 99, 99, 99].concat(Array(32).fill(99));
  const Q = 2 + 93 * Math.pow(0.3, 1.5), S = Q < 50 ? 5000 / Q : 200 - 2 * Q, qs = S / 100;
  const ch = (img, x, y) => { const cx = Math.min(W - 1, x), cy = Math.min(H - 1, Math.max(0, y)), i = cy * W + Math.max(0, cx); return [img.r[i], img.g[i], img.b[i]]; };
  const code = (get, tab, q) => { // 8 x 8 samples get(x, y) -> decoded 8 x 8
    const F = []; for (let v = 0; v < 8; v++) for (let u = 0; u < 8; u++) { let a = 0; for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) a += get(x, y) * B(x, u) * B(y, v); const qq = Math.max(1, tab[v * 8 + u] * q); F.push(Math.round(a / qq) * qq); }
    return (x, y) => { let a = 0; for (let v = 0; v < 8; v++) for (let u = 0; u < 8; u++) a += F[v * 8 + u] * B(x, u) * B(y, v); return a; };
  };
  let near = 0, tot = 0, blocky = 0, cconst = 0, ccount = 0;
  for (let my = 0; my < H; my += 16) for (let mx = 0; mx < W; mx += 16) {
    const yb = []; for (let by = 0; by < 2; by++) for (let bx = 0; bx < 2; bx++) yb.push(code((x, y) => { const c = ch(J, mx + bx * 8 + x, my + by * 8 + y); return 255 * (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) - 128; }, QY, qs));
    const cs = (x, y) => { let r = 0, g = 0, b = 0; for (const [dx, dy] of [[0, 0], [1, 0], [0, 1], [1, 1]]) { const c = ch(J, mx + 2 * x + dx, my + 2 * y + dy); r += c[0] / 4; g += c[1] / 4; b += c[2] / 4; } return [255 * (-0.168736 * r - 0.331264 * g + 0.5 * b), 255 * (0.5 * r - 0.418688 * g - 0.081312 * b)]; };
    const cb = code((x, y) => cs(x, y)[0], QC, qs), cr = code((x, y) => cs(x, y)[1], QC, qs);
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
      const px = mx + x, py = my + y; if (px >= W || py >= H) continue;
      const Yv = yb[(y >> 3) * 2 + (x >> 3)](x & 7, y & 7) + 128, Cb = cb(x >> 1, y >> 1), Cr = cr(x >> 1, y >> 1);
      const ref = [Yv + 1.402 * Cr, Yv - 0.344136 * Cb - 0.714136 * Cr, Yv + 1.772 * Cb].map(v => Math.min(1, Math.max(0, v / 255)));
      const i = py * W + px; tot++;
      if (Math.abs(o.r[i] - ref[0]) < 0.03 && Math.abs(o.g[i] - ref[1]) < 0.03 && Math.abs(o.b[i] - ref[2]) < 0.03) near++;
    }
  }
  const cbo = i => -0.168736 * o.r[i] - 0.331264 * o.g[i] + 0.5 * o.b[i];
  for (let y = 0; y < H; y += 2) for (let x = 0; x < W; x += 2) { const i = y * W + x, a = cbo(i); let same = true; for (const j of [i + 1, i + W, i + W + 1]) if (Math.abs(cbo(j) - a) > 1e-4 && o.b[j] < 1 && o.b[j] > 0) same = false; ccount++; if (same) cconst++; }
  for (let i = 0; i < W * H; i++) if (Math.abs(o.g[i] - J.g[i]) > 0.03) blocky++;
  ok("JPEG Damage: decodes as a reference JPEG codec does, colour at half resolution", near > 0.95 * tot && cconst > 0.97 * ccount && blocky > 0.08 * tot,
     `within 0.03 of the reference ${near}/${tot}, Cb constant over 2 x 2 in ${cconst}/${ccount}, changed from the input ${blocky}`); }
{ const o0 = run({ scMode: 0, scRate: 0, scDither: 0 }, 233, A), o1 = run({ scMode: 0, scRate: 100, scDither: 0 }, 233, A);
  let rows = 0; for (let y = 0; y < A.H; y++) { let c = 0; for (let x = 0; x < A.W; x++) { const i = y * A.W + x; if (Math.abs(o0.b[i] - o1.b[i]) + Math.abs(o0.r[i] - o1.r[i]) > 0.06) c++; } if (c > A.W * 0.3) rows++; }
  ok("JPEG Damage: bit errors cast whole runs of rows", rows >= 8, `rows mostly cast ${rows} of ${A.H}`); }

{ const W = 320, H = 180, V = image(W, H, (i, x, y) => { const v = 0.15 + 0.7 * y / H; return [v, 0.5 + 0.3 * Math.sin(x / 6), 1 - v]; });
  let best = 0;
  for (const f of [236, 250, 270, 290]) { const o = run({ scMode: 1, scRate: 100, scStrength: 100, scDither: 0 }, f, V); let sm = 0;
    for (let y = 1; y < H - 1; y++) for (let x = 0; x < W; x++) { const i = y * W + x; if (Math.abs(o.b[i] - o.b[i - W]) < 0.003 && Math.abs(o.b[i] - o.b[i + W]) < 0.003 && Math.abs(V.b[i] - V.b[i - W]) > 0.003) sm++; } best = Math.max(best, sm); }
  const z = run({ scMode: 1, scRate: 0, scDither: 0 }, 236, V), md = maxd(z, V, V.n);
  ok("Digital Damage: lost blocks smear down from the last good row; Rate 0 leaves the picture but for grain", best > 0.03 * W * H && md < 0.07, `smeared pixels ${best}, Rate 0 most change ${md.toFixed(3)}`); }

{ const W = 320, H = 90, bar = image(W, H, (i, x) => (x >= 60 && x < 64 ? [0.9, 0.9, 0.9] : [0.1, 0.1, 0.1]));
  const o = run({ scMode: 2, scStrength: 0, scRate: 0, scColour: 0, scSize: 50, scDither: 0 }, 236, bar);
  const gd = Math.round((0.008 + 0.05 * 0.5) * W) + 61;
  const at = x => meanOf(o, Y, W, x, 20, x + 2, 70), bg = at(150);
  ok("TV Damage: a ghost of a bright bar sits a delay to its right", at(gd) > bg + 0.03 && at(gd - 5) < at(gd), `at the delay ${at(gd).toFixed(3)}, before it ${at(gd - 5).toFixed(3)}, background ${bg.toFixed(3)}`);
  const C = image(240, 135, (i, x) => (x < 120 ? [0.8, 0.2, 0.2] : [0.2, 0.3, 0.8]));
  const sat = o2 => { let m = 0; for (let i = 0; i < C.n; i++) m += Math.max(o2.r[i], o2.g[i], o2.b[i]) - Math.min(o2.r[i], o2.g[i], o2.b[i]); return m / C.n; };
  const strong = run({ scMode: 2, scStrength: 0, scRate: 0, scColour: 100, scDither: 0 }, 236, C), weak = run({ scMode: 2, scStrength: 100, scRate: 0, scColour: 100, scDither: 0 }, 236, C);
  ok("TV Damage: a weak signal loses its colour", sat(weak) < 0.6 * sat(strong), `colour spread strong signal ${sat(strong).toFixed(3)}, weak ${sat(weak).toFixed(3)}`); }

{ const D = image(240, 135, (i, x, y) => [0.08 + 0.1 * Math.sin(x / 11) ** 2, 0.05, 0.12 + 0.05 * (y / 135)]);
  const o = run({ scMode: 3 }, 236, D), o1 = run({ scMode: 3, scShape: 1 }, 236, D);
  const mr = meanOf(o, (a, i) => a.r[i], 240, 60, 30, 180, 105), mg = meanOf(o, (a, i) => a.g[i], 240, 60, 30, 180, 105), mb = meanOf(o, (a, i) => a.b[i], 240, 60, 30, 180, 105);
  const inY = meanOf(D, Y, 240, 60, 30, 180, 105), outY = meanOf(o, Y, 240, 60, 30, 180, 105), corner = meanOf(o1, Y, 240, 0, 0, 12, 12);
  ok("Night Vision: the dark scene amplified, green, black outside the eyepiece", outY > 2 * inY && mg > 1.5 * mr && mg > 1.5 * mb && corner < 0.02, `luma in ${inY.toFixed(3)} out ${outY.toFixed(3)}, r g b ${mr.toFixed(3)} ${mg.toFixed(3)} ${mb.toFixed(3)}, corner ${corner.toFixed(3)}`); }

{ const R = image(240, 60, (i, x) => [x / 239, x / 239, x / 239]);
  const neg = run({ scMode: 4, scRate: 0, scDither: 0 }, 236, R), pos = run({ scMode: 4, scRate: 0, scDither: 0, scShape: 1 }, 236, R);
  const col = (o, x) => meanOf(o, Y, 240, x, 10, x + 8, 50);
  let mono = true; for (let x = 24; x < 208; x += 16) if (!(col(neg, x) > col(neg, x + 16) - 0.004 && col(pos, x) < col(pos, x + 16) + 0.004)) mono = false;
  const blue = meanOf(neg, (a, i) => a.b[i] - a.r[i], 240, 20, 10, 220, 50);
  ok("X-Ray: inverted density (and upright at Shape 1), on a blue base", mono && col(neg, 20) - col(neg, 210) > 0.5 && col(pos, 210) - col(pos, 20) > 0.5 && blue > 0.02,
     `negative ${col(neg, 20).toFixed(2)} to ${col(neg, 210).toFixed(2)}, upright ${col(pos, 20).toFixed(2)} to ${col(pos, 210).toFixed(2)}, blue over red ${blue.toFixed(3)}`); }

{ const W = 240, H = 1080, red = image(W, H, () => [0.7, 0.15, 0.1]);
  const P = { scMode: 5, scRate: 0, scDither: 0, scSize: 50 }, o = run(P, 236, red), pitch = 6 + 34 * 0.5;
  let cen = 0, cor = 0, rr = 0, gg = 0, n = 0;
  for (let j = -3; j <= 3; j++) for (let i = -3; i <= 3; i++) {
    const cx = Math.round((i + 0.5) * pitch + W / 2 - 0.5), cy = Math.round((j + 0.5) * pitch + H / 2 - 0.5);
    const ki = cy * W + cx, kc = Math.round(cy - pitch / 2) * W + Math.round(cx - pitch / 2);
    cen += Y(o, ki); cor += Y(o, kc); rr += o.r[ki]; gg += o.g[ki]; n++;
  }
  ok("LED Sign: round emitters lit at the centre, dark gaps, the cell's colour", cen / n > 0.3 && cor / n < 0.12 && rr > 2.5 * gg, `centre ${(cen / n).toFixed(3)}, corner ${(cor / n).toFixed(3)}, red ${(rr / n).toFixed(3)} green ${(gg / n).toFixed(3)}`); }

{ const W = 480, H = 270, dot = (cx, cy) => image(W, H, (i, x, y) => (Math.hypot(x - cx, y - cy) < 2.5 ? [1, 1, 1] : [0, 0, 0]));
  const sep = (cx, cy) => { const o = run({ scMode: 6, scRate: 0, scDither: 0, scColour: 0, scStrength: 100 }, 236, dot(cx, cy));
    const cen = k => { let sx = 0, sy = 0, sw = 0; for (let y = cy - 30; y < cy + 30; y++) for (let x = cx - 30; x < cx + 30; x++) { if (x < 0 || y < 0 || x >= W || y >= H) continue; const v = o[k][y * W + x]; if (v > 0.05) { sx += v * x; sy += v * y; sw += v; } } return [sx / sw, sy / sw]; };
    const r = cen("r"), g = cen("g"), b = cen("b"); return [Math.hypot(r[0] - g[0], r[1] - g[1]), Math.hypot(b[0] - g[0], b[1] - g[1])]; };
  const c = sep(240, 135), k = sep(440, 30);
  ok("Misalignment: red and blue off the green, more toward the corner", c[0] > 0.5 && c[1] > 0.5 && k[0] > c[0] + 0.5 && k[1] > c[1] + 0.5, `centre red ${c[0].toFixed(2)} blue ${c[1].toFixed(2)} px, corner red ${k[0].toFixed(2)} blue ${k[1].toFixed(2)} px`); }

{ let drop = 0, calm = 1, sparks = 0;
  for (let f = 20; f < 60; f++) { const o = run({ scMode: 7, scDither: 0, scRate: 100 }, f, A), c = diff(o, A, A.n, 0.06) / A.n; drop = Math.max(drop, c); calm = Math.min(calm, c); }
  const sp = run({ scMode: 7, scDither: 0, scRate: 0, scStrength: 100 }, 236, A);
  for (let i = 0; i < A.n; i++) if (Math.abs(sp.g[i] - A.g[i]) > 0.06) sparks++;
  ok("Video Glitch: drops some frames, sparkles only between", drop > 0.05 && calm < 0.01 && sparks > 0 && sparks < 0.01 * A.n, `worst frame ${(100 * drop).toFixed(1)}%, calmest ${(100 * calm).toFixed(2)}%, sparkles at Rate 0 ${sparks}`); }

{ const { sliders } = compile(F, {}, { frame: 1 }); let bad = 0; const sm = image(64, 48, () => [rnd(), rnd(), rnd()]);
  for (let k = 0; k < 30; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd(); P.scMode = k % 8;
    const o = run(P, Math.floor(rnd() * 999), sm); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok("Screen: range over 30 slider sets", bad === 0, `bad ${bad}`); }

{ const P = { emAmount: 0 }; for (const [nm, v] of Object.entries(compile(E, {}, { frame: 1 }).sliders)) if (nm !== "emAmount") P[nm] = v.hi;
  for (const st of [0, 1]) { const o = run({ ...P, emStyle: st }, 10, A, E); let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < A.n; i++) if (o[k][i] !== A[k][i]) d++;
    ok(`Emboss ${st ? "Glass" : "Shiny"}: off is identity`, d === 0, `differ ${d}`); } }
{ const flat = image(96, 54, () => [0.55, 0.4, 0.3]);
  for (const st of [0, 1]) { const o = run({ emStyle: st }, 1, flat, E); ok(`Emboss ${st ? "Glass" : "Shiny"}: a flat picture stays itself`, maxd(o, flat, flat.n) < 0.012, `most change ${maxd(o, flat, flat.n).toFixed(4)}`); } }
{ const W = 240, H = 1080, disc = image(W, H, (i, x, y) => { const v = 0.35 + 0.3 * Math.exp(-((x - 120) ** 2 + (y - 540) ** 2) / 900); return [v, v, v]; });
  const o = run({ emStyle: 0, emAngle: 135 }, 1, disc, E), iv = run({ emStyle: 0, emAngle: 135, emInvert: 1 }, 1, disc, E);
  const tl = o2 => meanOf(o2, Y, W, 90, 510, 104, 524), br = o2 => meanOf(o2, Y, W, 136, 556, 150, 570);
  let mx = 0, mi = 0; for (let i = 0; i < disc.n; i++) { mx = Math.max(mx, Y(o, i)); mi = Math.max(mi, Y(disc, i)); }
  ok("Emboss Shiny: lit from the top left, a highlight; Invert presses it in", tl(o) > br(o) + 0.08 && mx > mi + 0.05 && br(iv) > tl(iv) + 0.08,
     `top left ${tl(o).toFixed(3)}, bottom right ${br(o).toFixed(3)}, brightest ${mx.toFixed(3)} (in ${mi.toFixed(3)}), inverted ${tl(iv).toFixed(3)} / ${br(iv).toFixed(3)}`); }
{ const W = 240, H = 1080, R = image(W, H, (i, x) => { const v = 0.2 + 0.6 * Math.min(1, Math.max(0, (x - 70) / 100)); return [v, v, v]; });
  const o = run({ emStyle: 1, emShine: 0, emDetail: 0 }, 1, R, E), fl = run({ emStyle: 1, emShine: 0, emDetail: 0 }, 1, image(W, H, () => [0.5, 0.5, 0.5]), E);
  const oy = meanOf(o, Y, W, 100, 500, 140, 580), iy = meanOf(R, Y, W, 100, 500, 140, 580), dr = meanOf(o, (a, i) => a.r[i] - a.b[i], W, 100, 500, 140, 580);
  const d0 = meanOf(fl, (a, i) => a.r[i] - a.b[i], W, 100, 500, 140, 580);
  ok("Emboss Glass: the view bent along the slope, the colours parted", iy - oy > 0.02 && dr > d0 + 0.002, `luma in ${iy.toFixed(3)} out ${oy.toFixed(3)}, red over blue ${dr.toFixed(4)} (flat glass ${d0.toFixed(4)})`); }
{ const { sliders } = compile(E, {}, { frame: 1 }); let bad = 0; const sm = image(64, 48, () => [rnd(), rnd(), rnd()]);
  for (let k = 0; k < 30; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd(); P.emStyle = k % 2;
    const o = run(P, 1, sm, E); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok("Emboss: range over 30 slider sets", bad === 0, `bad ${bad}`); }
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
