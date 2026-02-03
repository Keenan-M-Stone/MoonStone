# Methods & Mathematical Foundations

## Overview
This document summarizes the software stack, mathematical models, derivations implemented in MoonStone, and the recommended tests to validate correctness and trustworthiness. It also documents the bundle format (`.moonstone.bundles`) used to share simulation setups.

---

## Software Stack
- Backend: Python 3.x, FastAPI, pytest.
- Frontend: React (Vite), TypeScript, Three.js.
- Acceleration: Numba (`njit`) on CPU and Numba-CUDA on devices with CUDA.
- Utilities: NumPy, SciPy (where needed), Matplotlib for analysis notebooks.

---

## Mathematical Methods

### Kerr-Schild Metric (Cartesian form)
We use the Kerr-Schild representation:

g_{\mu\nu} = \eta_{\mu\nu} + 2 H(x^i) l_{\mu} l_{\nu}

- H(r) = M r^3 / (r^4 + a^2 z^2)
- l_{\mu} are the Kerr-Schild null components (function of r, x,y,z and spin parameter a)

Our code implements:
- Newton iteration to recover `r(x,y,z)` from the quartic equation for Cartesian coordinates.
- Analytic partials dr/dx, dr/dy, dr/dz via implicit differentiation of the quartic (used in both CPU formal integrator and the device analytic kernel).
- dH/dx and dl/dx computed analytically from the above partials.

### Christoffel Symbols & Geodesic Equation
We compute acceleration as:

a^{\mu} = -\Gamma^{\mu}_{\alpha\beta} u^{\alpha} u^{\beta}

- On CPU (formal integrator): compute dg/dx_j using analytic dH/dx and dl/dx, invert g to get g^{\mu\nu}, build \Gamma and contract with u.
- On GPU (analytic device kernel): the same computation is performed in-device to avoid finite-difference noise and improve accuracy.

### Integrators
- RK4 fixed-step integrator for both position-only (POC) and full 4-velocity integration.
- Adaptive RK4 (step-doubling) for `rk4_adaptive` with simple error estimate.

---

## Tests & Trustworthiness Suite
Include the following lightweight tests (CI-friendly):

1. **Flat-space sanity**: traces are straight lines (numerical error ~0).
2. **Schwarzschild small-deflection**: measure deflection angle for impact parameter `b` and compare to analytic formula \(\Delta\phi \approx 4M/b\) in the weak-field regime.
3. **Nullness checks**: verify `g_{\mu\nu} u^{\mu} u^{\nu} ~ 0` for null geodesics integrated with `null_formal`.
4. **Photon sphere radius (Schwarzschild)**: verify circular photon orbit radius at r = 3 M by constructing near-circular rays in the equatorial plane and checking orbit radius.
5. **Kernel parity checks**: CPU formal vs GPU analytic kernel consistency tests (skipped in CI if CUDA absent).
6. **Provenance tests**: verify `meta` contains `device_analytic_requested` and `device_analytic_executed` flags and they reflect runtime behavior.

A companion Jupyter notebook (`docs/methods_notebook.ipynb`) contains runnable examples and plots comparing computed traces to analytic expectations.

---

## Bundles (.moonstone.bundles)
Place shareable simulation bundles (JSON) into `.moonstone.bundles/`.
Format example (see `.moonstone.bundles/default_simulation.json`):

```
{
  "name": "example_kerr_formal",
  "description": "Single-ray Kerr formal analytic device run",
  "source": {"x": 10.0, "y": 0.0, "z": 0.0},
  "directions": [{"x": -1.0, "y": 0.0, "z": 0.0}],
  "metric": {"type": "schwarzschild", "mass": 1.0},
  "params": {"method": "kerr_formal", "device": "gpu", "analytic": true, "npoints": 256}
}
```

The repo includes a small helper `backend/app/bundle_utils.py` with `save_bundle` and `load_bundle` for convenient import/export of these bundles.

---

## Notes on Derivations & Attributions
- Kerr-Schild, Kerr metric, and standard Christoffel expressions are textbook material (see e.g., Misner/Thorne/Wheeler). Where we performed algebraic manipulation (implicit differentiation of the quartic for dr/dx), those derivations are implemented in `app.geodesics` and tests reference the numeric results.

---

For questions about any derivation or to request a symbolic expansion of the full Christoffel components for device hardcoding, open an issue and we can prioritize codegen + verification steps.
