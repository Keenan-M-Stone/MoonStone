#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PIDS_DIR="$ROOT_DIR/scripts/pids"

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

stop_pid() {
  local name="$1"
  local pid="$2"

  if ! is_pid_running "$pid"; then
    return 0
  fi

  echo "Stopping $name (pid $pid)"
  kill "$pid" || true
  sleep 1
  if is_pid_running "$pid"; then
    echo "Killing $name (pid $pid)"
    kill -9 "$pid" || true
  fi
}

kill_pidfile(){
  local pidfile="$1"
  if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile")
    stop_pid "pidfile process" "$pid"
    rm -f "$pidfile"
  fi
}

# Stop backend/frontend/dask processes started by dev-up
kill_pidfile "$PIDS_DIR/backend.pid" || true
kill_pidfile "$PIDS_DIR/frontend.pid" || true
kill_pidfile "$PIDS_DIR/dask-scheduler.pid" || true
kill_pidfile "$PIDS_DIR/dask-worker.pid" || true

# Fallback for stale listeners without pidfiles (targeted to MoonStone processes only)
backend_listener_pid="$(find_listener_pid 8000)"
if [[ -n "$backend_listener_pid" ]] && is_pid_running "$backend_listener_pid"; then
  if cmdline_contains "$backend_listener_pid" "uvicorn" && (cmdline_contains "$backend_listener_pid" "app.main:app" || cwd_starts_with "$backend_listener_pid" "$ROOT_DIR/backend"); then
    stop_pid "backend listener" "$backend_listener_pid"
  fi
fi

frontend_listener_pid="$(find_listener_pid 3000)"
if [[ -n "$frontend_listener_pid" ]] && is_pid_running "$frontend_listener_pid"; then
  if cwd_starts_with "$frontend_listener_pid" "$ROOT_DIR/frontend" || cmdline_contains "$frontend_listener_pid" "vite"; then
    stop_pid "frontend listener" "$frontend_listener_pid"
  fi
fi

if [[ "${MOONSTONE_DEV_DOWN_AGGRESSIVE:-0}" == "1" ]]; then
  echo "Aggressive cleanup enabled (MOONSTONE_DEV_DOWN_AGGRESSIVE=1)."
  pkill -f "$ROOT_DIR/backend" || true
  pkill -f "$ROOT_DIR/frontend" || true
  pkill -f dask-scheduler || true
  pkill -f dask-worker || true
fi

# remove leftover pid dir if empty
if [ -d "$PIDS_DIR" ] && [ -z "$(ls -A $PIDS_DIR)" ]; then
  rmdir "$PIDS_DIR" || true
fi

echo "Dev environment stopped."