# MoonStone

MoonStone — interactive GUI and computation pipeline for general relativistic ray-tracing and Plebanski constitutive mapping.

This repository is a starting scaffold created from the SunStone project. It contains:

- `frontend/` — Vite + React + TypeScript frontend (UlfPanel stub, Three.js integration)
- `backend/` — Python (FastAPI) backend with Dask-ready trace worker and a Schwarzschild POC
- `docs/` — design & roadmap adapted from SunStone's Ulf design

Goal: enable fast, interactive simulation and visualization of null geodesics and metric→constitutive tensor mappings. For heavy compute we use Python + Dask and optional Numba/CUDA and C++ kernels for acceleration. For interactive responsiveness we provide a low-cost fast-mode trace + disk cache (backend) and a refine flow for high-fidelity results.

Quick start (backend):

```bash
conda activate moonstone
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Start the frontend (development):

```bash
cd frontend
npm ci
npm run dev
```

License: MIT (see `LICENSE`).
