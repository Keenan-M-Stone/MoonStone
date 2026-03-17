#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$ROOT_DIR/.moonstone"
DEV_DIR="$DATA_DIR/dev"
PID_DIR="$DEV_DIR/pids"
LOG_DIR="$DEV_DIR/logs"
FRONTEND_PORT_FILE="$DEV_DIR/frontend.port"

BACKEND_PORT="${MOONSTONE_BACKEND_PORT:-8000}"
FRONTEND_PORT_DEFAULT="${MOONSTONE_FRONTEND_PORT:-3000}"

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"
DASK_SCHED_PID_FILE="$PID_DIR/dask-scheduler.pid"
DASK_WORKER_PID_FILE="$PID_DIR/dask-worker.pid"

BACKEND_LOG="$LOG_DIR/backend/uvicorn.log"
FRONTEND_LOG="$LOG_DIR/frontend/vite.log"
DASK_SCHED_LOG="$LOG_DIR/backend/dask-scheduler.log"
DASK_WORKER_LOG="$LOG_DIR/backend/dask-worker.log"

is_pid_running() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1
}

show_one() {
  local name="$1"
  local pid_file="$2"
  local url="$3"
  local log_file="$4"

  if [[ ! -f "$pid_file" ]]; then
    echo "$name: down (no pid file)"
    [[ -n "$log_file" ]] && echo "  log: $log_file"
    return 0
  fi

  local pid
  pid="$(cat "$pid_file" || true)"

  if is_pid_running "$pid"; then
    if [[ -n "$url" ]]; then
      echo "$name: up (pid $pid) -> $url"
    else
      echo "$name: up (pid $pid)"
    fi
    [[ -n "$log_file" ]] && echo "  log: $log_file"
  else
    echo "$name: down (stale pid $pid)"
    [[ -n "$log_file" ]] && echo "  log: $log_file"
  fi
}

mkdir -p "$PID_DIR" "$LOG_DIR/backend" "$LOG_DIR/frontend" >/dev/null 2>&1 || true

show_one "Backend" "$BACKEND_PID_FILE" "http://127.0.0.1:${BACKEND_PORT}" "$BACKEND_LOG"
FRONTEND_PORT="$FRONTEND_PORT_DEFAULT"
if [[ -f "$FRONTEND_PORT_FILE" ]]; then
  FRONTEND_PORT="$(cat "$FRONTEND_PORT_FILE" || echo "$FRONTEND_PORT_DEFAULT")"
fi
show_one "Frontend" "$FRONTEND_PID_FILE" "http://127.0.0.1:${FRONTEND_PORT}" "$FRONTEND_LOG"
show_one "Dask scheduler" "$DASK_SCHED_PID_FILE" "" "$DASK_SCHED_LOG"
show_one "Dask worker" "$DASK_WORKER_PID_FILE" "" "$DASK_WORKER_LOG"
