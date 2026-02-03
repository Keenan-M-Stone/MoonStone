"""Metric and constitutive mapping utilities for MoonStone.

This module provides simple metric definitions (flat, Schwarzschild) and
an illustrative Plebanski-type mapping from a 4D metric to a 3x3
constitutive tensor (epsilon/mu and magneto-electric coupling xi).

Notes:
- The implementation here is intentionally simple and intended for a
  well-documented POC. For production or research use the mapping must
  be reviewed and replaced with a rigorous implementation following the
  sign/unit conventions in Hehl & Obukhov, Plebanski et al.
- GPU/Dask acceleration targets will operate on the sampling grid and
  can call these functions per-point.
"""
from typing import Tuple, Dict
import numpy as np

# NOTE: use geometric (G=c=1) units or document unit choices clearly.


def schwarzschild_metric(point: Tuple[float, float, float], mass: float) -> np.ndarray:
    """Return a 4x4 Schwarzschild metric in isotropic-like coordinates for POC.

    This is a simplified, static spherically-symmetric metric centered at origin.
    We return g_{mu nu} as a numpy array with signature (+,-,-,-) for convenience
    in downstream formulas (the mapping functions assume a positive time component).
    """
    x, y, z = point
    r = np.sqrt(x * x + y * y + z * z) + 1e-12
    m = float(mass)
    # Isotropic radial factor (approximate) — simple POC form
    rs = 2.0 * m
    f = 1.0 - rs / r
    g = np.zeros((4, 4), dtype=float)
    g[0, 0] = f
    invf = 1.0 / f
    g[1, 1] = -invf
    g[2, 2] = -invf
    g[3, 3] = -invf
    return g


def flat_metric(_: Tuple[float, float, float]) -> np.ndarray:
    g = np.diag([1.0, -1.0, -1.0, -1.0])
    return g


def plebanski_mapping(metric: np.ndarray) -> Dict[str, np.ndarray]:
    """Compute a Plebanski-style constitutive mapping for a 3+1 split.

    Returns a dict with keys 'eps' (3x3 permittivity), 'mu' (3x3 permeability),
    and 'xi' (3x3 magneto-electric coupling). This is a POC/formal mapping
    (not optimized) suitable for unit testing and visualization.
    """
    # metric: 4x4 g_{mu nu}
    g = metric
    # Validate shape
    if g.shape != (4, 4):
        raise ValueError('metric must be 4x4')

    # Compute inverse metric g^{mu nu}
    ginv = np.linalg.inv(g)

    # Determinant sign/scale
    detg = np.linalg.det(g)
    sign = np.sign(detg) if detg != 0 else 1.0

    # Extract spatial block g_{ij} and time-time g_{00}
    g00 = g[0, 0]
    gij = g[1:4, 1:4]
    gij_inv = np.linalg.inv(gij)

    # A simple Plebanski-inspired mapping (POC):
    # eps^{ij} = -sqrt(|g|)/g00 * g^{ij}
    factor = -np.sqrt(abs(detg) + 1e-30) / (g00 + 1e-30)
    eps = factor * gij_inv
    mu = factor * gij_inv
    # For POC keep xi small; proper mapping derives from g_{0i} components
    xi = np.zeros((3, 3), dtype=float)

    return {'eps': eps, 'mu': mu, 'xi': xi}


# Utility: sample constitutive tensor for a metric name + params
def constitutive_at(point: Tuple[float, float, float], metric_cfg: Dict) -> Dict[str, np.ndarray]:
    mtype = metric_cfg.get('type', 'flat')
    if mtype == 'schwarzschild':
        mass = metric_cfg.get('mass', 1.0)
        g = schwarzschild_metric(point, mass)
    else:
        g = flat_metric(point)
    return plebanski_mapping(g)
