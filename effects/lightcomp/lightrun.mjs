import fs from "node:fs";
import os from "node:os";
import { Worker, isMainThread, parentPort, workerData } from "node:worker_threads";
import { fileURLToPath } from "node:url";
import { compile } from "../../tests/cpu/dctl.mjs";

if (isMainThread) {
  const [file, pj, inp, ws, hs, fr, out, pr, th] = process.argv.slice(2);
  const W = +ws, H = +hs, n = Math.max(1, +(th || os.cpus().length - 2));
  const buf = inp === "black" ? null : fs.readFileSync(inp);
  const shared = new SharedArrayBuffer(W * H * 3 * 4);
  let done = 0;
  for (let k = 0; k < n; k++) {
    const w = new Worker(fileURLToPath(import.meta.url), {
      workerData: { file, pj, buf, W, H, frame: +fr, progress: pr === undefined ? 0.5 : +pr, ya: k, step: n, shared } });
    w.on("message", () => {
      if (++done === n) { fs.writeFileSync(out, Buffer.from(shared)); process.exit(0); }
    });
    w.on("error", e => { console.error(e); process.exit(1); });
  }
} else {
  const { file, pj, buf, W, H, frame, progress, ya, step, shared } = workerData;
  const n = W * H, r = new Float32Array(n), g = new Float32Array(n), b = new Float32Array(n);
  if (buf) for (let i = 0; i < n; i++) { r[i] = buf[i * 3] / 255; g[i] = buf[i * 3 + 1] / 255; b[i] = buf[i * 3 + 2] / 255; }
  const T = compile(file, JSON.parse(pj), { frame, progress }).transform;
  const R = { d: r, w: W }, G = { d: g, w: W }, B = { d: b, w: W }, o = new Float32Array(shared);
  const two = T.length >= 12;
  for (let y = ya; y < H; y += step) for (let x = 0; x < W; x++) {
    const c = two ? T(W, H, x, y, R, G, B, null, R, G, B, null) : T(W, H, x, y, R, G, B), i = (y * W + x) * 3;
    o[i] = c.x; o[i + 1] = c.y; o[i + 2] = c.z;
  }
  parentPort.postMessage(1);
}
