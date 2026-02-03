#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR/frontend"

echo "Checking frontend: node/npm and build"
if [ ! -d node_modules ]; then
  echo "Installing frontend dependencies (npm ci or fallback to npm install)"
  if npm ci --silent; then
    echo "npm ci succeeded"
  else
    echo "npm ci failed; attempting npm install"
    npm install --silent
  fi
fi

# try a dry build if script exists
if npm run | grep -q "build"; then
  npm run build --if-present
  echo "Frontend build succeeded"
else
  echo "No build script found; running lint if available"
  npm run lint --silent || true
fi

echo "Frontend check completed."