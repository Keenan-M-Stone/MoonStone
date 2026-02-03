#!/usr/bin/env bash
set -euo pipefail

# dev-up: start backend, frontend, (optional) Dask scheduler/worker and write PID files to scripts/pids
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS_DIR="$ROOT_DIR/scripts"
PIDS_DIR="$SCRIPTS_DIR/pids"
LOGS_DIR="$ROOT_DIR/logs"

mkdir -p "$PIDS_DIR" "$LOGS_DIR/backend" "$LOGS_DIR/frontend"

# Try to activate conda env 'moonstone' if present
if command -v conda >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh" || true
  if conda env list | grep -q "^\s*moonstone\s"; then
    echo "Activating conda env 'moonstone'"
    conda activate moonstone || true
  fi
fi

# Start backend (uvicorn) if not already running
BACKEND_LOG="$LOGS_DIR/backend/uvicorn.log"
if [ -f "$PIDS_DIR/backend.pid" ] && kill -0 "$(cat $PIDS_DIR/backend.pid)" 2>/dev/null; then
  echo "Backend appears to be running (pid $(cat $PIDS_DIR/backend.pid)). Skipping start."
else
  echo "Starting backend (uvicorn) ..."
  cd "$ROOT_DIR/backend"
  nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$BACKEND_LOG" 2>&1 &
  echo $! > "$PIDS_DIR/backend.pid"
  echo "Backend started, log: $BACKEND_LOG"
fi

# Start frontend (Vite) if not already running
FRONT_LOG="$LOGS_DIR/frontend/vite.log"
if [ -f "$PIDS_DIR/frontend.pid" ] && kill -0 "$(cat $PIDS_DIR/frontend.pid)" 2>/dev/null; then
  echo "Frontend appears to be running (pid $(cat $PIDS_DIR/frontend.pid)). Skipping start."
else
  echo "Starting frontend (npm run dev) ..."
  cd "$ROOT_DIR/frontend"
  # install dependencies if node_modules missing; tolerate failure
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
      fi
    fi
  fi
  # Only start dev server if package.json has a dev script and node_modules exist
  if npm run | grep -q "dev" && [ -d node_modules ]; then
    nohup npm run dev > "$FRONT_LOG" 2>&1 &
    echo $! > "$PIDS_DIR/frontend.pid"
    echo "Frontend started, log: $FRONT_LOG"
  else
    echo "Skipping frontend start (no 'dev' script or installation failed)"
  fi
fi

# Optional: start a local dask scheduler + worker if dask commands are available and not already running
if command -v dask-scheduler >/dev/null 2>&1; then
  if [ -f "$PIDS_DIR/dask-scheduler.pid" ] && kill -0 "$(cat $PIDS_DIR/dask-scheduler.pid)" 2>/dev/null; then
    echo "Dask scheduler already running (pid $(cat $PIDS_DIR/dask-scheduler.pid))."
  else
    echo "Starting local dask-scheduler ..."
    nohup dask-scheduler > "$LOGS_DIR/backend/dask-scheduler.log" 2>&1 &
    echo $! > "$PIDS_DIR/dask-scheduler.pid"
    echo "Dask scheduler started"
  fi
  if [ -f "$PIDS_DIR/dask-worker.pid" ] && kill -0 "$(cat $PIDS_DIR/dask-worker.pid)" 2>/dev/null; then
    echo "Dask worker already running (pid $(cat $PIDS_DIR/dask-worker.pid))."
  else
    echo "Starting local dask-worker ..."
    nohup dask-worker localhost:8786 > "$LOGS_DIR/backend/dask-worker.log" 2>&1 &
    echo $! > "$PIDS_DIR/dask-worker.pid"
    echo "Dask worker started"
  fi
fi

# Show short status
echo "--- STATUS ---"
if [ -f "$PIDS_DIR/backend.pid" ]; then
  echo "backend pid: $(cat $PIDS_DIR/backend.pid)"
fi
if [ -f "$PIDS_DIR/frontend.pid" ]; then
  echo "frontend pid: $(cat $PIDS_DIR/frontend.pid)"
fi
if [ -f "$PIDS_DIR/dask-scheduler.pid" ]; then
  echo "dask-scheduler pid: $(cat $PIDS_DIR/dask-scheduler.pid)"
fi

# Attempt to open the UI in the default browser (Vite default port 5173)
if command -v xdg-open >/dev/null 2>&1; then
  sleep 1
  xdg-open "http://localhost:5173" >/dev/null 2>&1 || true
fi

echo "Dev environment started. Use scripts/dev-down.sh to stop."