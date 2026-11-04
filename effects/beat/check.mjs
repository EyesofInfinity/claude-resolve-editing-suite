import fs from "node:fs";
import { transpile } from "../../tests/cpu/dctl.mjs";

const [file, expPath] = process.argv.slice(2);
const exp = JSON.parse(fs.readFileSync(expPath, "utf8"));
const { js, sliders } = transpile(file);
const prelude = fs.readFileSync(new URL("../../tests/cpu/dctl.mjs", import.meta.url), "utf8").match(/const prelude = `([\s\S]*?)`;/)[1];
const make = new Function("P", "ENV", prelude + js + "\nreturn { transform, btEnv, btTier };");
let fails = 0;
const ok = (name, pass, info) => { console.log(`${pass ? "pass" : "FAIL"} ${name} ${info}`); if (!pass) fails++; };

for (const [ci, c] of exp.cases.entries()) {
  const s = c.sliders, g = k => (s[k] !== undefined ? s[k] : sliders[k].def);
  const fps = g("btFps"), mode = Math.round(g("btMode"));
  const bright = [0, 3, 4, 5].includes(mode) ? 1 : 0;
  let worst = 0, at = -1;
  for (const [i, f] of c.frames.entries()) {
    const E = make(s, { frame: f });
    const tier = E.btTier(g("btRate"), bright);
    const e = E.btEnv(f, g("btStart"), g("btNudge"), fps, Math.trunc(g("btSource") + 0.5), Math.trunc(g("btShape") + 0.5),
      g("btAttack") * fps / 1000, g("btRelease") * fps / 1000, g("btAccent") / 100, tier, g("btBpm"), g("btFloor") / 100);
    const d = Math.abs(e - c.env[i]);
    if (d > worst) { worst = d; at = f; }
  }
  ok(`envelope case ${ci} (${c.name})`, worst < 1e-9, `worst ${worst.toExponential(2)} at frame ${at} over ${c.frames.length} frames`);
}

const W = 160, H = 90, n = W * H;
let seed = 7;
const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
const A = { r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
for (let i = 0; i < n; i++) {
  const x = i % W, y = Math.floor(i / W), spot = ((x - 50) ** 2 + (y - 30) ** 2 < 30) ? 0.6 : 0;
  const v = 0.15 + 0.5 * x / W + 0.2 * rnd() + spot;
  A.r[i] = Math.min(1, v); A.g[i] = Math.min(1, 0.9 * v); A.b[i] = Math.min(1, 0.8 * v + 0.1 * rnd());
}
function run(P, frame) {
  const T = make(P, { frame }).transform;
  const o = { r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
  const R = { d: A.r, w: W }, G = { d: A.g, w: W }, B = { d: A.b, w: W };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const c = T(W, H, x, y, R, G, B), i = y * W + x; o.r[i] = c.x; o.g[i] = c.y; o.b[i] = c.z; }
  return o;
}
const diff = (o, B) => { let d = 0; for (const k of ["r", "g", "b"]) for (let i = 0; i < n; i++) if (o[k][i] !== B[k][i]) d++; return d; };

for (let m = 0; m <= 6; m++) {
  const d0 = diff(run({ btMode: m, btAmount: 0 }, exp.loud), A);
  const d1 = diff(run({ btMode: m, btAmount: 100, btSource: 1, btRelease: 100 }, exp.quiet), A);
  const d2 = diff(run({ btMode: m, btAmount: 100, btSource: 1, btRelease: 100 }, exp.loud), A);
  ok(`reaction ${m} identity`, d0 === 0 && d1 === 0 && d2 > n * 0.05, `amount 0: ${d0}, quiet frame: ${d1}, loud frame changed ${d2}`);
}

{
  const a = run({ btMode: 2, btAmount: 80, btSource: 0 }, exp.loud), b = run({ btMode: 2, btAmount: 80, btSource: 0 }, exp.loud);
  ok("same frame twice identical", diff(a, b) === 0, `differ ${diff(a, b)}`);
}

{
  let bad = 0;
  for (let k = 0; k < 40; k++) {
    const P = {};
    for (const [nm, v] of Object.entries(sliders)) P[nm] = v.lo + (v.hi - v.lo) * rnd();
    P.btStart = 2 * rnd();
    const o = run(P, Math.floor(rnd() * 1500));
    for (const c of ["r", "g", "b"]) for (const v of o[c]) if (!Number.isFinite(v) || v < 0 || v > 1) { bad++; break; }
  }
  ok("range over 40 random slider sets", bad === 0, `bad ${bad}`);
}
console.log(fails ? `${fails} FAILED` : "all pass");
process.exit(fails ? 1 : 0);
