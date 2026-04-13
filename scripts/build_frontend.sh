#!/usr/bin/env bash
# Build Vite app for Django SPA shell (Elastic Beanstalk / any Linux deploy).
# Run from application root (e.g. /var/app/staging), not from frontend/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$ROOT/frontend"

echo "build_frontend: ROOT=$ROOT"
if [[ ! -d "$FRONTEND" ]]; then
  echo "ERROR: frontend/ is missing from the deployment bundle."
  echo "If you use 'eb deploy', ensure frontend/ is committed to git and not excluded by .ebignore."
  ls -la "$ROOT" || true
  exit 1
fi

if [[ ! -f "$FRONTEND/package.json" ]]; then
  echo "ERROR: $FRONTEND/package.json not found."
  exit 1
fi

cd "$FRONTEND"
echo "build_frontend: cwd=$(pwd)"
command -v node >/dev/null 2>&1 || { echo "ERROR: node not on PATH"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm not on PATH"; exit 1; }
node -v
npm -v

if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi

npm run build

if [[ ! -f dist/index.html ]]; then
  echo "ERROR: vite did not produce dist/index.html"
  ls -la dist 2>/dev/null || echo "(no dist dir)"
  exit 1
fi

echo "build_frontend: OK ($(wc -c < dist/index.html | tr -d ' ') bytes dist/index.html)"
ls -la dist/assets 2>/dev/null | head -8 || true
