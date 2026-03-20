Scripts in this directory

- dev-up.sh: Start backend, frontend, and optional local Dask scheduler/worker. Writes PIDs to `.moonstone/dev/pids/` and logs to `.moonstone/dev/logs/`.
- dev-down.sh: Stop MoonStone processes started by `dev-up.sh` (uses pidfiles and targeted port fallback).
- dev-status.sh: Show backend/frontend/Dask status from pidfiles and log locations.
- link_stardust.sh: Create an `npm link` from the StarDust frontend into MoonStone's frontend.

Diagnostics:
- diagnostics/env_check.sh: checks Python, Node, and CUDA helpers and prints status.
- diagnostics/run_tests.sh: runs `pytest -q` for the repository.
- diagnostics/frontend_check.sh: verifies frontend `npm ci` and attempts a build or lint.
- diagnostics/gpu_check.sh: checks `nvidia-smi` and `stardust.gpu` availability.
- diagnostics/health_check.sh: runs all diagnostics and writes `health_summary.json`.

Usage:
- Make scripts executable: `chmod +x scripts/*.sh scripts/diagnostics/*.sh`
- Start dev environment: `scripts/dev-up.sh`
- Stop dev environment: `scripts/dev-down.sh`
- Show status: `scripts/dev-status.sh`
- Run quick checks: `scripts/diagnostics/env_check.sh`
- Full health report: `scripts/diagnostics/health_check.sh`

Optional environment flags:
- `MOONSTONE_SKIP_BACKEND=1` — start frontend only (useful with remote backend).
- `MOONSTONE_API_BASE_URL=http://host:8000` — set API base URL passed to frontend (`VITE_API_BASE`).
- `MOONSTONE_NO_OPEN=1` — do not auto-open browser.
- `MOONSTONE_DEV_DOWN_AGGRESSIVE=1` — also run aggressive process cleanup by repo path.
