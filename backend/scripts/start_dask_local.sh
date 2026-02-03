#!/usr/bin/env bash
# Simple script to spawn a local Dask scheduler and one worker for development
set -euo pipefail

# Try to start scheduler and worker in background
command -v dask-scheduler >/dev/null 2>&1 || { echo 'dask-scheduler not found in PATH; ensure dask is installed'; exit 1; }
command -v dask-worker >/dev/null 2>&1 || { echo 'dask-worker not found in PATH; ensure dask is installed'; exit 1; }

PORT=${DASK_SCHEDULER_PORT:-8786}
LOGDIR=${DASK_LOGDIR:-./dask-logs}
mkdir -p "$LOGDIR"

echo "Starting dask-scheduler on port $PORT"
nohup dask-scheduler --port $PORT > "$LOGDIR/scheduler.log" 2>&1 &
SCHED_PID=$!
sleep 1

echo "Starting dask-worker connecting to localhost:$PORT"
nohup dask-worker localhost:$PORT > "$LOGDIR/worker.log" 2>&1 &
WORKER_PID=$!

echo "Scheduler PID: $SCHED_PID"
echo "Worker PID: $WORKER_PID"

echo "To stop: kill $SCHED_PID $WORKER_PID"
