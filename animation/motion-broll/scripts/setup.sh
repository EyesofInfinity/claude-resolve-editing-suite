#!/usr/bin/env bash
# One-time setup in the user's project. Installs Playwright + Chromium into ./motion/node_modules.
set -e
MOTION_DIR="${1:-./motion}"
mkdir -p "$MOTION_DIR"/{clips,dist,out,work}
missing=()
command -v node >/dev/null || missing+=("node (https://nodejs.org)")
command -v ffmpeg >/dev/null || missing+=("ffmpeg (macOS: brew install ffmpeg)")
# on Windows "python3" is often the Microsoft Store placeholder, which exists but does not run: test that it runs
PY=""
for p in python3 python; do if "$p" -c "import sys" >/dev/null 2>&1; then PY="$p"; break; fi; done
[ -n "$PY" ] || missing+=("python 3")
if [ ${#missing[@]} -gt 0 ]; then echo "Missing: ${missing[*]}"; exit 1; fi
"$PY" -c "import numpy" 2>/dev/null || { echo "Missing: the Python package numpy. Run: $PY -m pip install numpy"; exit 1; }
if [ ! -d "$MOTION_DIR/node_modules/playwright" ]; then
  # a package.json here stops npm from installing into a parent project
  [ -f "$MOTION_DIR/package.json" ] || echo '{"private":true}' > "$MOTION_DIR/package.json"
  (cd "$MOTION_DIR" && npm install --silent playwright@1.64.1 && npx playwright install chromium)
fi
ffmpeg -hide_banner -encoders 2>/dev/null | grep -q prores_ks || echo "Note: your ffmpeg has no prores_ks encoder; transparent panel clips will fail."
echo "Ready. Clips go in $MOTION_DIR/clips, renders in $MOTION_DIR/out."
