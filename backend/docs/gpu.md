GPU Acceleration (POC)

Overview

- The backend contains a POC CUDA-accelerated kernel module at `app/accelerated_cuda.py` which implements batched, per-ray sampling kernels for flat-space and a weak-field Schwarzschild deflection model.
- GPU kernels are optional and are used only when explicitly requested via the `device` parameter (set to `"gpu"` in request `params`) or when server-side logic chooses GPU-enabled batching.

How to check availability

- The API exposes a small endpoint: `GET /moon/gpu` which returns `{ "cuda": true }` when a CUDA-capable runtime (Numba+CUDA) is available and usable on the server.
- The shared helper `stardust.gpu.is_cuda_available()` is used throughout the code base to detect availability and provide consistent behavior.

How to use

- To request GPU execution for a trace, include `params: { "device": "gpu" }` in the `POST /moon/trace` request body. When available, the server will use the batched GPU kernel to compute all rays in a single call.
- To request the RK4 POC integrator (CPU or CUDA POC), set `params: { "method": "rk4" }`. This will select RK4-style stepping when available (CPU RK4 implemented; CUDA RK4 currently reuses the POC kernel path).
Fallbacks

- If CUDA is not available, the code falls back to existing CPU paths, which include Numba `njit` kernels (if Numba is installed) and pure-Python loops as a last resort.
- Tests are written to skip GPU-only assertions when CUDA is not present.

Dask GPU scheduling

- When a trace request includes `params: { device: 'gpu' }`, the server will prefer to schedule the batched job on Dask workers that advertise a `GPU` resource. This is done by submitting the batched trace function with `resources={'GPU': 1}` so that GPU-aware workers receive the task.
- To run GPU-accelerated workloads in a Dask cluster, start workers with a `--resources GPU=1` flag (or use a scheduler/orchestrator that advertises GPU resources on workers).

Notes

- The current GPU kernels are a POC and designed for benchmarking and batched sampling. A production-grade GPU solver will require adaptive integration, accuracy controls, and additional physical modeling.
- Contributions to improve the CUDA kernels (performance, correctness, and more metrics) are welcome and should include tests and small microbenchmarks.
