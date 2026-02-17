# MoonStone Development Plan and Feature Roadmap

## High-Priority Features and Research Items

### 1. Observer and Lab Clock Features
- Add per-observer clocks and a global lab time.
- Allow assigning lab time for observers and display time dilation effects.
- **Viability:** Straightforward to add observer clock fields and UI. Time dilation requires metric-aware measure tool (see below).

### 2. Override StarDust Measure Tool for Time Dilation
- Replace standard Euclidean measure with proper time calculation in curved spacetime.
- Show time dilation visually and numerically when rendering non-Euclidean grids.
- **Status:** StarDust measure tool is currently Euclidean. Needs MoonStone override and metric access.
- **Best Path:** Subclass/override measure tool in MoonStone, inject metric field, and update UI to show proper time.

### 3. Grid Drawing and Simulation Frame Controls
- Determine how the grid is drawn and how it maps to the simulation frame.
- Identify which controls (cell size, grid dimensions, pixelation, etc.) affect the simulation frame.
- **Status:** Grid is currently drawn from metric field grid parameters. Controls exist but may need clarification and UI improvements.
- **Best Path:** Audit grid drawing code, document mapping, and expose relevant controls in UI.

### 4. Photon Trajectory Visualization
- Confirm all photon trajectories that can reach observer objects are drawn in the simulation frame.
- **Status:** Trajectory code exists but may not enumerate all possible paths.
- **Best Path:** Review geodesic solver and observer detection logic; add UI to show all valid paths.

### 5. GPU Integration for Realtime Light Mapping/Curvature
- Assess ability to use GPU for light mapping and metric calculations (for redraw on drag, grid precision, etc.).
- **Status:** POC CUDA kernels exist on the backend (backend/app/accelerated_cuda.py) and runtime detection is already implemented via `stardust.gpu.is_cuda_available()` and `GET /moon/gpu` — GPU is selectable but not production-ready.  
- **Best Path / Next Steps:**
  1. Add an automated "GPU smoke" backend route that runs a tiny kernel and returns correctness + timing (safe, short-running).  
  2. Add a dev script (MoonStone/scripts/diagnostics/gpu_check.sh) and a StarDust Admin UI card showing `is_cuda_available()` + smoke-test result.  
  3. If smoke-test passes, prototype offloading one expensive path (metric sampling or RK4 integration) to GPU and benchmark.
  4. Add fallbacks and feature-flagging so UX degrades to CPU when GPU unavailable.

### 6. Display Calculations for Light Trajectories
- Show equations/results for light trajectories between observer/source pairs (effective local metrics, transformation optics, etc.).
- **Status:** Visual-only today (photon overlay + color shift). Numeric/symbolic diagnostics are not exposed.
- **Best Path:** Add a detail panel that computes and displays per-path diagnostics (time-of-flight, redshift estimate, deflection angle). Make it available from the photon overlay tooltip or selection.

### 7. Redraw Code Path Refactor & User Control
- Replace hardcoded redraw logic with a configurable policy so expensive work is only performed when desired:
  - Implement a small observer/callback registry for redraw sinks (order: metric → photons → overlays).  
  - Add UI toggles/controls: `recalcOnZoom`, `recalcOnPan` (default: false for heavy jobs), `recalcOnDrag` (for interactive GPU-backed redraws), and a manual `Recompute` button / keybinding (suggested: F3).  
  - Provide an explicit `overlayCacheRef` invalidation API for downstream extensions.
- **Current behavior / viability notes:**
  - MoonStone already caches world-space overlays (`overlayCacheRef`) and uses `recalcOnZoom` to avoid recompute on zoom; grid/photon world data is independent of pan (so panning does not require recompute).  
  - StarDust's `renderCanvas2dOverlays` currently does NOT include `isPanning` in its ctx — adding `isPanning` (or `viewCenter`) to that ctx is a backward-compatible change that enables downstream apps to suppress expensive recompute during pan/drag.
- **Best Path / Concrete changes:**
  1. Extend StarDust's `renderCanvas2dOverlays` ctx to include `isPanning` and `viewCenter` (minimal API addition).  
  2. Add `recalcOnPan` / `recalcOnDrag` toggles + manual `Recompute` button in MoonStone UI (located in `extensions.toolsExtra` of `MoonStone/frontend/src/App.tsx`).  
  3. Implement a small redraw registry (observer pattern) in StarDust so other downstream apps can register sinks.

---
+### Admin UI & Lightweight Instrumentation (NEW — high priority)
+- Goal: surface runaway/expensive work quickly and allow low-friction ops (throttle/inspect/trim).  
+- Rationale: recent hard-shutdown incident shows lack of runtime visibility; low-effort instrumentation prevents future outages.  
+- What to add (short-term):
  - Backend: expose `/moon/admin/compute-stats` returning semaphore queue depth, active tasks, counters (requests rejected by MAX_METRIC_GRID_POINTS), and a `POST /moon/admin/prune-metric-fields` endpoint.  
  - Frontend: reuse StarDust's existing `ResourceMonitor` and add a small `Admin / Compute` card in MoonStone (use `ResourceMonitor` + custom stats).  
  - Metrics: simple in-process counters + short lifetime gauges (no external telemetry required initially).
+- Implementation files: 
  - Backend: update `backend/app/traces.py` or add `backend/app/admin_api.py`; read semaphore state from `metric_fields_api` globals.  
  - Frontend: add `Admin` panel in `MoonStone/frontend/src/App.tsx` (reuse `ResourceMonitor` from `@stardust/ui`).
+- Benefit: immediate visibility, ability to throttle or prune metric fields, and reduce operational risk.

+### Pruning / Storage Policy (NEW — short term)
+- Add configurable TTL or max-count cleanup for `metric_fields` storage (server-side cron or on-write pruning).  
+- Suggested defaults: max 500 entries OR 30 days TTL; expose an admin endpoint and CLI utility to force prune.

+---
+## Immediate recommended next steps (proposed priority)
+1. Instrumentation + Admin UI (low-effort, high value) — implement backend `/moon/admin/compute-stats` + small MoonStone admin card.  ✅ recommended
+2. Add pruning policy for `metric_fields` (prevent disk growth).  
+3. GPU availability smoke-test (run `stardust.gpu.is_cuda_available()` + small kernel) and add GPU-smoke endpoint + UI badge.  
+4. Redraw refactor (observer pattern + `isPanning` in overlay ctx) — medium effort; follow after (1)-(3).
+
+These updates will be added to the backlog and tracked as discrete PRs.

### 8. Minimize Metric Storage
- Avoid storing metrics for Undo/Redo; recompute from baseline metric and object properties.
- **Status:** Metrics are currently stored per field.
- **Best Path:** Refactor undo/redo to store only object state and baseline metric reference.

## Desired Features (Tracking)
- Insert and manipulate objects in generic spacetime (mass-energy, geometry, momentum, spin, etc.), yielding curvature and frame drag.
- Calculate transformation optics results in realtime or on command, accounting for light waveforms and polarizations (exportable to SunStone).
- Enable advanced simulations via RunPanel and backend: mass+mass dynamics, robust photon trajectories, precise metrics, gravitational radiation.
- Load metrics and gravitational waveforms from backend simulators:
  - Load baseline metric; treat new objects as perturbations or run new backend jobs.
  - Load/edit gravitational waveforms as objects; allow phase, polarization, intensity adjustment.
- Auto-generate simulation reports as Jupyter notebooks with templates for graphing, animation, and code editing (frame rate, time window, camera angle, etc.).

## Implementation Order (Recommended)
1. Audit and document grid drawing and simulation frame controls.
2. Add observer/lab clocks and UI for time dilation.
3. Override measure tool for proper time in curved spacetime.
4. Refactor redraw logic to observer pattern and add user controls.
5. Review photon trajectory code and ensure all valid paths are visualized.
6. Add UI for displaying light trajectory calculations.
7. Research/prototype GPU integration for expensive calculations.
8. Refactor undo/redo to minimize metric storage.
9. Continue tracking and prioritizing advanced features as above.

---

**This plan should be updated as features are implemented or requirements change.**
