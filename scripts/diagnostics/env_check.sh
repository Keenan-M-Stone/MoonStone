#!/usr/bin/env bash
set -euo pipefail

echo "== Environment check =="

echo -n "Python: " && python -V
python -c "import sys, pkgutil; print('PIP packages:'); print('\n'.join(p.name for p in pkgutil.iter_modules()))" | sed -n '1,20p'

if command -v node >/dev/null 2>&1; then
  echo -n "Node: " && node -v
else
  echo "Node: missing"
fi
if command -v npm >/dev/null 2>&1; then
  echo -n "npm: " && npm -v
else
  echo "npm: missing"
fi

# Check CUDA / GPU helper
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi ok"
else
  echo "nvidia-smi not found"
fi

python - <<'PY'
try:
    import importlib
    for m in ('numpy','numba','pytest','nbformat'):
        try:
            __import__(m)
            print(f"{m}: ok")
        except Exception:
            print(f"{m}: missing")
    try:
        import stardust.gpu as g
        print('stardust.gpu: ok, cuda_available=', g.is_cuda_available())
    except Exception as e:
        print('stardust.gpu: missing or error', e)
except Exception as e:
    print('python env probe failed:', e)
PY

echo "== End env check =="