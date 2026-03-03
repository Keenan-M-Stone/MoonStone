# MoonStone Development Plan and Feature Roadmap

## High-Priority Features and Research Items

Note: This section is a thematic list of high-value items; see "Immediate recommended next steps" for near-term sequencing.

### 1. Observer and Lab Clock Features

- Add per-observer clocks and a lab-reference (asymptotic) time.
- Allow assigning lab time for observers and display time dilation effects.
- **Viability:** Straightforward to add observer clock fields and UI. Time dilation requires metric-aware measure tool (see below).

**Terminology (GR intent):**

- **Lab time** is the reference time measured by an idealized observer sufficiently far from the simulated
  region that spacetime is effectively flat (an asymptotic/inertial reference). It acts as the canonical
  reference timeline for the UI and for comparing clocks.
- **Observer time** is the *proper time* accumulated along an observer's worldline inside the simulated
  (potentially curved) spacetime and will generally differ from lab time depending on the metric and the observer's trajectory.

### 2. Override StarDust Measure Tool for Time Dilation

- Replace standard Euclidean measure with proper time calculation in curved spacetime.
- Show time dilation visually and numerically when rendering non-Euclidean grids.
- **Status:** StarDust measure tool is currently Euclidean. Needs MoonStone override and metric access.
- **Best Path:** Subclass/override measure tool in MoonStone, inject metric field, and update UI to show proper time.

### 3. Grid Drawing and Simulation Frame Controls

- Determine how the grid is drawn and how it maps to the simulation frame.
- Identify which controls (cell size, grid dimensions, pixelation, etc.) affect the simulation frame.
- **Status:** Grid is currently drawn from metric field grid parameters. Controls exist but may need clarification and UI improvements.
- **Design intent / source of truth:**
  The resulting metric field is the source of truth. UI controls should edit *inputs/parameters* that produce the metric
  (baseline metric + object perturbations) and the renderer should visualize the metric-derived grid/curvature; when UI
  settings and metric parameters disagree, the metric wins.
- **Best Path:** Audit grid drawing code, document mapping (UI controls → metric params → rendered grid), and expose relevant controls in UI.

### 4. Photon Trajectory Visualization

- Confirm all photon trajectories that can reach observer objects are drawn in the simulation frame.
- **Status:** Trajectory code exists but may not enumerate all possible paths.
- **Best Path:** Review geodesic solver and observer detection logic; add UI to show all valid paths.

### 5. GPU Integration for Realtime Light Mapping/Curvature

- Assess ability to use GPU for light mapping and metric calculations (for redraw on drag, grid precision, etc.).
- **Status:** POC CUDA kernels exist on the backend (backend/app/accelerated_cuda.py)
   and runtime detection is already implemented via `stardust.gpu.is_cuda_available()`
   and `GET /moon/gpu` — GPU is selectable but not production-ready.  
- **Best Path / Next Steps:**
  1. Add an automated "GPU smoke" backend route that runs a tiny kernel and returns correctness + timing (safe, short-running).  
  2. Add a dev script (MoonStone/scripts/diagnostics/gpu_check.sh) and a Resource/Compute monitor card showing
    `is_cuda_available()` + smoke-test result (prefer implementing the monitor UI as an opt-in StarDust panel so MoonStone/SunStone can reuse it).  
  3. If smoke-test passes, prototype offloading one expensive path (metric sampling or RK4 integration) to GPU and benchmark.
  4. Add fallbacks and feature-flagging so UX degrades to CPU when GPU unavailable.

### 6. Display Calculations for Light Trajectories

- Show equations/results for light trajectories between observer/source pairs (effective local metrics, transformation optics, etc.).
- **Status:** Visual-only today (photon overlay + color shift). Numeric/symbolic diagnostics are not exposed.
- **Best Path:**
  Add a detail panel that computes and displays per-path diagnostics (time-of-flight, redshift estimate, deflection angle).
  Make it available from the photon overlay tooltip or selection.

### 7. Redraw Code Path Refactor & User Control

- Replace hardcoded redraw logic with a configurable policy so expensive work is only performed when desired:
  - Implement a small observer/callback registry for redraw sinks (order: metric → photons → overlays).  
  - Add UI toggles/controls: `recalcOnZoom`, `recalcOnPan` (default: false for heavy jobs),
    `recalcOnDrag` (for interactive GPU-backed redraws), and a manual `Recompute` button / keybinding (suggested: F3).  
  - Provide an explicit `overlayCacheRef` invalidation API for downstream extensions.
- **Current behavior / viability notes:**
  - MoonStone already caches world-space overlays (`overlayCacheRef`) and uses `recalcOnZoom`
    to avoid recompute on zoom; grid/photon world data is independent of pan (so panning does not require recompute).  
  - StarDust's `renderCanvas2dOverlays` currently does NOT include `isPanning` in its ctx —
    adding `isPanning` (or `viewCenter`) to that ctx is a backward-compatible change that enables downstream apps
    to suppress expensive recompute during pan/drag.
- **Best Path / Concrete changes:**
  1. Extend StarDust's `renderCanvas2dOverlays` ctx to include `isPanning` and `viewCenter` (minimal API addition).  
  2. Add `recalcOnPan` / `recalcOnDrag` toggles + manual `Recompute` button in MoonStone UI
     (located in `extensions.toolsExtra` of `MoonStone/frontend/src/App.tsx`).  
  3. Implement a small redraw registry (observer pattern) in StarDust so other downstream apps can register sinks.

---

### Resource/Compute Monitor & Lightweight Instrumentation (NEW — high priority)

**Modularity intent:**
The Resource/Compute monitor UI should live in StarDust as an opt-in feature/panel so it can be
included or excluded per app (MoonStone, SunStone, future apps). MoonStone should provide
MoonStone-specific stats and routes; StarDust should remain domain-agnostic.

- Backend:
  - expose `/moon/admin/compute-stats` returning semaphore queue depth, active tasks, counters
  (requests rejected by MAX_METRIC_GRID_POINTS), and a `POST /moon/admin/prune-metric-fields` endpoint.
  - update `backend/app/traces.py` or add `backend/app/admin_api.py`; read semaphore state from `metric_fields_api` globals.  
- Frontend:
  - reuse StarDust's existing `ResourceMonitor` and add a small `Compute` card/panel entrypoint (in StarDust) that can render
    app-provided stats (MoonStone will provide `/moon/admin/compute-stats`).
  - in MoonStone, enable the panel and provide the MoonStone-specific stats wiring.
- Metrics:
  - simple in-process counters + short lifetime gauges (no external telemetry required initially).

**Access intent:** This is not dev-only.
Like SunStone, resource visibility should be available to all users of MoonStone so they can understand and control local resource usage.

**Naming note:**
The current route prefix uses `/moon/admin/...` for convenience, but the intended access model is user-facing resource monitoring.
Consider renaming to a neutral prefix (e.g. `/moon/compute/...`) if/when we harden auth and API shape.

**Crash/debug intent:** Prioritize signals that explain whole-machine instability (queue depth, active tasks,
estimated memory use, metric field count/bytes on disk, and recent prune activity) so we can diagnose why MoonStone
can destabilize the host.

---

## Immediate recommended next steps (proposed priority)

1. Instrumentation + Resource/Compute monitor (low-effort, high value) — implement backend `/moon/admin/compute-stats` + reusable monitor panel.
2. Add pruning policy for `metric_fields` (prevent disk growth).  
3. GPU availability smoke-test (run `stardust.gpu.is_cuda_available()` + small kernel) and add GPU-smoke endpoint + UI badge.  
4. Redraw refactor (observer pattern + `isPanning` in overlay ctx) — medium effort; follow after (1)-(3).

These updates will be added to the backlog and tracked as discrete PRs.

**Pruning policy intent (to prevent host crashes):** Pruning should be automatic by default (with a manual endpoint for debugging).
Prefer a simple, predictable policy such as a disk-budget cap and/or max-count of cached metric fields, optionally with an age/TTL backstop.

### 8. Minimize Metric Storage

- Avoid storing metrics for Undo/Redo; recompute from baseline metric and object properties.
- **Status:** Metrics are currently stored per field.
- **Best Path:** Refactor undo/redo to store only object state and baseline metric reference.

## Desired Features (Tracking)

- Insert and manipulate objects in generic spacetime (mass-energy, geometry, momentum, spin, etc.),
  yielding curvature and frame drag.
- Calculate transformation optics results in realtime or on command, accounting for light waveforms
  and polarizations (exportable to SunStone).
- Enable advanced simulations via RunPanel and backend:
  mass+mass dynamics, robust photon trajectories, precise metrics, gravitational radiation.
- Load metrics and gravitational waveforms from backend simulators:
  - Load baseline metric; treat new objects as perturbations or run new backend jobs.
  - Load/edit gravitational waveforms as objects; allow phase, polarization, intensity adjustment.
- Auto-generate simulation reports as Jupyter notebooks with templates for graphing, 
  animation, and code editing (frame rate, time window, camera angle, etc.).

## Implementation Order (Recommended)

1. Instrumentation + Resource/Compute monitor.
2. Add pruning policy for `metric_fields`.
3. GPU availability smoke-test + feature gating.
4. Audit and document grid drawing and simulation frame controls.
5. Add observer/lab clocks and UI for time dilation.
6. Override measure tool for proper time in curved spacetime.
7. Refactor redraw logic to observer pattern and add user controls.
8. Review photon trajectory code and ensure all valid paths are visualized.
9. Add UI for displaying light trajectory calculations.
10. Research/prototype GPU integration for expensive calculations.
11. Refactor undo/redo to minimize metric storage.
12. Continue tracking and prioritizing advanced features as above.

---

**This plan should be updated as features are implemented or requirements change.**

---

## What is needed (overview)

MoonStone should stay focused on General Relativity domain logic
(metrics, curvature visualization, proper-time tools, photon trajectories,
backend solver integration).  

StarDust should provide reusable, opt-in app infrastructure
(CAD canvas, property editors, and optionally the Resource/Compute monitor UI),
with MoonStone/SunStone supplying app-specific data and endpoints.

- A CAD interface where the user can make and place objects, observers, light sources
  (getting this from StarDust)
- A utility for editing the properties of those objects and elements (also getting most of this from StarDust)
  - Mass/Energy Density of objects
  - Geometric properties
  - Position in spacetime
  - Lab relative momentum vector
  - Spin (and possibly charge)
  - Gravitational Radiation Waveform properties (imported, calculated, or specified)
  - Visibility (on/off)
  - Color, Shading, Transparency, Gradient, etc
- A view where we render the curvature of the spacetime grid so that we can actually see
  how spacetime is curved by those objects. Options:
  - can make derived classes of visible grid frame in StarDust and show this instead of flat grid in the CAD editor canvas.
  - can have a separate viewport where we show how spacetime is curved by our simulation elements
- Wherever we are showing the curved spacetime grid, this is where we want to render the possible photon
  trajectories between light sources and observers.
  - Might be wise to also allow turning on/off observers and sources, so the user doesn't get overwhelmed.
- Ability to load and export metrics so that we can draw and modify spacetime configurations that are or aren't perfectly flat
  (wherever those are being shown) and treat elements we insert into them as perturbations to that base curvature.
