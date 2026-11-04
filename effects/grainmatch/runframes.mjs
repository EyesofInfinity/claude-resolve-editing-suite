import fs from "node:fs";
import os from "node:os";
import { Worker, isMainThread, parentPort, workerData } from "node:worker_threads";
import { compile } from "../../tests/cpu/dctl.mjs";

if (isMainThread) {
  let a = process.argv.slice(2);
  let threads = 16;
  const ti = a.indexOf("--threads");
  if (ti >= 0) { threads = +a[ti + 1]; a.splice(ti, 2); }
  const [dctl, pjson, Ws, Hs, f0s, ...io] = a;
  const W = +Ws, H = +Hs, n = W * H;
  threads = Math.min(threads, os.cpus().length);
  for (let k = 0; k < io.length / 2; k++) {
    const t0 = Date.now();
    const buf = fs.readFileSync(io[2 * k]);
    const src = new SharedArrayBuffer(n * 3 * 4), dst = new SharedArrayBuffer(n * 3 * 4);
    const s = new Float32Array(src);
    for (let i = 0; i < n; i++) for (let c = 0; c < 3; c++) s[c * n + i] = buf.readUInt16LE((i * 3 + c) * 2) / 65535;
    const rows = Math.ceil(H / threads);
    await Promise.all(Array.from({ length: threads }, (_, j) => new Promise((res, rej) => {
      const w = new Worker(new URL(import.meta.url), { workerData: { dctl, P: JSON.parse(pjson), W, H, frame: +f0s + k, src, dst, y0: j * rows, y1: Math.min(H, (j + 1) * rows) } });
      w.on("message", res); w.on("error", rej);
    })));
    const d = new Float32Array(dst), out = Buffer.alloc(n * 6);
    for (let i = 0; i < n; i++) for (let c = 0; c < 3; c++) out.writeUInt16LE(Math.max(0, Math.min(65535, Math.round(d[c * n + i] * 65535))), (i * 3 + c) * 2);
    fs.writeFileSync(io[2 * k + 1], out);
    console.log(io[2 * k + 1], "frame", +f0s + k, "ms", Date.now() - t0);
  }
} else {
  const { dctl, P, W, H, frame, src, dst, y0, y1 } = workerData;
  const n = W * H, s = new Float32Array(src), d = new Float32Array(dst);
  const T = compile(dctl, P, { frame }).transform;
  const R = { d: s.subarray(0, n), w: W }, G = { d: s.subarray(n, 2 * n), w: W }, B = { d: s.subarray(2 * n), w: W };
  for (let y = y0; y < y1; y++) for (let x = 0; x < W; x++) {
    const c = T(W, H, x, y, R, G, B), i = y * W + x;
    d[i] = c.x; d[n + i] = c.y; d[2 * n + i] = c.z;
  }
  parentPort.postMessage(1);
}
