// Installs the script dependencies once and checks that Chromium and ffmpeg are usable. The cross-platform
// twin of setup.sh: runs with Node 24+ (or Bun) on macOS, Linux and Windows. Uses bun when it is on PATH,
// npm otherwise. Safe to re-run; it is a no-op when everything is already in place.
import { existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const HERE = dirname(fileURLToPath(import.meta.url));
const WIN = process.platform === "win32";
// npm, npx and bun are .cmd shims on Windows, which spawnSync only runs through a shell; the commands here
// are fixed strings, so they go to the shell as one line
const spawn = (cmd, args, opts) => WIN ? spawnSync([cmd, ...args].join(" "), { ...opts, shell: true }) : spawnSync(cmd, args, opts);
const run = (cmd, args) => spawn(cmd, args, { cwd: HERE, stdio: "inherit" });
const has = (cmd) => spawn(cmd, ["--version"], { stdio: "ignore" }).status === 0;

const bun = has("bun");
const ffmpegBin = join(HERE, "node_modules", "ffmpeg-static", WIN ? "ffmpeg.exe" : "ffmpeg");
if (!existsSync(join(HERE, "node_modules", "playwright")) || !existsSync(ffmpegBin)) {
  const r = bun ? run("bun", ["install", "--silent"]) : run("npm", ["install", "--no-audit", "--no-fund", "--loglevel=error"]);
  if (r.status !== 0) { console.error("dependency install failed"); process.exit(1); }
}

const probe = `const {chromium}=await import("playwright"); const b=await chromium.launch(); await b.close(); console.log("chromium ok")`;
const evalArgs = process.versions.bun ? ["-e", probe] : ["--input-type=module", "-e", probe];
const ok = spawnSync(process.execPath, evalArgs, { cwd: HERE, stdio: "ignore" }).status === 0;
if (!ok) {
  console.log("Chromium missing for this Playwright version, installing it...");
  const r = bun ? run("bunx", ["playwright", "install", "chromium"]) : run("npx", ["playwright", "install", "chromium"]);
  if (r.status !== 0) { console.error("Chromium install failed"); process.exit(1); }
}

const ff = existsSync(ffmpegBin) ? ffmpegBin : "ffmpeg";
const v = spawnSync(ff, ["-hide_banner", "-version"], { encoding: "utf8" });
if (v.status !== 0) { console.error("ffmpeg not usable: ffmpeg-static did not download its binary and none is on PATH"); process.exit(1); }
console.log(v.stdout.split("\n")[0]);
console.log("ready: " + HERE);
