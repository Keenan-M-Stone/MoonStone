# MoonStone Roadmap

This document is an adaptation of SunStone's Ulf design and maps the phased plan for MoonStone.

## MVP Scope

Phase 1 — UI & model plumbing (short)
- `UlfPanel` React component (front-end) with scene graph, object editor, trace controls, and inspector.
- Units settings, scene persistence under `data_dir/moonstone/`.
- Data models: `SpacetimeObject`, `PhotonSource`, `TraceRequest`, `TraceResult`, `ConstitutiveTensorSample`.

Phase 2 — Simple metrics & visualization
- Schwarzschild (weak-field) POC, cylinder/cosmic-string placeholders.
- Renderer primitives and line renderer for rays (Three.js).

Phase 3 — Geodesic integrator & trace service
- FastAPI endpoints for `POST /moon/trace`, `GET /moon/trace/:id`, `GET /moon/metric/:id`, and `POST /moon/export`.
- Dask integration for parallel traces and heavy compute; optional C++/GPU acceleration hooks.

Phase 4 — Constitutive mapping & export
- Plebanski mapping implementation and sample exports (JSON/HDF5).

Phase 5 — Advanced metrics & performance
- Kerr support, JIT/GPU acceleration, caching, and batch processing.

Phase 6 — Advanced authoring & astrophysics helpers (later)
- Advanced settings dialog (keep default UI minimal; hide experimental toggles).
- Hertzsprung–Russell (HR) diagram helper for inserting/selecting stellar masses with light sources pinned to stars and initialized with approximate spectral presets.
- Allow emitters/observers to be “pinned” to massive objects (e.g., stars/planets/black holes): pinned = grouped/parented CAD objects so they can be moved/manipulated together (common for sources/observers inside gravity wells).

## Notes
- Backend: Python (FastAPI) + Dask. Compute-heavy kernels can be moved to C++ or GPU using pybind11/CUDA if necessary.
- Frontend: Vite + React + TypeScript with Three.js for 3D visualization. Real-time interactivity is prioritized.
