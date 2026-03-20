#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$ROOT_DIR/.moonstone"
DEV_DIR="$DATA_DIR/dev"
PID_DIR="$DEV_DIR/pids"
LEGACY_PID_DIR="$ROOT_DIR/scripts/pids"
FRONTEND_PORT_FILE="$DEV_DIR/frontend.port"

BACKEND_PORT="${MOONSTONE_BACKEND_PORT:-8000}"
FRONTEND_PORT_DEFAULT="${MOONSTONE_FRONTEND_PORT:-3000}"

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

stop_pid_direct() {
  local name="$1"
  local pid="$2"
  if [[ -z "$pid" ]] || ! is_pid_running "$pid"; then
    return 0
  fi
  echo "Stopping $name (pid $pid)…"
  kill -TERM "$pid" >/dev/null 2>&1 || true
  for _ in {1..25}; do
    if ! is_pid_running "$pid"; then
      echo "$name stopped"
      return 0
    fi
    sleep 0.2
  done
  echo "$name still running; killing (pid $pid)…" >&2
  kill -KILL "$pid" >/dev/null 2>&1 || true
}

stop_pid_file() {
  local name="$1"
  local pid_file="$2"

  if [[ ! -f "$pid_file" ]]; then
    echo "$name not running (no pid file)"
    return 0
  fi

  local pid
  pid="$(cat "$pid_file" || true)"

  if [[ -z "$pid" ]]; then
    rm -f "$pid_file"
    echo "$name not running (empty pid file)"
    return 0
  fi

  if ! is_pid_running "$pid"; then
    rm -f "$pid_file"
    echo "$name not running (stale pid $pid)"
    return 0
  fi

  echo "Stopping $name (pid $pid)…"
  kill -TERM "$pid" >/dev/null 2>&1 || true

  # Wait up to ~5 seconds
  for _ in {1..25}; do
    if ! is_pid_running "$pid"; then
      rm -f "$pid_file"
      echo "$name stopped"
      return 0
    fi
    sleep 0.2
  done

  echo "$name still running; killing (pid $pid)…" >&2
  kill -KILL "$pid" >/dev/null 2>&1 || true
  rm -f "$pid_file"
  echo "$name killed"
}

frontend_port="$FRONTEND_PORT_DEFAULT"
if [[ -f "$FRONTEND_PORT_FILE" ]]; then
  frontend_port="$(cat "$FRONTEND_PORT_FILE" || echo "$FRONTEND_PORT_DEFAULT")"
fi

mkdir -p "$PID_DIR" "$LEGACY_PID_DIR" >/dev/null 2>&1 || true

for name in backend frontend dask-scheduler dask-worker; do
  stop_pid_file "$name" "$PID_DIR/$name.pid"
  stop_pid_file "$name (legacy)" "$LEGACY_PID_DIR/$name.pid"
done

rm -f "$FRONTEND_PORT_FILE" >/dev/null 2>&1 || true

backend_listener_pid="$(find_listener_pid "$BACKEND_PORT")"
if [[ -n "$backend_listener_pid" ]] && is_pid_running "$backend_listener_pid"; then
  if cmdline_contains "$backend_listener_pid" "uvicorn" && (cmdline_contains "$backend_listener_pid" "app.main:app" || cwd_starts_with "$backend_listener_pid" "$ROOT_DIR/backend"); then
    stop_pid_direct "backend listener" "$backend_listener_pid"
  fi
fi

frontend_listener_pid="$(find_listener_pid "$frontend_port")"
if [[ -n "$frontend_listener_pid" ]] && is_pid_running "$frontend_listener_pid"; then
  if cwd_starts_with "$frontend_listener_pid" "$ROOT_DIR/frontend" || cmdline_contains "$frontend_listener_pid" "vite"; then
    stop_pid_direct "frontend listener" "$frontend_listener_pid"
  fi
fi

if [[ "${MOONSTONE_DEV_DOWN_AGGRESSIVE:-0}" == "1" ]]; then
  echo "Aggressive cleanup enabled (MOONSTONE_DEV_DOWN_AGGRESSIVE=1)."
  pkill -f "$ROOT_DIR/backend" || true
  pkill -f "$ROOT_DIR/frontend" || true
  pkill -f dask-scheduler || true
  pkill -f dask-worker || true
fi

echo "Dev environment stopped."