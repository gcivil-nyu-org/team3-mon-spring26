#!/usr/bin/env bash
# Elastic Beanstalk: produce a fresh frontend/dist on every deploy.
# If npm/node is unavailable or the build fails, falls back to the committed
# frontend/dist that ships in the deployment archive.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="${ROOT}/frontend"

if [[ ! -d "${FRONTEND}" ]]; then
  echo "eb_build_frontend: no frontend/ directory."
  exit 1
fi

# ---- Attempt a fresh Vite build (best-effort) ----------------------------
build_ok=0
if [[ -f "${FRONTEND}/package.json" ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    if command -v dnf >/dev/null 2>&1; then
      dnf install -y nodejs npm 2>&1 || true
    elif command -v yum >/dev/null 2>&1; then
      yum install -y nodejs npm 2>&1 || true
    fi
  fi

  if command -v npm >/dev/null 2>&1; then
    # EB often sets NODE_ENV=production; that makes npm skip devDependencies, so Vite is missing.
    unset NODE_ENV || true
    export NPM_CONFIG_PRODUCTION=false

    # Back up the committed dist so we can restore it if the build fails.
    if [[ -d "${FRONTEND}/dist" ]]; then
      cp -a "${FRONTEND}/dist" "${FRONTEND}/dist_backup"
    fi

    echo "eb_build_frontend: npm ci + vite build..."
    rm -rf "${FRONTEND}/dist"
    if (
      cd "${FRONTEND}"
      if [[ -f package-lock.json ]] || [[ -f npm-shrinkwrap.json ]]; then
        npm ci
      else
        npm install
      fi
      npm run build
    ); then
      build_ok=1
      rm -rf "${FRONTEND}/dist_backup"
      echo "eb_build_frontend: fresh Vite build succeeded."
    else
      echo "eb_build_frontend: Vite build FAILED — restoring committed dist."
      rm -rf "${FRONTEND}/dist"
      if [[ -d "${FRONTEND}/dist_backup" ]]; then
        mv "${FRONTEND}/dist_backup" "${FRONTEND}/dist"
      fi
    fi
  else
    echo "eb_build_frontend: npm not available — using committed dist."
  fi
fi

# ---- Verify final state --------------------------------------------------
if [[ ! -f "${FRONTEND}/dist/index.html" ]]; then
  echo "eb_build_frontend: ERROR frontend/dist/index.html missing. Ensure the dist is committed to git."
  exit 1
fi

assets_dir="${FRONTEND}/dist/assets"
if [[ ! -d "${assets_dir}" ]] || ! compgen -G "${assets_dir}/*" >/dev/null 2>&1; then
  echo "eb_build_frontend: ERROR dist/assets missing or empty."
  exit 1
fi

echo "eb_build_frontend: OK ($(wc -c < "${FRONTEND}/dist/index.html" | tr -d ' ') bytes index.html)"
