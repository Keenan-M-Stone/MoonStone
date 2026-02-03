#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

echo "Running pytest (fast) ..."
pytest -q || { echo "pytest failed"; exit 2; }

echo "All tests passed."