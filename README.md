# MoonStone

MoonStone — interactive GUI and computation pipeline for general relativistic ray-tracing and Plebanski constitutive mapping.

This repository is a starting scaffold created from the SunStone project. It contains:

- `frontend/` — Vite + React + TypeScript frontend (UlfPanel stub, Three.js integration)
- `backend/` — Python (FastAPI) backend with Dask-ready trace worker and a Schwarzschild POC
- `docs/` — design & roadmap adapted from SunStone's Ulf design

Goal: enable fast, interactive simulation and visualization of null geodesics and metric→constitutive tensor mappings. For heavy compute we plan to use Python + Dask and optional C++/GPU acceleration in later phases.

License: MIT (see `LICENSE`).
