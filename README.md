# MoonStone

MoonStone — interactive GUI and computation pipeline for general relativistic ray-tracing and Plebanski constitutive mapping.

This repository is a starting scaffold created from the SunStone project. It contains:

Note: The frontend uses the `@stardust/ui` package (StarDust) as a minimal CAD UI framework that provides an application frame, menu bar, tools/inspector panels and a `CADCanvas` mount point for Three.js. See `StarDust/frontend/README.md` for details and demo.

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

## Running tests & notebooks
- Run unit tests: `pytest -q`
- Run the methods/test notebook (if you have `nbconvert` and `jupyter` installed):

```bash
python -m pip install nbconvert jupyter
jupyter nbconvert --to notebook --execute docs/methods_notebook.ipynb --ExecutePreprocessor.timeout=120
```

## Development Checklist (current gaps)
- [ ] Symbolic expansion & device hard-coding of full Christoffel components on-device for maximum fidelity and performance.
- [ ] Waveform extraction & transformation-optics export path (planned module and exporter).
- [ ] Advanced GPU profiling and micro-optimizations for CUDA kernels.
- [ ] More exhaustive CI coverage for GPU-only tests (depends on runner availability).

License: MIT (see `LICENSE`).
