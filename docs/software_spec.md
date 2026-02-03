# MoonStone Software Specification

## Overview
This document describes the UI components, controls, settings, available solvers, how to access them, and a troubleshooting guide for common error messages.

---

## UI Components & Controls ✅

- **Main View / Scene Canvas**
  - Renders rays, sources, and metric samples using Three.js.
  - Camera controls: orbit/zoom/pan via standard mouse gestures.

- **Scene List**
  - Multiple scenes can be created and switched between.
  - Each scene stores solver selection, quick settings, and object list.

- **Source Panel**
  - Controls: Source X/Y/Z (numeric inputs) — sets emitter location.
  - Update triggers a new trace (debounced).

- **Metric Panel**
  - Type selector: `flat`, `schwarzschild` (future: `kerr`)
  - Schwarzschild: Mass input.
  - Sample metric tensors at observer location.

- **Observer Panel**
  - X/Y/Z for sampling constitutive tensors.
  - Button: "Sample Tensor" to request /moon/metric.

- **Quick Solver (Quick Editor)**
  - Quick solver selector: `weak` (fast), `rk4`, `rk4_adaptive`, `null`, `null_formal`, `kerr_formal`.
  - Quick Settings (per-scene):
    - `engine`: `approx` | `formal`
    - `device`: `cpu` | `gpu`
    - `spin`: spin vector for Kerr solver
    - `use_numba`: boolean CPU accel
    - **`analytic_device`**: boolean — when set, GPU Kerr path will try the analytic Christoffel device kernel (if available)

- **Trace Controls**
  - Update Trace, Refine Trace, Export buttons.
  - Streaming trace via WebSocket with progress indicator.

- **Bench Dashboard**
  - Run micro-benchmarks for selected solvers.
  - View historical per-solver timing.

- **Status & Meta Display**
  - Shows whether the last trace used an analytic device kernel (requested/executed), caching info, and any warnings.

---

## Solvers & How to Use 🔧

- **`weak`**: Fast approximate Schwarzschild weak-field deflection. Use for interactive previews.
  - Access: Quick Solver -> Weak; or POST `/moon/trace` with `params.method` absent or `weak`.

- **`rk4`**: Simple RK4 spatial integrator for demoing curvature effects.
  - Access: `params.method = 'rk4'`.

- **`rk4_adaptive`**: Adaptive step RK4 (step-doubling). Use for improved accuracy with moderate cost.
  - Access: `params.method = 'rk4_adaptive'`.

- **`null`**: Simplified null geodesic POC with approximated Christoffel.
  - Access: `params.method = 'null'`.

- **`null_formal`**: Post-Newtonian Schwarzschild null geodesic integrator computing Christoffel analytically (CPU).
  - Access: `params.method = 'null_formal'` or set `engine: 'formal'` in quick settings.

- **`kerr_formal`**: Kerr-Schild Cartesian formal integrator (CPU) computing Christoffel (finite-difference or analytic partials depending on method/device).
  - Access: `params.method = 'kerr_formal'`.
  - Device switch: `params.device = 'gpu'` will attempt GPU batch kernels when available.
  - `params.analytic = true` requests the analytic device kernel if using GPU (runtime-executed provenance is reported).

- **Accelerated paths**
  - CPU: Numba `njit` implementations (if `use_numba` is true).
  - GPU: Numba-CUDA kernels when `device = 'gpu'` and CUDA available. When `kerr_formal` + `analytic`, the kernel computes analytic dr/dx, dH/dx, dl/dx and forms Christoffel contractions on-device.

---

## Access & APIs
- HTTP: POST `/moon/trace` — body: { source, directions, metric, params }
  - Response `meta` includes: `cached`, `num_dirs`, `metric`, `device_analytic_requested`, `device_analytic_executed` (when applicable).
- WebSocket: `/moon/trace/ws` — streaming partials include `meta` with provenance flags in each partial and the done message.
- GPU status: GET `/moon/gpu` returns `{cuda: true|false}`.
- Benchmarks: POST `/moon/bench` and GET `/moon/bench/history`.

---

## Troubleshooting Guide 🛠️

- Error: **CUDA not available / GPU missing**
  - Cause: No CUDA-capable device or missing drivers/libraries.
  - Action: Ensure drivers + CUDA toolkit installed; verify with `nvidia-smi` and server-side `stardust.gpu.is_cuda_available()`; fallback to CPU or run on a machine with CUDA.

- Error: **Dask submit failure / remote worker unavailable**
  - Cause: No running Dask scheduler or misconfigured resources.
  - Action: Confirm Dask scheduler is running and that `resources: {'GPU':1}` matches resource labels. App falls back to local computation when Dask fails.

- Warning: **Analytic kernel requested but executed=False**
  - Cause: The analytic device kernel raised an exception or was not chosen at runtime.
  - Action: Inspect server logs for kernel stacktrace; try `analytic=false` to use approximate path; check GPU health and driver logs.

- Error: **WebSocket disconnected / partials stop**
  - Cause: Network blip, client disconnect, or server-side exception.
  - Action: Reconnect; monitor server logs; run the single-shot `/moon/trace` endpoint as fallback.

- Error: **Trace result appears cached unexpectedly**
  - Cause: Cache key matched previous request parameters.
  - Action: Modify params or include a distinguishing tag (or clear cache on server) and re-run.

- Error: **Server HTTP 5xx**
  - Cause: Internal server exception.
  - Action: Check server logs and the exception stacktrace; reproduce request with minimal params and escalate.

---

If you encounter other issues, collect request payload and server logs and open an issue with the trace `meta` and logs.
