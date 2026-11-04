import { compile, run } from "../../tests/cpu/dctl.mjs";

const GM = "build/Develop Grain Match.dctl";
const W = 1920, H = 1080, REG = { x0: 800, y0: 400, x1: 1056, y1: 656 }, N = 256 * 256;
let s = 33;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
const img = fn => {
  const n = W * H, o = { w: W, h: H, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const c = fn(x, y), i = y * W + x; o.r[i] = c[0]; o.g[i] = c[1]; o.b[i] = c[2]; }
  return o;
};
const flat = v => img(() => [v, v, v]);
const gm = (P, im, frame = 1, reg = REG) => run(compile(GM, P, { frame }).transform, im, reg);
let fails = 0, count = 0;
const ok = (name, pass, info) => { count++; console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const KR = 0.2126, KB = 0.0722, KG = 1 - KR - KB;
const ycc = (o, v) => {
  const Y = new Float64Array(N), Cb = new Float64Array(N), Cr = new Float64Array(N);
  for (let i = 0; i < N; i++) {
    const r = (o.r[i] - v) * 255, g = (o.g[i] - v) * 255, b = (o.b[i] - v) * 255, y = KR * r + KG * g + KB * b;
    Y[i] = y; Cb[i] = (b - y) / (2 * (1 - KB)); Cr[i] = (r - y) / (2 * (1 - KR));
  }
  return { Y, Cb, Cr };
};
const mean = a => { let m = 0; for (const v of a) m += v; return m / a.length; };
const sd = a => { const m = mean(a); let q = 0; for (const v of a) q += (v - m) ** 2; return Math.sqrt(q / a.length); };
const corr = (a, b) => { const ma = mean(a), mb = mean(b); let p = 0, qa = 0, qb = 0; for (let i = 0; i < a.length; i++) { p += (a[i] - ma) * (b[i] - mb); qa += (a[i] - ma) ** 2; qb += (b[i] - mb) ** 2; } return p / Math.sqrt(qa * qb); };
const lag1 = a => { const x = [], y = []; for (let r = 0; r < 256; r++) for (let c = 0; c < 255; c++) { x.push(a[r * 256 + c]); y.push(a[r * 256 + c + 1]); }
  for (let r = 0; r < 255; r++) for (let c = 0; c < 256; c++) { x.push(a[r * 256 + c]); y.push(a[(r + 1) * 256 + c]); } return corr(x, y); };
const discRho = s => { if (s < 0.25) return 0; let a = 0, b = 0; for (let k = -12; k <= 12; k++) { const g0 = Math.exp(-k * k / (2 * s * s)), g1 = Math.exp(-(k + 1) * (k + 1) / (2 * s * s)); a += g0 * g1; b += g0 * g0; } return a / b; };
const diffN = (o, im) => { let d = 0; for (let y = REG.y0; y < REG.y1; y++) for (let x = REG.x0; x < REG.x1; x++) { const i = (y - REG.y0) * 256 + (x - REG.x0), j = y * W + x; if (o.r[i] !== im.r[j] || o.g[i] !== im.g[j] || o.b[i] !== im.b[j]) d++; } return d; };

const { sliders } = compile(GM, {}, { frame: 1 });
const grey = flat(0.45);
const tex = img((x, y) => { const v = 0.4 + 0.25 * Math.sin(x / 5) * Math.cos(y / 7) + 0.1 * rnd(); return [v, 0.9 * v, 0.8 * v]; });
const MONO = { gmRefBS: 0, gmRefBM: 0, gmRefBH: 0, gmRefRS: 0, gmRefRM: 0, gmRefRH: 0 };

{
  const P = { gmAmount: 0 }; for (const [nm, v] of Object.entries(sliders)) if (nm !== "gmAmount" && nm !== "gmView") P[nm] = v.hi;
  ok("Amount 0 is identity (every other slider at its top)", diffN(gm(P, tex), tex) === 0, "");
  const same = { gmClYS: 3, gmClYM: 2.5, gmClYH: 1.8, gmClBS: 1.2, gmClBM: 0.9, gmClBH: 0.6, gmClRS: 1.2, gmClRM: 0.9, gmClRH: 0.6 };
  ok("a clip as grainy as the reference is left exactly", diffN(gm(same, tex), tex) === 0, "");
  const more = { gmClYS: 9, gmClYM: 9, gmClYH: 9, gmClBS: 5, gmClBM: 5, gmClBH: 5, gmClRS: 5, gmClRM: 5, gmClRH: 5 };
  ok("a clip grainier than the reference is left exactly", diffN(gm(more, tex), tex) === 0, "");
}
{
  const o = ycc(gm({ ...MONO, gmRefYM: 3, gmRefSz: 0 }, grey), 0.45);
  ok("Ref Grain Mids 3 adds 3 codes of luma grain on mid grey", Math.abs(sd(o.Y) / 3 - 1) < 0.03 && sd(o.Cb) < 1e-6, `luma ${sd(o.Y).toFixed(3)} colour ${sd(o.Cb).toExponential(1)}`);
  ok("the grain has no mean (mid grey stays mid grey)", Math.abs(mean(o.Y)) < 0.05, `mean ${mean(o.Y).toFixed(4)} codes`);
  const d = ycc(gm({ ...MONO, gmRefYM: 3, gmRefSz: 0, gmClYM: 2, gmClSz: 0 }, grey), 0.45);
  ok("only the difference is added: Ref 3 over Clip 2 adds sqrt(5) = 2.236 codes", Math.abs(sd(d.Y) / Math.sqrt(5) - 1) < 0.03, `${sd(d.Y).toFixed(3)}`);
  const dark = 0.15, lite = 0.80;
  const od = ycc(gm({ ...MONO, gmRefYS: 4, gmRefYM: 1, gmRefYH: 1.5, gmRefSz: 0 }, flat(dark)), dark);
  const ol = ycc(gm({ ...MONO, gmRefYS: 4, gmRefYM: 1, gmRefYH: 1.5, gmRefSz: 0 }, flat(lite)), lite);
  ok("band strengths: 4 codes in the shadows, 1.5 in the highlights", Math.abs(sd(od.Y) / 4 - 1) < 0.03 && Math.abs(sd(ol.Y) / 1.5 - 1) < 0.03, `${sd(od.Y).toFixed(3)} ${sd(ol.Y).toFixed(3)}`);
}
{
  const o = ycc(gm({ gmRefYM: 3, gmRefBM: 2.4, gmRefRM: 1.5, gmRefYB: 50, gmRefYR: -30, gmRefBR: 20, gmRefSz: 1, gmRefCSz: 1 }, grey), 0.45);
  ok("Ref Blue Mids 2.4 and Ref Red Mids 1.5 add Cb 2.4 and Cr 1.5 codes", Math.abs(sd(o.Cb) / 2.4 - 1) < 0.04 && Math.abs(sd(o.Cr) / 1.5 - 1) < 0.04, `Cb ${sd(o.Cb).toFixed(3)} Cr ${sd(o.Cr).toFixed(3)}`);
  const pb = { ...MONO, gmRefYS: 0, gmRefYM: 0, gmRefYH: 0, gmRefBS: 2, gmRefRM: 2, gmRefSz: 0, gmRefCSz: 0 };
  const sh = ycc(gm(pb, flat(0.15)), 0.15), md = ycc(gm(pb, flat(0.45)), 0.45);
  ok("colour by band: blue only in the shadows, red only in the mids", Math.abs(sd(sh.Cb) / 2 - 1) < 0.04 && sd(sh.Cr) < 0.01 && Math.abs(sd(md.Cr) / 2 - 1) < 0.04 && sd(md.Cb) < 0.01,
     `shadows Cb ${sd(sh.Cb).toFixed(3)} Cr ${sd(sh.Cr).toFixed(3)}, mids Cb ${sd(md.Cb).toFixed(3)} Cr ${sd(md.Cr).toFixed(3)}`);
  const c1 = corr(o.Y, o.Cb), c2 = corr(o.Y, o.Cr), c3 = corr(o.Cb, o.Cr);
  ok("the links come out: Y-Cb 0.5, Y-Cr -0.3, Cb-Cr 0.2", Math.abs(c1 - 0.5) < 0.04 && Math.abs(c2 + 0.3) < 0.04 && Math.abs(c3 - 0.2) < 0.04, `${c1.toFixed(3)} ${c2.toFixed(3)} ${c3.toFixed(3)}`);
}
for (const [yb, yr, br] of [[-40, -40, 0], [-55, -44, 22], [80, 80, 80], [-90, 90, -90]]) {
  const o = ycc(gm({ gmRefYM: 3, gmClYM: 2.8, gmRefBM: 1.2, gmRefRM: 1.2, gmRefYB: yb, gmRefYR: yr, gmRefBR: br, gmRefSz: 1, gmRefCSz: 1, gmClSz: 1, gmClCSz: 1 }, grey), 0.45);
  const wantY = Math.sqrt(9 - 2.8 * 2.8);
  ok(`links ${yb}/${yr}/${br} over a clip at Y 2.8: strengths Y ${wantY.toFixed(3)}, Cb and Cr 1.2`,
     Math.abs(sd(o.Y) / wantY - 1) < 0.05 && Math.abs(sd(o.Cb) / 1.2 - 1) < 0.05 && Math.abs(sd(o.Cr) / 1.2 - 1) < 0.05,
     `Y ${sd(o.Y).toFixed(3)} Cb ${sd(o.Cb).toFixed(3)} Cr ${sd(o.Cr).toFixed(3)}`);
}
{
  const P = { ...MONO, gmRefYM: 3, gmRefSz: 0, gmSeed: 7, gmHold: 50 };
  const o = ycc(gm(P, grey, 2897), 0.45);
  ok("Seed 7, Hold 50, frame 2897: strength 3 codes", Math.abs(sd(o.Y) / 3 - 1) < 0.04, `${sd(o.Y).toFixed(3)}`);
}
for (const sz of [0, 0.5, 1.0, 2.0, 3.0]) {
  const o = ycc(gm({ ...MONO, gmRefYM: 3, gmRefSz: sz }, grey), 0.45);
  const want = sz <= 1 ? discRho(sz) : Math.exp(-0.25 / (sz * sz)), got = lag1(o.Y);
  ok(`Size ${sz}: lag-1 correlation ${want.toFixed(3)}`, Math.abs(got - want) < 0.03 && Math.abs(sd(o.Y) / 3 - 1) < (sz >= 2 ? 0.1 : 0.04), `got ${got.toFixed(3)}, strength ${sd(o.Y).toFixed(3)}`);
}
{
  const big = { w: 1920, h: 2160, r: new Float32Array(1920 * 2160).fill(0.45), g: new Float32Array(1920 * 2160).fill(0.45), b: new Float32Array(1920 * 2160).fill(0.45) };
  const o = ycc(run(compile(GM, { ...MONO, gmRefYM: 3, gmRefSz: 1.5 }, { frame: 1 }).transform, big, REG), 0.45);
  const want = Math.exp(-0.25 / 9);
  ok("at 2160 lines Size 1.5 draws a 3 px grain", Math.abs(lag1(o.Y) - want) < 0.03, `lag-1 ${lag1(o.Y).toFixed(3)} want ${want.toFixed(3)}`);
}
{
  const clip = gm({ ...MONO, gmRefYM: 1, gmRefSz: 0.5, gmSeed: 7 }, grey);
  const cimg = flat(0.45);
  for (let y = REG.y0; y < REG.y1; y++) for (let x = REG.x0; x < REG.x1; x++) { const i = (y - REG.y0) * 256 + (x - REG.x0), j = y * W + x; cimg.r[j] = clip.r[i]; cimg.g[j] = clip.g[i]; cimg.b[j] = clip.b[i]; }
  const tot = ycc(gm({ ...MONO, gmRefYM: 3, gmRefSz: 1.0, gmClYM: 1, gmClSz: 0.5 }, cimg), 0.45);
  const want = discRho(1.0), got = lag1(tot.Y);
  const plain = ycc(gm({ ...MONO, gmRefYM: 3, gmRefSz: 1.0, gmClYM: 1, gmClSz: 1.0 }, cimg), 0.45);
  ok("Clip grain 1 at 0.5 px plus the match reads as the reference's 3 codes at 1 px", Math.abs(sd(tot.Y) / 3 - 1) < 0.04 && Math.abs(got - want) < 0.03,
     `strength ${sd(tot.Y).toFixed(3)} lag-1 ${got.toFixed(3)} want ${want.toFixed(3)} (uncompensated ${lag1(plain.Y).toFixed(3)})`);
  const c2 = gm({ ...MONO, gmRefYM: 2.5, gmRefSz: 0.0, gmSeed: 8 }, grey);
  const cimg2 = flat(0.45);
  for (let y = REG.y0; y < REG.y1; y++) for (let x = REG.x0; x < REG.x1; x++) { const i = (y - REG.y0) * 256 + (x - REG.x0), j = y * W + x; cimg2.r[j] = c2.r[i]; cimg2.g[j] = c2.g[i]; cimg2.b[j] = c2.b[i]; }
  const add = ycc(gm({ ...MONO, gmRefYM: 3, gmRefSz: 1.0, gmClYM: 2.5, gmClSz: 0.0, gmView: 1 }, cimg2), 0.45);
  ok("an unreachable size stops at twice the reference's (2 px)", Math.abs(lag1(add.Y) - Math.exp(-0.25 / 4)) < 0.03, `added lag-1 ${lag1(add.Y).toFixed(3)} want ${Math.exp(-0.25 / 4).toFixed(3)}`);
}
{
  const P = { ...MONO, gmRefYM: 3, gmRefSz: 1 };
  const a = ycc(gm(P, grey, 1), 0.45).Y, b = ycc(gm(P, grey, 2), 0.45).Y;
  const h = { ...P, gmHold: 100 }, ha = ycc(gm(h, grey, 1), 0.45).Y, hb = ycc(gm(h, grey, 2), 0.45).Y;
  const m = { ...P, gmHold: 50 }, ma = ycc(gm(m, grey, 1), 0.45).Y, mb = ycc(gm(m, grey, 2), 0.45).Y;
  ok("Hold 0: new grain every frame", Math.abs(corr(a, b)) < 0.03, `frame 1 to 2 ${corr(a, b).toFixed(3)}`);
  ok("Hold 100: the grain stays", corr(ha, hb) > 0.999, `${corr(ha, hb).toFixed(4)}`);
  ok("Hold 50: half the variance stays", Math.abs(corr(ma, mb) - 0.5) < 0.04 && Math.abs(sd(ma) / 3 - 1) < 0.04, `${corr(ma, mb).toFixed(3)} strength ${sd(ma).toFixed(3)}`);
  const s1 = ycc(gm({ ...P, gmSeed: 1 }, grey, 1), 0.45).Y;
  ok("Seed changes the grain", Math.abs(corr(a, s1)) < 0.03, `${corr(a, s1).toFixed(3)}`);
}
{
  const P = { gmRefYS: 20, gmRefYM: 20, gmRefYH: 20, gmRefBS: 10, gmRefBM: 10, gmRefBH: 10, gmRefRS: 10, gmRefRM: 10, gmRefRH: 10 };
  const k = gm(P, flat(0)), w = gm(P, flat(1)), sw = gm(P, flat(1.2));
  let bad = 0; for (let i = 0; i < N; i++) { if (k.r[i] !== 0 || k.g[i] !== 0 || k.b[i] !== 0) bad++; if (w.r[i] !== 1 || w.b[i] !== 1) bad++; if (Math.abs(sw.g[i] - 1.2) > 1e-6) bad++; }
  ok("pure black, pure white and superwhite take no grain", bad === 0, `${bad} pixels moved`);
}
{
  const o = gm({ ...MONO, gmRefYM: 3, gmView: 1 }, flat(0.05));
  const y = ycc(o, 0.45).Y;
  ok("View Grain shows the grain over mid grey", Math.abs(mean(y)) < 0.1 && Math.abs(sd(y) / 3 - 1) < 0.05, `mean ${mean(y).toFixed(3)} sd ${sd(y).toFixed(3)}`);
}
{
  let bad = 0;
  for (let k = 0; k < 30; k++) {
    const P = {}; for (const [nm, v] of Object.entries(sliders)) if (nm !== "gmView") P[nm] = v.lo + (v.hi - v.lo) * rnd();
    const o = run(compile(GM, P, { frame: 1 + k }).transform, tex, { x0: 900, y0: 500, x1: 964, y1: 564 });
    for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; }
  }
  ok("range over 30 slider sets", bad === 0, `bad ${bad}`);
}
console.log(`${count - fails} of ${count} pass`);
process.exit(fails ? 1 : 0);
