#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$ROOT_DIR/.moonstone"
DEV_DIR="$DATA_DIR/dev"
PID_DIR="$DEV_DIR/pids"
LOG_DIR="$DEV_DIR/logs"

LEGACY_PID_DIR="$ROOT_DIR/scripts/pids"

BACKEND_PORT="${MOONSTONE_BACKEND_PORT:-8000}"
FRONTEND_PORT="${MOONSTONE_FRONTEND_PORT:-3000}"
CONDA_ENV_NAME="${MOONSTONE_CONDA_ENV:-moonstone}"
BACKEND_PYTHON_OVERRIDE="${MOONSTONE_BACKEND_PYTHON:-}"

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"
DASK_SCHED_PID_FILE="$PID_DIR/dask-scheduler.pid"
DASK_WORKER_PID_FILE="$PID_DIR/dask-worker.pid"
FRONTEND_PORT_FILE="$DEV_DIR/frontend.port"

BACKEND_LOG="$LOG_DIR/backend/uvicorn.log"
FRONTEND_LOG="$LOG_DIR/frontend/vite.log"
DASK_SCHED_LOG="$LOG_DIR/backend/dask-scheduler.log"
DASK_WORKER_LOG="$LOG_DIR/backend/dask-worker.log"

BACKEND_BIN_DIR=""

mkdir -p "$PID_DIR" "$LOG_DIR/backend" "$LOG_DIR/frontend" "$LEGACY_PID_DIR"

OSRELEASE=""
if [[ -r /proc/sys/kernel/osrelease ]]; then
  OSRELEASE="$(cat /proc/sys/kernel/osrelease)"
fi
IS_WSL=0
if echo "$OSRELEASE" | grep -qiE "microsoft|wsl"; then
  IS_WSL=1
fi

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

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

http_ok() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -sf "$url" >/dev/null 2>&1
    return $?
  fi
  python3 - <<'PY' "$url" >/dev/null 2>&1
import sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1], timeout=1.0):
        sys.exit(0)
except Exception:
    sys.exit(1)
PY
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

  if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" && "$(uname -s)" != "Darwin" ]]; then
    echo "No GUI session detected. Open this URL manually: $url"
    return 0
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    nohup xdg-open "$url" >/dev/null 2>&1 &
  elif command -v open >/dev/null 2>&1; then
    nohup open "$url" >/dev/null 2>&1 &
  elif command -v python3 >/dev/null 2>&1; then
    nohup python3 -m webbrowser "$url" >/dev/null 2>&1 &
  else
    echo "No browser opener found. Open this URL manually: $url"
  fi
}

pick_backend_python() {
  if [[ -n "$BACKEND_PYTHON_OVERRIDE" && -x "$BACKEND_PYTHON_OVERRIDE" ]]; then
    echo "$BACKEND_PYTHON_OVERRIDE"
    return 0
  fi

  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    echo "$ROOT_DIR/.venv/bin/python"
    return 0
  fi

  if [[ -n "${VIRTUAL_ENV:-}" && -x "$VIRTUAL_ENV/bin/python" ]]; then
    echo "$VIRTUAL_ENV/bin/python"
    return 0
  fi

  if command -v conda >/dev/null 2>&1; then
    # shellcheck disable=SC1091
    source "$(conda info --base)/etc/profile.d/conda.sh" || true
    if conda env list | awk '{print $1}' | grep -Fxq "$CONDA_ENV_NAME"; then
      conda activate "$CONDA_ENV_NAME" >/dev/null 2>&1 || true
      if command -v python >/dev/null 2>&1; then
        command -v python
        return 0
      fi
    fi
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi

  return 1
}

copy_pid_to_legacy() {
  local file_name="$1"
  local source_file="$2"
  if [[ -f "$source_file" ]]; then
    cp "$source_file" "$LEGACY_PID_DIR/$file_name"
  fi
}

wait_for_process_http() {
  local pid="$1"
  local url="$2"
  local log_file="$3"
  local label="$4"

  for _ in {1..40}; do
    if ! is_pid_running "$pid"; then
      echo "$label exited during startup. Last log lines:" >&2
      tail -n 60 "$log_file" >&2 || true
      return 1
    fi
    if http_ok "$url"; then
      return 0
    fi
    sleep 0.25
  done

  echo "$label did not become responsive at $url. Last log lines:" >&2
  tail -n 60 "$log_file" >&2 || true
  return 1
}

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
      copy_pid_to_legacy "backend.pid" "$BACKEND_PID_FILE"
      return 0
    fi
  fi

  local listener_pid
  listener_pid="$(find_listener_pid "$BACKEND_PORT")"
  if [[ -n "$listener_pid" ]] && is_pid_running "$listener_pid"; then
    if cmdline_contains "$listener_pid" "uvicorn" && (cmdline_contains "$listener_pid" "app.main:app" || cwd_starts_with "$listener_pid" "$ROOT_DIR/backend"); then
      echo "$listener_pid" >"$BACKEND_PID_FILE"
      copy_pid_to_legacy "backend.pid" "$BACKEND_PID_FILE"
      echo "Backend already running on :$BACKEND_PORT (adopted pid $listener_pid)."
      return 0
    fi
    echo "Port $BACKEND_PORT already in use by pid $listener_pid; backend not started." >&2
    return 1
  fi

  local backend_python
  backend_python="$(pick_backend_python)" || {
    echo "No suitable Python interpreter found for backend." >&2
    return 1
  }
  BACKEND_BIN_DIR="$(dirname "$backend_python")"

  echo "Starting backend (uvicorn) ..."
  cd "$ROOT_DIR/backend"

  "$backend_python" -c "import uvicorn, fastapi, app.main" >/dev/null 2>&1 || {
    echo "Backend interpreter '$backend_python' is missing MoonStone backend deps." >&2
    echo "Run: cd $ROOT_DIR/backend && $backend_python -m pip install -r requirements.txt" >&2
    return 1
  }

  local backend_host="127.0.0.1"
  if [[ "$IS_WSL" == "1" ]]; then
    backend_host="0.0.0.0"
  fi

  nohup "$backend_python" -m uvicorn app.main:app --host "$backend_host" --port "$BACKEND_PORT" --log-level info >"$BACKEND_LOG" 2>&1 &

  local pid="$!"
  echo "$pid" >"$BACKEND_PID_FILE"
  copy_pid_to_legacy "backend.pid" "$BACKEND_PID_FILE"
  if ! wait_for_process_http "$pid" "http://127.0.0.1:$BACKEND_PORT/docs" "$BACKEND_LOG" "Backend"; then
    rm -f "$BACKEND_PID_FILE" "$LEGACY_PID_DIR/backend.pid"
    return 1
  fi

  echo "Backend started, log: $BACKEND_LOG"
}

start_frontend() {
  if [[ -f "$FRONTEND_PID_FILE" ]]; then
    local pid
    pid="$(cat "$FRONTEND_PID_FILE" || true)"
    if is_pid_running "$pid"; then
      echo "Frontend appears to be running (pid $pid). Skipping start."
      echo "$FRONTEND_PORT" >"$FRONTEND_PORT_FILE"
      copy_pid_to_legacy "frontend.pid" "$FRONTEND_PID_FILE"
      return 0
    fi
  fi

  local listener_pid
  listener_pid="$(find_listener_pid "$FRONTEND_PORT")"
  if [[ -n "$listener_pid" ]] && is_pid_running "$listener_pid"; then
    if cwd_starts_with "$listener_pid" "$ROOT_DIR/frontend" || cmdline_contains "$listener_pid" "vite"; then
      echo "$listener_pid" >"$FRONTEND_PID_FILE"
      echo "$FRONTEND_PORT" >"$FRONTEND_PORT_FILE"
      copy_pid_to_legacy "frontend.pid" "$FRONTEND_PID_FILE"
      echo "Frontend already running on :$FRONTEND_PORT (adopted pid $listener_pid)."
      return 0
    fi
    echo "Port $FRONTEND_PORT already in use by pid $listener_pid; frontend not started." >&2
    return 1
  fi

  require_cmd npm
  echo "Starting frontend (npm run dev) ..."
  cd "$ROOT_DIR/frontend"

  if [[ ! -d node_modules ]]; then
    echo "Installing frontend dependencies (npm ci or fallback to npm install) ..."
    if npm ci --silent; then
      echo "npm ci succeeded"
    else
      echo "npm ci failed; attempting npm install"
      npm install --silent
    fi
  fi

  local api_base="${MOONSTONE_API_BASE_URL:-}"
  if [[ -z "$api_base" ]]; then
    if [[ "$IS_WSL" == "1" ]]; then
      api_base="http://localhost:$BACKEND_PORT"
    else
      api_base="http://127.0.0.1:$BACKEND_PORT"
    fi
  fi
  export VITE_API_BASE="$api_base"

  nohup npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" >"$FRONTEND_LOG" 2>&1 &

  local pid="$!"
  echo "$pid" >"$FRONTEND_PID_FILE"
  echo "$FRONTEND_PORT" >"$FRONTEND_PORT_FILE"
  copy_pid_to_legacy "frontend.pid" "$FRONTEND_PID_FILE"
  if ! wait_for_process_http "$pid" "http://127.0.0.1:$FRONTEND_PORT" "$FRONTEND_LOG" "Frontend"; then
    rm -f "$FRONTEND_PID_FILE" "$FRONTEND_PORT_FILE" "$LEGACY_PID_DIR/frontend.pid"
    return 1
  fi

  echo "Frontend started, log: $FRONTEND_LOG"
}

start_dask() {
  if [[ "${MOONSTONE_SKIP_DASK:-0}" == "1" ]]; then
    echo "Skipping local Dask services (MOONSTONE_SKIP_DASK=1)."
    return 0
  fi

  local scheduler_cmd=""
  local worker_cmd=""
  if [[ -n "$BACKEND_BIN_DIR" && -x "$BACKEND_BIN_DIR/dask-scheduler" && -x "$BACKEND_BIN_DIR/dask-worker" ]]; then
    scheduler_cmd="$BACKEND_BIN_DIR/dask-scheduler"
    worker_cmd="$BACKEND_BIN_DIR/dask-worker"
  elif command -v dask-scheduler >/dev/null 2>&1 && command -v dask-worker >/dev/null 2>&1; then
    scheduler_cmd="dask-scheduler"
    worker_cmd="dask-worker"
  else
    echo "Dask commands not found; skipping local scheduler/worker startup."
    return 0
  fi

  if [[ -f "$DASK_SCHED_PID_FILE" ]] && is_pid_running "$(cat "$DASK_SCHED_PID_FILE")"; then
    echo "Dask scheduler already running (pid $(cat "$DASK_SCHED_PID_FILE"))."
  else
    echo "Starting local dask-scheduler ..."
    nohup "$scheduler_cmd" >"$DASK_SCHED_LOG" 2>&1 &
    echo "$!" >"$DASK_SCHED_PID_FILE"
    copy_pid_to_legacy "dask-scheduler.pid" "$DASK_SCHED_PID_FILE"
    echo "Dask scheduler started"
  fi

  if [[ -f "$DASK_WORKER_PID_FILE" ]] && is_pid_running "$(cat "$DASK_WORKER_PID_FILE")"; then
    echo "Dask worker already running (pid $(cat "$DASK_WORKER_PID_FILE"))."
  else
    echo "Starting local dask-worker ..."
    nohup "$worker_cmd" localhost:8786 >"$DASK_WORKER_LOG" 2>&1 &
    echo "$!" >"$DASK_WORKER_PID_FILE"
    copy_pid_to_legacy "dask-worker.pid" "$DASK_WORKER_PID_FILE"
    echo "Dask worker started"
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

echo "UI:      http://127.0.0.1:${FRONTEND_PORT}"
if [[ "$backend_ok" == "1" ]]; then
  echo "API:     http://127.0.0.1:${BACKEND_PORT}"
  echo "API docs http://127.0.0.1:${BACKEND_PORT}/docs"
else
  echo "API:     (not running)"
fi

if [[ "$frontend_ok" == "1" ]]; then
  open_url "http://127.0.0.1:${FRONTEND_PORT}"
else
  echo "Frontend may not be running. Open this URL manually: http://127.0.0.1:${FRONTEND_PORT}"
fi