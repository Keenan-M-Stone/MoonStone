#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS_DIR="$ROOT_DIR/scripts"
PIDS_DIR="$SCRIPTS_DIR/pids"
LOGS_DIR="$ROOT_DIR/logs"

mkdir -p "$PIDS_DIR" "$LOGS_DIR/backend" "$LOGS_DIR/frontend"

OSRELEASE=""
if [[ -r /proc/sys/kernel/osrelease ]]; then
  OSRELEASE="$(cat /proc/sys/kernel/osrelease)"
fi
IS_WSL=0
if echo "$OSRELEASE" | grep -qiE "microsoft|wsl"; then
  IS_WSL=1
fi

BACKEND_PID_FILE="$PIDS_DIR/backend.pid"
FRONTEND_PID_FILE="$PIDS_DIR/frontend.pid"
DASK_SCHED_PID_FILE="$PIDS_DIR/dask-scheduler.pid"
DASK_WORKER_PID_FILE="$PIDS_DIR/dask-worker.pid"

BACKEND_LOG="$LOGS_DIR/backend/uvicorn.log"
FRONT_LOG="$LOGS_DIR/frontend/vite.log"

is_pid_running() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1
}

find_listener_pid() {
  local port="$1"
  local line
  line="$(ss -ltnp 2>/dev/null | grep ":$port" | head -n 1 || true)"
  if [[ -z "$line" ]]; then
    echo ""
    return 0
  fi
  echo "$line" | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | head -n 1
}

cmdline_contains() {
  local pid="$1"
  local needle="$2"
  if [[ ! -r "/proc/$pid/cmdline" ]]; then
    return 1
  fi
  tr '\0' ' ' <"/proc/$pid/cmdline" | grep -Fq -- "$needle"
}

cwd_starts_with() {
  local pid="$1"
  local prefix="$2"
  local cwd
  cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  [[ -n "$cwd" ]] && [[ "$cwd" == "$prefix"* ]]
}

open_url() {
  local url="$1"
  if [[ "${MOONSTONE_NO_OPEN:-}" == "1" ]]; then
    return 0
  fi

  if [[ "$IS_WSL" == "1" ]] && command -v cmd.exe >/dev/null 2>&1; then
    cmd.exe /c start "" "$url" >/dev/null 2>&1 &
    return 0
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    nohup xdg-open "$url" >/dev/null 2>&1 &
  fi
}

http_ok() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -sf "$url" >/dev/null 2>&1
    return $?
  fi
  python - <<'PY' "$url" >/dev/null 2>&1
import sys, urllib.request
url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=1.0) as r:
        sys.exit(0 if 200 <= getattr(r, 'status', 200) < 300 else 1)
except Exception:
    sys.exit(1)
PY
}

# Try to use conda env 'moonstone' if present (prefer explicit env binaries).
MOONSTONE_ENV_BIN=""
if command -v conda >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh" || true
  if conda env list | grep -q "^\s*moonstone\s"; then
    echo "Activating conda env 'moonstone'"
    conda activate moonstone || true

    CONDA_BASE="$(conda info --base 2>/dev/null || true)"
    if [ -n "$CONDA_BASE" ] && [ -d "$CONDA_BASE/envs/moonstone/bin" ]; then
      MOONSTONE_ENV_BIN="$CONDA_BASE/envs/moonstone/bin"
    fi
  fi
fi

start_backend() {
  if [[ "${MOONSTONE_SKIP_BACKEND:-0}" == "1" ]]; then
    echo "Skipping backend start (MOONSTONE_SKIP_BACKEND=1)."
    return 0
  fi

  if [[ -f "$BACKEND_PID_FILE" ]]; then
    local pid
    pid="$(cat "$BACKEND_PID_FILE" || true)"
    if is_pid_running "$pid"; then
      echo "Backend appears to be running (pid $pid). Skipping start."
      return 0
    fi
  fi

  local listener_pid
  listener_pid="$(find_listener_pid 8000)"
  if [[ -n "$listener_pid" ]] && is_pid_running "$listener_pid"; then
    if cmdline_contains "$listener_pid" "uvicorn" && (cmdline_contains "$listener_pid" "app.main:app" || cwd_starts_with "$listener_pid" "$ROOT_DIR/backend"); then
      echo "$listener_pid" >"$BACKEND_PID_FILE"
      echo "Backend already running on :8000 (adopted pid $listener_pid)."
      return 0
    fi
    echo "Port 8000 already in use by pid $listener_pid; backend not started." >&2
    return 1
  fi

  echo "Starting backend (uvicorn) ..."
  cd "$ROOT_DIR/backend"

  local backend_host="127.0.0.1"
  if [[ "$IS_WSL" == "1" ]]; then
    backend_host="0.0.0.0"
  fi

  local backend_python=""
  if [[ -n "${MOONSTONE_BACKEND_PYTHON:-}" ]] && [[ -x "${MOONSTONE_BACKEND_PYTHON}" ]]; then
    backend_python="${MOONSTONE_BACKEND_PYTHON}"
  elif [[ -n "$MOONSTONE_ENV_BIN" ]] && [[ -x "$MOONSTONE_ENV_BIN/python" ]]; then
    backend_python="$MOONSTONE_ENV_BIN/python"
  elif command -v python3 >/dev/null 2>&1; then
    backend_python="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    backend_python="$(command -v python)"
  fi

  if [[ -z "$backend_python" ]]; then
    echo "No suitable Python interpreter found for backend." >&2
    return 1
  fi

  if ! "$backend_python" -c "import uvicorn" >/dev/null 2>&1; then
    echo "Backend Python '$backend_python' cannot import uvicorn." >&2
    echo "Install in your backend environment (e.g. pip install -r backend/requirements.txt) or set MOONSTONE_BACKEND_PYTHON." >&2
    return 1
  fi

  nohup "$backend_python" -m uvicorn app.main:app --host "$backend_host" --port 8000 --log-level info > "$BACKEND_LOG" 2>&1 &
  echo $! > "$BACKEND_PID_FILE"
  echo "Backend started, log: $BACKEND_LOG"

  local backend_pid
  backend_pid="$(cat "$BACKEND_PID_FILE")"
  local backend_url="http://127.0.0.1:8000/"
  for _ in {1..30}; do
    if ! is_pid_running "$backend_pid"; then
      echo "Backend exited during startup. Last log lines:"
      tail -n 60 "$BACKEND_LOG" || true
      rm -f "$BACKEND_PID_FILE"
      return 1
    fi
    if http_ok "$backend_url"; then
      echo "Backend is responsive at $backend_url"
      return 0
    fi
    sleep 0.2
  done

  echo "Backend did not become responsive at $backend_url. Last log lines:"
  tail -n 60 "$BACKEND_LOG" || true
  rm -f "$BACKEND_PID_FILE"
  return 1
}

start_frontend() {
  if [[ -f "$FRONTEND_PID_FILE" ]]; then
    local pid
    pid="$(cat "$FRONTEND_PID_FILE" || true)"
    if is_pid_running "$pid"; then
      echo "Frontend appears to be running (pid $pid). Skipping start."
      return 0
    fi
  fi

  local listener_pid
  listener_pid="$(find_listener_pid 3000)"
  if [[ -n "$listener_pid" ]] && is_pid_running "$listener_pid"; then
    if cwd_starts_with "$listener_pid" "$ROOT_DIR/frontend"; then
      echo "$listener_pid" >"$FRONTEND_PID_FILE"
      echo "Frontend already running on :3000 (adopted pid $listener_pid)."
      return 0
    fi
    echo "Port 3000 already in use by pid $listener_pid; frontend not started." >&2
    return 1
  fi

  echo "Starting frontend (npm run dev) ..."
  cd "$ROOT_DIR/frontend"

  if [ ! -d node_modules ]; then
    echo "Installing frontend dependencies (npm ci or fallback to npm install) ..."
    if npm ci --silent; then
      echo "npm ci succeeded"
    else
      echo "npm ci failed; attempting npm install"
      if npm install --silent; then
        echo "npm install succeeded"
      else
        echo "npm install failed; skipping frontend start"
        return 1
      fi
    fi
  fi

  local api_base="${MOONSTONE_API_BASE_URL:-}"
  if [[ -z "$api_base" ]]; then
    if [[ "$IS_WSL" == "1" ]]; then
      api_base="http://localhost:8000"
    else
      api_base="http://127.0.0.1:8000"
    fi
  fi
  export VITE_API_BASE="$api_base"

  if node -e "const p=require('./package.json'); process.exit((p && p.scripts && p.scripts.dev) ? 0 : 1)"; then
    nohup npm run dev > "$FRONT_LOG" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"
    echo "Frontend started, log: $FRONT_LOG"
    return 0
  fi

  echo "Skipping frontend start (no 'dev' script)"
  return 1
}

# Optional: start a local dask scheduler + worker if dask commands are available and not already running
start_dask() {
if command -v dask-scheduler >/dev/null 2>&1; then
  if [ -f "$DASK_SCHED_PID_FILE" ] && is_pid_running "$(cat "$DASK_SCHED_PID_FILE")"; then
    echo "Dask scheduler already running (pid $(cat "$DASK_SCHED_PID_FILE"))."
  else
    echo "Starting local dask-scheduler ..."
    if [ -n "$MOONSTONE_ENV_BIN" ] && [ -x "$MOONSTONE_ENV_BIN/dask-scheduler" ]; then
      nohup "$MOONSTONE_ENV_BIN/dask-scheduler" > "$LOGS_DIR/backend/dask-scheduler.log" 2>&1 &
    else
      nohup dask-scheduler > "$LOGS_DIR/backend/dask-scheduler.log" 2>&1 &
    fi
    echo $! > "$DASK_SCHED_PID_FILE"
    echo "Dask scheduler started"
  fi
  if [ -f "$DASK_WORKER_PID_FILE" ] && is_pid_running "$(cat "$DASK_WORKER_PID_FILE")"; then
    echo "Dask worker already running (pid $(cat "$DASK_WORKER_PID_FILE"))."
  else
    echo "Starting local dask-worker ..."
    if [ -n "$MOONSTONE_ENV_BIN" ] && [ -x "$MOONSTONE_ENV_BIN/dask-worker" ]; then
      nohup "$MOONSTONE_ENV_BIN/dask-worker" localhost:8786 > "$LOGS_DIR/backend/dask-worker.log" 2>&1 &
    else
      nohup dask-worker localhost:8786 > "$LOGS_DIR/backend/dask-worker.log" 2>&1 &
    fi
    echo $! > "$DASK_WORKER_PID_FILE"
    echo "Dask worker started"
  fi
fi
}

backend_ok=1
if ! start_backend; then
  backend_ok=0
fi
frontend_ok=1
if ! start_frontend; then
  frontend_ok=0
fi
start_dask

# Show short status
echo "--- STATUS ---"
if [ -f "$BACKEND_PID_FILE" ]; then
  echo "backend pid: $(cat "$BACKEND_PID_FILE")"
fi
if [ -f "$FRONTEND_PID_FILE" ]; then
  echo "frontend pid: $(cat "$FRONTEND_PID_FILE")"
fi
if [ -f "$DASK_SCHED_PID_FILE" ]; then
  echo "dask-scheduler pid: $(cat "$DASK_SCHED_PID_FILE")"
fi

if [ "$backend_ok" -eq 1 ]; then
  echo "api: http://127.0.0.1:8000"
else
  echo "api: (not running)"
fi
echo "ui:  http://127.0.0.1:3000"

if [ "$frontend_ok" -eq 1 ]; then
  sleep 1
  open_url "http://127.0.0.1:3000"
fi

echo "Dev environment started. Use scripts/dev-down.sh to stop."