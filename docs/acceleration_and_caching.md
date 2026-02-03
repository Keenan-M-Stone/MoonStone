# Acceleration & Caching (POC)

This document summarizes the early approach used by MoonStone for making interactive tracing and constitutive mapping responsive.

Key ideas
- Fast interactive mode: use approximate solvers (weak-field approximations, lower-resolution sampling) to provide instant visual feedback while the user drags sources/objects.
- Refinement: provide an explicit "Refine Trace" action that requests a higher-resolution/high-fidelity trace which will replace the low-res one when ready.
- Caching: deterministic per-request keys are computed from the trace request (source, directions, metric, params) and stored on-disk in `backend/cache/` as pickled objects. Cache hits are returned immediately.
- Acceleration:
  - CPU JIT via `Numba` (POC in `backend/app/accelerated.py`) for low-latency hot loops.
  - Distributed batching using `Dask` — the service will attempt to create a local `Client` by default and will submit ray directions parallelized across workers.
  - For GPU acceleration, consider Numba CUDA or JAX/CuPy kernels for array-based integrators; these require additional development and device-dependent packaging.

Developer notes
- Start a local Dask scheduler & worker for development:

```bash
./backend/scripts/start_dask_local.sh
```

- Numba is optional; if Numba is not available the accelerated kernels are skipped. Use the `moonstone` conda environment to ensure `numba` is installed.

Next steps
- Replace the simplistic Plebanski mapping with a rigorously validated implementation and add GPU-friendly batch kernels.
- Add an LRU eviction policy for the cache and optionally move to HDF5 for larger trace datasets.
- Add progressive streaming of trace results to the frontend (WebSocket) so partial results can be displayed while traces compute.
