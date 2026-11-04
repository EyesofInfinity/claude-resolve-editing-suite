import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
let files = process.argv.slice(2);
if (!files.length) {
  const eff = path.join(repo, "effects");
  for (const d of fs.readdirSync(eff)) {
    const b = path.join(eff, d, "build");
    if (fs.existsSync(b)) for (const f of fs.readdirSync(b)) if (f.endsWith(".dctl")) files.push(path.join(b, f));
  }
  for (const f of fs.readdirSync(path.join(repo, "nodes"))) if (f.endsWith(".dctl")) files.push(path.join(repo, "nodes", f));
  files.push(path.join(repo, "Develop.dctl"));
}
let bad = 0;
for (const f of files) {
  const src = fs.readFileSync(f, "utf8").replace(/\/\/[^\n]*/g, "").replace(/\/\*[\s\S]*?\*\//g, "");
  const m = /__DEVICE__\s+float[34]\s+(transform|transition)\s*\([^)]*\)\s*\{/.exec(src);
  if (!m) { console.log(`NO MAIN: ${path.relative(repo, f)}`); bad++; continue; }
  let i = m.index + m[0].length, depth = 1;
  const start = i;
  while (i < src.length && depth) { if (src[i] === "{") depth++; else if (src[i] === "}") depth--; i++; }
  const body = src.slice(start, i - 1);
  const rets = [...body.matchAll(/\breturn\b[ \t]*([^;]*);/g)].map(r => r[1]);
  const wrong = rets.filter(r => /\n/.test(r) && !/^\s*make_float[34]\s*\(/.test(r));
  if (!rets.length || wrong.length) {
    bad++;
    console.log(`BAD: ${path.relative(repo, f)}: ${rets.length ? wrong.map(w => "return " + w.slice(0, 50)).join("; ") : "no return"}`);
  }
}
console.log(`${files.length} files, ${bad} whose main function has a return over several lines not starting make_float`);
process.exit(bad ? 1 : 0);
