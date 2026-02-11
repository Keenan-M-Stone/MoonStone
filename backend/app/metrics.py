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
    We return g_{mu nu} as a numpy array with signature (-,+,+,+) to match the
    Plebanski mapping convention used by SunStone's ULF utilities.
    """
    x, y, z = point
    r = np.sqrt(x * x + y * y + z * z) + 1e-12
    m = float(mass)
    # Isotropic radial factor (approximate) — simple POC form
    rs = 2.0 * m
    f = 1.0 - rs / r
    g = np.zeros((4, 4), dtype=float)
    g[0, 0] = -f
    invf = 1.0 / f
    g[1, 1] = invf
    g[2, 2] = invf
    g[3, 3] = invf
    return g


def flat_metric(_: Tuple[float, float, float]) -> np.ndarray:
    g = np.diag([-1.0, 1.0, 1.0, 1.0])
    return g


def plebanski_mapping(metric: np.ndarray) -> Dict[str, np.ndarray]:
    """Compute Plebanski constitutive tensors (eps, mu, xi, zeta) from a 4x4 metric g_{μν}.

    Convention matches SunStone's `plebanski_from_metric` implementation:
    - metric signature assumed (-,+,+,+)
    - flat Minkowski gives eps=mu≈-I, xi=zeta≈0

    Returns numpy arrays (3x3) for keys: eps, mu, xi, zeta.
    """
    g4 = np.asarray(metric, dtype=float)
    if g4.shape != (4, 4):
        raise ValueError('metric must be 4x4')

    detg = float(np.linalg.det(g4))
    sqrt_neg_g = np.sqrt(abs(-detg))
    invg = np.linalg.inv(g4)

    # 3D Levi-Civita epsilon_{ijk}
    eps3 = np.zeros((3, 3, 3), dtype=float)
    eps3[0, 1, 2] = 1.0
    eps3[0, 2, 1] = -1.0
    eps3[1, 0, 2] = -1.0
    eps3[1, 2, 0] = 1.0
    eps3[2, 0, 1] = 1.0
    eps3[2, 1, 0] = -1.0

    eps_mat = np.zeros((3, 3), dtype=float)
    mu_mat = np.zeros((3, 3), dtype=float)
    xi_mat = np.zeros((3, 3), dtype=float)
    zeta_mat = np.zeros((3, 3), dtype=float)

    def compute_H_from_F(F: np.ndarray) -> np.ndarray:
        # H^{μν} = sqrt(-g) g^{μα} g^{νβ} F_{αβ}
        return sqrt_neg_g * (invg @ F @ invg.T)

    # Basis for electric inputs: F_{0j} = 1
    for j in range(3):
        F = np.zeros((4, 4), dtype=float)
        F[0, j + 1] = 1.0
        F[j + 1, 0] = -1.0
        H = compute_H_from_F(F)
        D = H[0, 1:4].copy()  # D^i = H^{0i}
        B = np.zeros(3, dtype=float)
        for i in range(3):
            s = 0.0
            for p in range(3):
                for q in range(3):
                    s += 0.5 * eps3[i, p, q] * H[p + 1, q + 1]
            B[i] = s
        eps_mat[:, j] = D
        zeta_mat[:, j] = B

    # Basis for magnetic inputs: F_{kl} = -epsilon_{klj}
    for j in range(3):
        F = np.zeros((4, 4), dtype=float)
        for k in range(3):
            for l in range(3):
                F[k + 1, l + 1] = -eps3[k, l, j]
        F = 0.5 * (F - F.T)
        H = compute_H_from_F(F)
        D = H[0, 1:4].copy()
        B = np.zeros(3, dtype=float)
        for i in range(3):
            s = 0.0
            for p in range(3):
                for q in range(3):
                    s += 0.5 * eps3[i, p, q] * H[p + 1, q + 1]
            B[i] = s
        xi_mat[:, j] = D
        mu_mat[:, j] = B

    return {'eps': eps_mat, 'mu': mu_mat, 'xi': xi_mat, 'zeta': zeta_mat}


# Utility: sample constitutive tensor for a metric name + params
def constitutive_at(point: Tuple[float, float, float], metric_cfg: Dict) -> Dict[str, np.ndarray]:
    mtype = metric_cfg.get('type', 'flat')
    if mtype == 'schwarzschild':
        mass = metric_cfg.get('mass', 1.0)
        g = schwarzschild_metric(point, mass)
    else:
        g = flat_metric(point)
    return plebanski_mapping(g)
