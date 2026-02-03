# MoonStone Backend

This folder contains a FastAPI-based proof-of-concept trace service used by MoonStone's frontend.

Run locally (recommended using the `moonstone` conda environment):

```bash
conda activate moonstone
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Key endpoints (POC):
- `POST /moon/trace` — submit a `TraceRequest` and return a sampled `TraceResult`.
- `GET /moon/trace/{id}` — retrieve a stored trace.
- `POST /moon/metric` — compute Plebanski-style constitutive tensors (`eps`, `mu`, `xi`) at a 3D point for a metric.
- `POST /moon/export` — export sampled constitutive tensors along a previously computed trace.

Dask acceleration:
- The service attempts to use Dask (local client by default) for parallelizing trace directions.
- For larger workloads, run a Dask scheduler & workers (e.g., via `dask-scheduler` + `dask-worker`) and configure the service
  to connect to the cluster.

Notes:
- All metric/constitutive implementations here are POCs; replace with rigorous implementations for production/research use.
- See `backend/tests` for unit tests that validate basic behavior.
