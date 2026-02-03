#!/usr/bin/env bash
set -euo pipefail

if command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi output:"
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
else
  echo "nvidia-smi not found on PATH"
fi

python - <<'PY'
try:
    import stardust.gpu as g
    print('stardust.gpu.is_cuda_available() ->', g.is_cuda_available())
except Exception as e:
    print('stardust.gpu not available:', e)
PY