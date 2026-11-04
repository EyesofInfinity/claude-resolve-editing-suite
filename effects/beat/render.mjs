import fs from "node:fs";
import { spawn } from "node:child_process";
import { transpile } from "../../tests/cpu/dctl.mjs";

const [dctl, pj, input, ss, nf, f0, out, ws, hs, fs_] = process.argv.slice(2);
const W = +(ws || 1280), H = +(hs || 720), FPS = +(fs_ || 24), N = +nf, F0 = +f0;
const params = pj.trim().startsWith("{") ? JSON.parse(pj) : JSON.parse(fs.readFileSync(pj, "utf8"));
const { js, sliders } = transpile(dctl);
for (const k of Object.keys(params)) if (!(k in sliders)) throw new Error("unknown slider " + k);
const prelude = fs.readFileSync(new URL("../../tests/cpu/dctl.mjs", import.meta.url), "utf8").match(/const prelude = `([\s\S]*?)`;/)[1];
const make = new Function("P", "ENV", prelude + js + "\nreturn transform;");

const dec = spawn("ffmpeg", ["-v", "error", "-nostdin", "-ss", String(ss), "-i", input, "-frames:v", String(N), "-vf",
  `fps=${FPS},scale=${W}:${H}:force_original_aspect_ratio=increase:in_color_matrix=bt709,crop=${W}:${H}`,
  "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]);
const enc = spawn("ffmpeg", ["-v", "error", "-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", `${W}x${H}`,
  "-r", String(FPS), "-i", "-", "-c:v", "libx264", "-crf", "12", "-preset", "fast", "-pix_fmt", "yuv420p",
  "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", out], { stdio: ["pipe", "inherit", "inherit"] });

const size = W * H * 3, n = W * H;
let buf = Buffer.alloc(0), k = 0;
const img = { r: new Float32Array(n), g: new Float32Array(n), b: new Float32Array(n) };
const R = { d: img.r, w: W }, G = { d: img.g, w: W }, B = { d: img.b, w: W };
const o = Buffer.alloc(size);
const t0 = Date.now();
function frame(raw) {
  for (let i = 0; i < n; i++) { img.r[i] = raw[i * 3] / 255; img.g[i] = raw[i * 3 + 1] / 255; img.b[i] = raw[i * 3 + 2] / 255; }
  const T = make(params, { frame: F0 + k });
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const c = T(W, H, x, y, R, G, B), i = y * W + x;
    o[i * 3] = Math.max(0, Math.min(255, Math.round(c.x * 255)));
    o[i * 3 + 1] = Math.max(0, Math.min(255, Math.round(c.y * 255)));
    o[i * 3 + 2] = Math.max(0, Math.min(255, Math.round(c.z * 255)));
  }
  k++;
  return enc.stdin.write(Buffer.from(o));
}
dec.stdout.on("data", d => {
  buf = Buffer.concat([buf, d]);
  while (buf.length >= size) {
    const raw = buf.subarray(0, size);
    buf = buf.subarray(size);
    frame(raw);
  }
});
dec.on("close", () => {
  enc.stdin.end();
  enc.on("close", () => console.log(JSON.stringify({ out, frames: k, sec_per_frame: +((Date.now() - t0) / 1000 / Math.max(1, k)).toFixed(3) })));
});
