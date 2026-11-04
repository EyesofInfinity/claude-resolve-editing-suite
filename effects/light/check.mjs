import { compile, runTransition } from "../../tests/cpu/dctl.mjs";

const B = "build/";
const W = 240, H = 135;
function chart(seed) {
  const n = W * H, img = { w: W, h: H, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  let s = seed;
  const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = y * W + x, ramp = x / (W - 1);
    img.r[i] = y < 20 ? ramp : rnd(); img.g[i] = y < 20 ? ramp : rnd() * 0.8; img.b[i] = y < 20 ? ramp : rnd() * 0.6;
  }
  return img;
}
function runT(file, params, env, img) {
  const T = compile(B + file, params, env).transform;
  const o = { r: new Float32Array(W * H), g: new Float32Array(W * H), b: new Float32Array(W * H) };
  const R = { d: img.r, w: W }, G = { d: img.g, w: W }, Bt = { d: img.b, w: W };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const c = T(W, H, x, y, R, G, Bt), i = y * W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z;
  }
  return o;
}
const q = v => Math.round(Math.max(0, Math.min(1, v)) * 1023);
function diffCount(a, b) {
  let n = 0, mx = 0;
  for (const k of ["r", "g", "b"]) for (let i = 0; i < a[k].length; i++) {
    const d = Math.abs(q(a[k][i]) - q(b[k][i])); if (d) n++; if (d > mx) mx = d;
  }
  return { n, mx };
}
function badRange(o) {
  for (const k of ["r", "g", "b"]) for (const v of o[k]) if (!Number.isFinite(v) || v < 0 || v > 1) return true;
  return false;
}
function corr(a, b, c) {           // correlation of the change two frames make against the clean picture
  let sa = 0, sb = 0, saa = 0, sbb = 0, sab = 0, n = a.r.length;
  for (let i = 0; i < n; i++) { const x = a.g[i] - c.g[i], y = b.g[i] - c.g[i]; sa += x; sb += y; saa += x * x; sbb += y * y; sab += x * y; }
  const ma = sa / n, mb = sb / n;
  return (sab / n - ma * mb) / Math.sqrt((saa / n - ma * ma) * (sbb / n - mb * mb) + 1e-12);
}
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };

const A = chart(1), Bimg = chart(2);
let d = diffCount(runT("Develop Leak.dctl", { lkAmount: 0 }, { frame: 10 }, A), A);
ok("leak off is identity", d.n === 0, JSON.stringify(d));
d = diffCount(runT("Develop Burn.dctl", { bnAmount: 0 }, { frame: 10 }, A), A);
ok("burn off is identity", d.n === 0, JSON.stringify(d));

const lk = runT("Develop Leak.dctl", { lkEdge: 180, lkWidth: 20, lkFog: 0 }, { frame: 10 }, A);
let far = 0, near = 0;
for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
  const i = y * W + x, dd = Math.abs(lk.g[i] - A.g[i]);
  if (x > W * 0.75) far = Math.max(far, dd); if (x < W * 0.1) near += dd / (W * 0.1 * H);
}
ok("leak stays at its edge", far < 2 / 1023 && near > 0.02, `right quarter max ${(far * 1023).toFixed(2)}/1023, left tenth mean ${(near * 1023).toFixed(1)}/1023`);

const grey = chart(3); grey.r.fill(0.3); grey.g.fill(0.3); grey.b.fill(0.3);
const nz = { bnGrain: 0, bnDust: 0 };
const b1 = runT("Develop Burn.dctl", nz, { frame: 236 }, grey), b1r = runT("Develop Burn.dctl", nz, { frame: 236 }, grey);
ok("burn repeat identical", diffCount(b1, b1r).n === 0, "");
let c100 = 0;                                    // mean |corr| over six neighbouring pairs: one pair can be chance
for (let f = 236; f < 242; f++)
  c100 += Math.abs(corr(runT("Develop Burn.dctl", nz, { frame: f }, grey), runT("Develop Burn.dctl", nz, { frame: f + 1 }, grey), grey)) / 6;
const s1 = runT("Develop Burn.dctl", { ...nz, bnSpeed: 0 }, { frame: 236 }, grey), s2 = runT("Develop Burn.dctl", { ...nz, bnSpeed: 0 }, { frame: 237 }, grey);
const c0 = corr(s1, s2, grey);
ok("burn speed", c100 < 0.5 && c0 > 0.9, `corr speed 100 ${c100.toFixed(3)}, speed 0 ${c0.toFixed(3)}`);

for (const st of [0, 1, 2, 3]) {
  const o1 = runTransition(B + "Develop Light Dissolve.dctl", { ldStyle: st }, { progress: 1 }, A, Bimg);
  ok(`style ${st} ends on the incoming shot`, diffCount(o1, Bimg).n === 0, JSON.stringify(diffCount(o1, Bimg)));
  if (st) {
    const o0 = runTransition(B + "Develop Light Dissolve.dctl", { ldStyle: st }, { progress: 0 }, A, Bimg);
    ok(`style ${st} starts on the outgoing shot`, diffCount(o0, A).n === 0, JSON.stringify(diffCount(o0, A)));
  }
}

for (const hard of [0, 40, 90]) {
  const o1 = runTransition(B + "Develop Light Dissolve.dctl", { ldStyle: 0, ldHard: hard }, { progress: 1 }, A, Bimg);
  ok(`flash burn at Hard ${hard} ends on the incoming shot`, diffCount(o1, Bimg).n === 0, JSON.stringify(diffCount(o1, Bimg)));
}

let s = 7;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
const files = { "Develop Leak.dctl": null, "Develop Burn.dctl": null, "Develop Light Dissolve.dctl": null };
for (const f of Object.keys(files)) {
  const { sliders } = compile(B + f, {}, { frame: 1 });
  let bad = 0;
  for (let k = 0; k < 40; k++) {
    const P = {};
    for (const [n, v] of Object.entries(sliders)) P[n] = v.lo + (v.hi - v.lo) * rnd();
    for (const n of ["ldStyle", "ldPalette", "lkPalette", "bnPalette"]) if (n in P) P[n] = Math.round(P[n]);
    const o = f.includes("Dissolve") ? runTransition(B + f, P, { progress: rnd(), frame: 5 }, A, Bimg) : runT(f, P, { frame: Math.floor(rnd() * 999) }, A);
    if (badRange(o)) bad++;
  }
  ok(`${f} range over 40 slider sets`, bad === 0, `bad ${bad}`);
}
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
