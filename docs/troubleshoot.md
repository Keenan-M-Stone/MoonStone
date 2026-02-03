# Troubleshooting Quick Reference

This sheet collects common issues, their likely causes, and recommended actions.

- **CUDA not available**
  - Cause: Driver or CUDA Toolkit missing, or no GPU on host.
  - Action: Install drivers, ensure `nvidia-smi` reports a device; verify Python package `stardust.gpu` detects CUDA.

- **Kernel execution error: analytic kernel failed**
  - Cause: Device kernel hit an exception (unsupported math or memory), or runtime mismatch.
  - Action: Check server logs for stack trace. Retry with `params.analytic=false` to use approximate kernel; collect kernel logs for debugging.

- **Dask submission error**
  - Cause: Scheduler not reachable or resource mismatch.
  - Action: Ensure Dask scheduler is running and resources tag on workers match requested resources.

- **WebSocket disconnects prematurely**
  - Cause: Client network or server-side exception.
  - Action: Use the non-streaming `/moon/trace` endpoint to check payload correctness and server-side traceback.

- **Unexpected cached results**
  - Cause: Cache keys are computed from request payload; minor differences may still match.
  - Action: Add a unique tag to `params` to force recalculation or clear the cache on server.
