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
- **Status:** Currently CPU-bound; no GPU integration.
- **Best Path:** Research WebGL/WebGPU compute shaders or offload to backend; prototype for most expensive calculations.

### 6. Display Calculations for Light Trajectories
- Show equations/results for light trajectories between observer/source pairs (effective local metrics, transformation optics, etc.).
- **Status:** Not currently shown; only visualized.
- **Best Path:** Add UI panel or overlay to display symbolic/numeric results for selected observer/source pairs.

### 7. Redraw Code Path Refactor & User Control
- Replace hardcoded redraw logic with user-configurable observer pattern:
  - Implement observer pattern with registered sinks/sources for redraw callbacks.
  - Ensure callback order: metric curvature → light trajectories → constitutive tensors.
  - Add settings: redraw on drag (GPU may be needed), redraw on drop (multithreaded), redraw on command (keymap, e.g. F3).
- **Status:** Redraw is currently direct and not user-configurable.
- **Best Path:** Refactor to observer pattern, add settings UI, and document callback order.

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
