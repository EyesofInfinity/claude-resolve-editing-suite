import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const LIMIT = 64;
const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
let files = process.argv.slice(2);
if (!files.length) {
  const eff = path.join(repo, "effects");
  for (const d of fs.readdirSync(eff)) {
    const b = path.join(eff, d, "build");
    if (fs.existsSync(b)) for (const f of fs.readdirSync(b)) if (f.endsWith(".dctl")) files.push(path.join(b, f));
  }
  for (const f of fs.readdirSync(path.join(repo, "nodes"))) if (f.endsWith(".dctl")) files.push(path.join(repo, "nodes", f));
  files.push(path.join(repo, "Develop 1 Light.dctl"), path.join(repo, "Develop 2 Color.dctl"));
}
let over = 0;
for (const f of files) {
  const n = (fs.readFileSync(f, "utf8").match(/^\s*DEFINE_UI_PARAMS\s*\(/gm) || []).length;
  if (n > LIMIT) {
    over++;
    console.log(`OVER: ${path.relative(repo, f)} declares ${n} sliders; a DCTL plugin node takes ${LIMIT}`);
  }
}
console.log(`${files.length} files, ${over} over ${LIMIT} sliders`);
process.exit(over ? 1 : 0);
