Scripts in this directory

- dev-up.sh: Start backend/frontend and optional local dask scheduler/worker. Writes PIDs to `scripts/pids/` and logs to `logs/`.
- dev-down.sh: Stop processes started by `dev-up.sh` (uses pidfiles and pkill fallback).

Diagnostics:
- diagnostics/env_check.sh: checks Python, Node, and CUDA helpers and prints status.
- diagnostics/run_tests.sh: runs `pytest -q` for the repository.
- diagnostics/frontend_check.sh: verifies frontend `npm ci` and attempts a build or lint.
- diagnostics/gpu_check.sh: checks `nvidia-smi` and `stardust.gpu` availability.

Usage:
- Make scripts executable: `chmod +x scripts/*.sh scripts/diagnostics/*.sh`
- Start dev environment: `scripts/dev-up.sh`
- Stop dev environment: `scripts/dev-down.sh`
- Run quick checks: `scripts/diagnostics/env_check.sh`
