#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STARDUST_DIR="$ROOT_DIR/../StarDust/frontend"
MOON_DIR="$ROOT_DIR/frontend"

if [ ! -d "$STARDUST_DIR" ]; then
  echo "StarDust frontend directory not found at $STARDUST_DIR"
  echo "Please clone or ensure it exists relative to the MoonStone repo root."
  exit 1
fi

# Install and link the StarDust package
cd "$STARDUST_DIR"
if [ -f package-lock.json ] || [ -f pnpm-lock.yaml ] || [ -f yarn.lock ]; then
  echo "Installing StarDust frontend dependencies..."
  npm ci || npm install
else
  echo "No lockfile in StarDust, using npm install"
  npm install
fi

echo "Creating global link for StarDust package (@stardust/ui)..."
npm link

# Link into MoonStone frontend
cd "$MOON_DIR"

echo "Linking @stardust/ui into MoonStone frontend..."
npm link @stardust/ui || { echo "npm link failed; try running the commands manually"; exit 1; }

echo "Linking complete. Run scripts/dev-down.sh && scripts/dev-up.sh to restart the dev stack and pick up the linked package."