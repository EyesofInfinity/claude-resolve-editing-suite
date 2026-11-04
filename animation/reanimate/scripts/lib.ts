// Shared helpers for the reanimate scripts. TypeScript with no build step: runs on Bun, or on Node 24+
// (which strips the types itself), on macOS, Linux and Windows.
import { mkdirSync, existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { spawnSync } from "node:child_process";

export const SCRIPTS_DIR = dirname(fileURLToPath(import.meta.url));
export const IS_WINDOWS = process.platform === "win32";

let ffmpegCached: string | undefined;
/** ffmpeg-static's binary (ffmpeg.exe on Windows), else $FFMPEG, else an ffmpeg on PATH. */
export function ffmpegPath(): string {
  if (ffmpegCached) return ffmpegCached;
  const bundled = join(SCRIPTS_DIR, "node_modules", "ffmpeg-static", IS_WINDOWS ? "ffmpeg.exe" : "ffmpeg");
  for (const p of [bundled, process.env.FFMPEG, "ffmpeg"]) {
    if (!p) continue;
    if (p === bundled && !existsSync(p)) continue;
    if (spawnSync(p, ["-hide_banner", "-version"], { encoding: "utf8" }).status === 0) return (ffmpegCached = p);
  }
  throw new Error(`ffmpeg not found, run node ${join(SCRIPTS_DIR, "setup.mjs")} (or put ffmpeg on PATH)`);
}

/** "https://…", "file:///…" and "data:…" pass through; anything else is a local file path. A Windows
 *  drive letter ("C:\\site\\index.html") is a path, never a URL scheme. */
export function toUrl(v: string): string {
  if (/^[a-z][a-z0-9+.-]+:/i.test(v) && !/^[a-z]:[\\/]/i.test(v)) return v;
  return pathToFileURL(resolve(v)).href;
}

export function ffmpeg(args: string[], opts: { quiet?: boolean } = {}): string {
  const r = spawnSync(ffmpegPath(), ["-hide_banner", "-loglevel", opts.quiet ? "error" : "warning", ...args], { encoding: "utf8", maxBuffer: 64 << 20 });
  if (r.status !== 0) throw new Error(`ffmpeg failed (${r.status}): ${r.stderr}`);
  return r.stderr;
}

/** Minimal argv parser: --key value, --flag, --key=value. Returns { _: positionals, ...flags }. */
export function parseArgs(argv: string[], defaults: Record<string, any> = {}): Record<string, any> {
  const out: Record<string, any> = { _: [], ...defaults };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith("--")) { out._.push(a); continue; }
    const eq = a.indexOf("=");
    if (eq > 0) { out[a.slice(2, eq)] = a.slice(eq + 1); continue; }
    const key = a.slice(2);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith("--")) out[key] = true;
    else { out[key] = next; i++; }
  }
  return out;
}

export function usage(text: string): never {
  console.log(text.trim() + "\n");
  process.exit(0);
}

export function ensureDir(p: string): string { mkdirSync(p, { recursive: true }); return p; }

export function num(v: any, fallback: number): number {
  if (v === undefined || v === true) return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

/** "1:23.5" | "83.5" | "83.5s" | "1500ms" -> seconds */
export function parseTime(v: any): number | undefined {
  if (v === undefined || v === true) return undefined;
  const s = String(v).trim();
  if (s.endsWith("ms")) return Number(s.slice(0, -2)) / 1000;
  if (s.includes(":")) { const [m, sec] = s.split(":"); return Number(m) * 60 + Number(sec); }
  return Number(s.replace(/s$/, ""));
}

export function parseSize(v: any, fallback: { width: number; height: number }) {
  if (!v || v === true) return fallback;
  const m = String(v).match(/^(\d+)x(\d+)$/);
  if (!m) throw new Error(`bad size "${v}", expected WxH`);
  return { width: Number(m[1]), height: Number(m[2]) };
}

export function parseRect(v: any): { x: number; y: number; width: number; height: number } | undefined {
  if (!v || v === true) return undefined;
  const p = String(v).split(",").map(Number);
  if (p.length !== 4 || p.some((n) => !Number.isFinite(n))) throw new Error(`bad rect "${v}", expected x,y,w,h`);
  return { x: p[0], y: p[1], width: p[2], height: p[3] };
}

export function listFrames(dir: string): string[] {
  return readdirSync(dir).filter((f) => /\.png$/i.test(f)).sort().map((f) => join(dir, f));
}

export function readJson<T = any>(p: string): T { return JSON.parse(readFileSync(p, "utf8")); }
export function writeJson(p: string, v: any) { writeFileSync(p, JSON.stringify(v, null, 2) + "\n"); }
export function abs(p: string) { return resolve(p); }
export const pad = (n: number, w = 4) => String(n).padStart(w, "0");
