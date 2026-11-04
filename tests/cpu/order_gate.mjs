import { transpile } from "./dctl.mjs";

let bad = 0;
for (const f of process.argv.slice(2)) {
  try { transpile(f); console.log("ok   " + f); } catch (e) { bad++; console.log("FAIL " + f + ": " + e.message); }
}
process.exit(bad ? 1 : 0);
