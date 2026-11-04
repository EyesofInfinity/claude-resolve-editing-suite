import { compile } from "../../tests/cpu/dctl.mjs";

const D = "build/Develop Damage.dctl";
let s = 31;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
function image(W, H, fill) {
  const n = W * H, A = { W, H, n, r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  for (let i = 0; i < n; i++) { const c = fill(i, i % W, (i / W) | 0); A.r[i] = c[0]; A.g[i] = c[1]; A.b[i] = c[2]; }
  return A;
}
function run(P, frame, A) {
  const T = compile(D, P, { frame }).transform;
  const o = { r: new Float32Array(A.n), g: new Float32Array(A.n), b: new Float32Array(A.n) };
  const R = { d: A.r, w: A.W }, G = { d: A.g, w: A.W }, Bt = { d: A.b, w: A.W };
  for (let y = 0; y < A.H; y++) for (let x = 0; x < A.W; x++) { const c = T(A.W, A.H, x, y, R, G, Bt), i = y * A.W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z; }
  return o;
}
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };
const mean = (a) => a.reduce((p, v) => p + v, 0) / a.length;
const W = 480, H = 270;
const A = image(W, H, (i, x, y) => { const v = 0.4 + 0.3 * Math.sin(x / 13) * Math.cos(y / 17) + 0.05 * rnd(); return [v, 0.9 * v, 0.8 * v]; });
const grey = image(W, H, () => [0.5, 0.5, 0.5]);
const dark = image(W, H, () => [0.08, 0.08, 0.1]);
{ const P = { dmAmount: 0 }; for (const [nm, v] of Object.entries(compile(D, {}, { frame: 1 }).sliders)) if (!(nm in P)) P[nm] = v.hi;
  const o = run(P, 10, A); let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < A.n; i++) if (o[k][i] !== A[k][i]) d++;
  ok("off is identity", d === 0, `differ ${d}`); }
const bar0 = image(W, H, (i, x, y) => (x > 120 && x < 360 && y > 128 && y < 143 ? [0.94, 0.93, 0.9] : [0.03, 0.03, 0.04]));
for (let m = 0; m < 6; m++) {
  const S = m === 5 ? bar0 : A;
  const a1 = run({ dmMode: m }, 236, S), a2 = run({ dmMode: m }, 236, S), b1 = run({ dmMode: m }, 241, S);
  let rep = 0, mov = 0; for (let i = 0; i < S.n; i++) { if (a1.g[i] !== a2.g[i]) rep++; if (a1.g[i] !== b1.g[i]) mov++; }
  const moves = m === 0 || m === 4 || m === 5;
  ok(`mode ${m}: repeat identical, ${moves ? "moves" : "holds"}`, rep === 0 && (moves ? mov > 100 : mov === 0), `repeat ${rep}, moved ${mov}`);
}
{ let scr = 0, spk = 0;
  for (let f = 300; f < 348; f++) {
    const o = run({ dmMode: 0, dmStrength: 100, dmAge: 0 }, f, grey); let best = 0, marks = 0;
    for (let x = 0; x < W; x++) { let run_ = 0, top = 0; for (let y = 0; y < H; y++) { const d = Math.abs(o.g[y * W + x] - o.g[y * W + ((x + 6) % W)]); if (d > 0.08) { run_++; top = Math.max(top, run_); } else run_ = 0; } best = Math.max(best, top); }
    for (let i = 0; i < grey.n; i++) if (o.g[i] < 0.2) marks++;
    if (best >= 60) scr++; if (marks > 0) spk++;
  }
  ok("Film Damage: long scratches on many frames", scr >= 12, `${scr} of 48 frames`);
  ok("Film Damage: dark specks on most frames", spk >= 24, `${spk} of 48 frames`); }
{ const ms = [], rb = [];
  for (let f = 100; f < 148; f++) { const o = run({ dmMode: 4, dmStrength: 80 }, f, grey); ms.push(mean(o.g)); rb.push(mean(o.r) / mean(o.b)); }
  const mu = mean(ms), sd = Math.sqrt(mean(ms.map(v => (v - mu) ** 2)));
  let cov = 0; const rbm = mean(rb); for (let i = 0; i < ms.length; i++) cov += (ms[i] - mu) * (rb[i] - rbm);
  ok("Light Flicker: the exposure wanders", sd > 0.02, `sd ${sd.toFixed(4)} of mean ${mu.toFixed(3)}`);
  ok("Light Flicker: warmer as it dims", cov < 0, `cov ${cov.toExponential(2)}`); }
{ const o = run({ dmMode: 2, dmStrength: 100 }, 1, grey); let up = 0, dn = 0, dr = 0, db = 0;
  for (let i = 0; i < grey.n; i++) { if (o.g[i] > 0.5 + 1e-6) up++; if (o.g[i] < 0.48) dn++; dr += 0.5 - o.r[i]; db += 0.5 - o.b[i]; }
  ok("Stains: darken and stain warm, never brighten", up === 0 && dn > 200 && db > 1.5 * dr, `brighter ${up}, stained ${dn}, red loss ${dr.toFixed(1)}, blue loss ${db.toFixed(1)}`); }
{ const o = run({ dmMode: 3, dmStrength: 100 }, 1, dark); let lit = 0, dk = 0;
  for (let i = 0; i < dark.n; i++) { if (o.g[i] > 0.16) lit++; if (o.g[i] < 0.06) dk++; }
  ok("Scratches: lit lines over a dark picture, few gouges", lit > 300 && lit > 2 * dk, `lit ${lit}, gouged ${dk}`); }
{ const z = run({ dmMode: 1, dmStrength: 0 }, 1, A); let d = 0; for (let i = 0; i < A.n; i++) d = Math.max(d, Math.abs(z.g[i] - A.g[i]));
  ok("Grunge: Strength 0 gives the picture back", d < 1e-6, `max ${d.toExponential(1)}`);
  const big = image(960, 540, () => [0.5, 0.5, 0.5]), o = run({ dmMode: 1, dmStrength: 100 }, 1, big); let e = 0, ne = 0, c = 0, nc = 0;
  for (let y = 0; y < 540; y++) for (let x = 0; x < 960; x++) { const v = o.g[y * 960 + x]; if (x < 40 || x >= 920 || y < 25 || y >= 515) { e += v; ne++; } else if (Math.abs(x - 480) < 160 && Math.abs(y - 270) < 90) { c += v; nc++; } }
  ok("Grunge: grime gathers at the edges", e / ne < c / nc - 0.02, `edge ${(e / ne).toFixed(3)}, centre ${(c / nc).toFixed(3)}`); }
{ const bar = image(W, H, (i, x, y) => (x > 120 && x < 360 && y > 128 && y < 143 ? [0.94, 0.93, 0.9] : [0.03, 0.03, 0.04]));
  const flat = run({ dmMode: 5, dmBurn: 60 }, 1, dark); let d = 0; for (let i = 0; i < dark.n; i++) d = Math.max(d, Math.abs(flat.g[i] - dark.g[i]));
  ok("Edge Burn: a picture under the Key is untouched", d < 1e-6, `max ${d.toExponential(1)}`);
  const b0 = run({ dmMode: 5, dmBurn: 0 }, 1, bar); let held = 0, rough = 0, tot = 0;
  for (let x = 140; x < 340; x++) { if (Math.abs(b0.g[135 * W + x] - bar.g[135 * W + x]) < 1e-3) held++; for (const y of [129, 142]) { tot++; if (Math.abs(b0.g[y * W + x] - bar.g[y * W + x]) > 0.1) rough++; } }
  ok("Edge Burn: Burn 0 keeps the stroke and roughens its edges", held > 190 && rough > 0.1 * tot && rough < 0.9 * tot, `centre held ${held}/200, edges eaten ${rough}/${tot}`);
  const b1 = run({ dmMode: 5, dmBurn: 100 }, 1, bar); let left = 0; for (let i = 0; i < bar.n; i++) left = Math.max(left, Math.abs(b1.g[i] - 0.03));
  ok("Edge Burn: Burn 100 leaves the ground", left < 2 / 255, `max off the ground ${(left * 255).toFixed(2)}/255`);
  let ember = 0; for (const fb of [35, 45, 55]) { const o = run({ dmMode: 5, dmBurn: fb }, 1, bar); for (let i = 0; i < bar.n; i++) if (o.r[i] > 0.5 && o.r[i] > o.g[i] + 0.12 && o.g[i] > o.b[i] + 0.12) ember++; }
  ok("Edge Burn: a burning front glows orange", ember > 30, `${ember} orange pixels over three Burn settings`); }
{ const { sliders } = compile(D, {}, { frame: 1 }); let bad = 0; const sm = image(160, 90, () => [rnd(), rnd(), rnd()]);
  for (let k = 0; k < 24; k++) { const P = {}; for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd(); P.dmMode = k % 6;
    const o = run(P, Math.floor(rnd() * 999), sm); for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; } }
  ok("range over 24 slider sets, four per mode", bad === 0, `bad ${bad}`); }
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
