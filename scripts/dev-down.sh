#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PIDS_DIR="$ROOT_DIR/scripts/pids"

kill_pidfile(){
  local pidfile="$1"
  if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      echo "Stopping pid $pid from $pidfile"
      kill "$pid" || true
      sleep 1
      if kill -0 "$pid" 2>/dev/null; then
        echo "Killing $pid"
        kill -9 "$pid" || true
      fi
    fi
    rm -f "$pidfile"
  fi
}

# Stop backend/frontend/dask processes started by dev-up
kill_pidfile "$PIDS_DIR/backend.pid" || true
kill_pidfile "$PIDS_DIR/frontend.pid" || true
kill_pidfile "$PIDS_DIR/dask-scheduler.pid" || true
kill_pidfile "$PIDS_DIR/dask-worker.pid" || true

# As a fallback, try to pkill likely lingering processes
pkill -f uvicorn || true
pkill -f "vite" || true
pkill -f "npm run dev" || true
pkill -f dask-scheduler || true
pkill -f dask-worker || true

# remove leftover pid dir if empty
if [ -d "$PIDS_DIR" ] && [ -z "$(ls -A $PIDS_DIR)" ]; then
  rmdir "$PIDS_DIR" || true
fi

echo "Dev environment stopped."