import fs from "node:fs";
import { compile } from "../../tests/cpu/dctl.mjs";

const [file, pj, dir, ws, hs, f0s, i0s, i1s, ...flags] = process.argv.slice(2);
const W = +ws, H = +hs, P = JSON.parse(pj), useD = flags.includes("depth");
const rf = flags.find(f => f.startsWith("rows="));
const ry0 = rf ? +rf.slice(5).split(":")[0] : 0, ry1 = rf ? +rf.slice(5).split(":")[1] : H;
const pad = i => String(i).padStart(4, "0");
const n = W * H;
for (let i = +i0s; i < +i1s; i++) {
  const T = compile(file, P, { frame: +f0s + i }).transform;
  const buf = fs.readFileSync(`${dir}/a_${pad(i)}.rgb`);
  const r = new Float32Array(n), g = new Float32Array(n), b = new Float32Array(n);
  for (let k = 0; k < n; k++) { r[k] = buf[k * 3] / 255; g[k] = buf[k * 3 + 1] / 255; b[k] = buf[k * 3 + 2] / 255; }
  const R = { d: r, w: W }, G = { d: g, w: W }, B = { d: b, w: W };
  let A = R;
  if (useD) {
    const db = fs.readFileSync(`${dir}/d_${pad(i)}.u16`), a = new Float32Array(n);
    for (let k = 0; k < n; k++) a[k] = db.readUInt16LE(k * 2) / 65535;
    A = { d: a, w: W };
  }
  const out = Buffer.alloc((ry1 - ry0) * W * 3);
  const q = v => (v <= 0 ? 0 : v >= 1 ? 255 : Math.round(v * 255));
  for (let y = ry0; y < ry1; y++) for (let x = 0; x < W; x++) {
    const c = T(W, H, x, y, R, G, B, A), k = ((y - ry0) * W + x) * 3;
    out[k] = q(c.x); out[k + 1] = q(c.y); out[k + 2] = q(c.z);
  }
  fs.writeFileSync(rf ? `${dir}/o_${pad(i)}_r${ry0}.rgb` : `${dir}/o_${pad(i)}.rgb`, out);
}
