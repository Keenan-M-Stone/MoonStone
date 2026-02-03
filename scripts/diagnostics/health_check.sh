#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
OUTFILE="$ROOT_DIR/scripts/diagnostics/health_summary.json"
TMPDIR=$(mktemp -d)
FAIL=0

# helper to run a command and capture stdout/stderr and exit code
run_cmd(){
  local name="$1"
  shift
  local out="$TMPDIR/${name}.out"
  local err="$TMPDIR/${name}.err"
  {
    echo "--- RUN: $name ---"
    "$@"
  } >"$out" 2>"$err" || true
  local code=$?
  # Build JSON without jq for portability
  local out_txt
  local err_txt
  out_txt="$(sed -n '1,200p' "$out" | python -c "import json,sys; print(json.dumps(sys.stdin.read()[:200]))")"
  err_txt="$(sed -n '1,200p' "$err" | python -c "import json,sys; print(json.dumps(sys.stdin.read()[:200]))")"
  printf '{"name":"%s","exit_code":%d,"out":%s,"err":%s}' "$name" "$code" "$out_txt" "$err_txt" > "$TMPDIR/${name}.json"
  cat "$TMPDIR/${name}.json"
  return $code
}

# run individual checks and capture JSON fragments
env_json=$(run_cmd env_check bash "$ROOT_DIR/scripts/diagnostics/env_check.sh")
if [ $? -ne 0 ]; then FAIL=1; fi
frontend_json=$(run_cmd frontend_check bash "$ROOT_DIR/scripts/diagnostics/frontend_check.sh")
if [ $? -ne 0 ]; then FAIL=1; fi
tests_json=$(run_cmd run_tests bash "$ROOT_DIR/scripts/diagnostics/run_tests.sh")
if [ $? -ne 0 ]; then FAIL=1; fi
gpu_json=$(run_cmd gpu_check bash "$ROOT_DIR/scripts/diagnostics/gpu_check.sh")
if [ $? -ne 0 ]; then FAIL=1; fi

# assemble final JSON using Python (avoid requiring `jq`)
python - <<PY
import json, time, pathlib
TMP = pathlib.Path("$TMPDIR")
def load(name):
    p = TMP / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"name": name, "exit_code": 127, "out": "", "err": ""}
env = load('env_check')
frontend = load('frontend_check')
tests = load('run_tests')
gpu = load('gpu_check')
summary = {
    'timestamp': int(time.time()),
    'env': env,
    'frontend': frontend,
    'tests': tests,
    'gpu': gpu,
    'ok': (env.get('exit_code') == 0 and frontend.get('exit_code') == 0 and tests.get('exit_code') == 0 and gpu.get('exit_code') == 0)
}
OUT = pathlib.Path("$OUTFILE")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(summary))
print('Wrote health summary to', str(OUT))
PY

# cleanup
rm -rf "$TMPDIR"

if [ "$FAIL" -ne 0 ]; then
  echo "One or more checks failed"
  exit 2
fi

exit 0
