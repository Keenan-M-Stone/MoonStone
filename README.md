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

```bash
python -m pip install nbconvert jupyter
jupyter nbconvert --to notebook --execute docs/methods_notebook.ipynb --ExecutePreprocessor.timeout=120

## Metric Field Import/Export (baseline grids)

MoonStone supports importing a baseline spacetime metric sampled on a regular 3D grid.
This is intended as the first step toward workflows like:

- Import external (NR / offline) metric solutions as a baseline.
- Sample Plebanski/Boston constitutive tensors on-demand via `/moon/metric`.
- Later compose analytic “object” perturbations on top of the baseline.

Current scope:
- Supported now: constitutive sampling at points (`/moon/metric`) with `metric.type='field'`.
- Not supported yet: geodesic tracing or run solvers over field metrics (requests are rejected rather than silently traced as flat).

Modified gravity / alternative models:
- MoonStone does not currently solve field equations (GR or otherwise) to produce metrics from stress-energy.
- If you want a modified-gravity model, supply the metric directly via `metric.type='field'` or `metric.type='matrix'` and treat `metric.gravity_model` as metadata.
- The constitutive mapping assumes transformation-optics conventions (Plebanski/Boston) and does not enforce that the metric satisfies any particular equations.

### File Format

Each imported field is stored as a directory `backend/app/metric_fields/<id>/` containing:

- `meta.json`: grid metadata
- `data.npz`: numpy archive with array `g` of shape `(nx, ny, nz, 4, 4)` containing covariant metric components $g_{\mu\nu}$

Example `meta.json`:

```json
{
	"version": 1,
	"kind": "metric_field",
	"id": "<server-assigned>",
	"coord_system": "cartesian",
	"grid": {
		"origin": [0.0, 0.0, 0.0],
		"spacing": [0.1, 0.1, 0.1],
		"shape": [64, 64, 64],
		"order": "xyz"
	},
	"components": "g_cov",
	"signature": "-+++"
}
```

### API Endpoints

- `POST /moon/metric-field` (multipart form-data): upload `meta` (JSON) and `data` (NPZ)
- `GET /moon/metric-fields`: list field ids
- `GET /moon/metric-field/{id}/meta`: fetch metadata
- `GET /moon/metric-field/{id}/data`: download `data.npz`
- `DELETE /moon/metric-field/{id}`: delete

To sample constitutive tensors from an imported field, call `/moon/metric` with:

```json
{
	"point": {"x": 0.0, "y": 0.0, "z": 0.0},
	"metric": {"type": "field", "field_id": "<id>", "mapping": "sunstone"}
}
```

### Discoverability for Generic Editors

- `GET /moon/metric-registry`: lists supported metric types and mapping conventions
- `POST /moon/metric/validate`: returns normalized configs + warnings to guide users before running
```

## Development Checklist (current gaps)
- [ ] Symbolic expansion & device hard-coding of full Christoffel components on-device for maximum fidelity and performance.
- [ ] Waveform extraction & transformation-optics export path (planned module and exporter).
- [ ] Advanced GPU profiling and micro-optimizations for CUDA kernels.
- [ ] More exhaustive CI coverage for GPU-only tests (depends on runner availability).
- [ ] Advanced settings dialog to hide experimental/rare toggles while keeping the default UI minimal.
- [ ] Hertzsprung–Russell (HR) diagram helper for inserting/selecting stars (mass presets + light sources with approximate spectra).
- [ ] Allow sources/observers to be “pinned” to massive objects (CAD grouping/parenting so they move/manipulate together).

## License

MoonStone is licensed under the MIT License. See:

- `LICENSE`
- `THIRD_PARTY_NOTICES.md`
- `ATTRIBUTION.md`
