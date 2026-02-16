"""Numerical curvature utilities.

MoonStone currently treats metrics as user-supplied (analytic, matrix, field) and
does not solve field equations (GR or modified gravity) in general.

This module provides an *approximate* point-sampled curvature diagnostic for
static metrics g_{μν}(x,y,z) with ∂_t g = 0. It is intended for:

- sanity checks (e.g. flat metric => ~0 curvature)
- interactive exploration of imported metric fields

Important limitations:
- time derivatives are assumed zero
- finite difference step size matters; results are not guaranteed stable
- boundary handling clamps to one-sided differences
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Tuple

import numpy as np


MetricFn = Callable[[Tuple[float, float, float]], np.ndarray]


@dataclass(frozen=True)
class CurvatureResult:
    ricci_scalar: float
    metric_det: float


def _finite_diff_metric_derivs(metric_at: MetricFn, p: Tuple[float, float, float], h: float) -> np.ndarray:
    """Compute ∂_i g_{μν} for i in {x,y,z} via central differences."""
    x, y, z = (float(p[0]), float(p[1]), float(p[2]))
    dg = np.zeros((3, 4, 4), dtype=float)
    for i, dp in enumerate(((h, 0.0, 0.0), (0.0, h, 0.0), (0.0, 0.0, h))):
        px = (x + dp[0], y + dp[1], z + dp[2])
        mx = (x - dp[0], y - dp[1], z - dp[2])
        gp = metric_at(px)
        gm = metric_at(mx)
        dg[i] = (gp - gm) / (2.0 * h)
    return dg


def _christoffel(g: np.ndarray, dg_xyz: np.ndarray) -> np.ndarray:
    """Compute Γ^ρ_{μν} for static metrics using only spatial derivatives."""
    g = np.asarray(g, dtype=float)
    if g.shape != (4, 4):
        raise ValueError('g must be 4x4')
    invg = np.linalg.inv(g)

    def d_g(coord_index: int, a: int, b: int) -> float:
        # coord_index: 0=t, 1=x, 2=y, 3=z; we assume d/dt = 0.
        if coord_index == 0:
            return 0.0
        return float(dg_xyz[coord_index - 1, a, b])

    Gamma = np.zeros((4, 4, 4), dtype=float)
    for rho in range(4):
        for mu in range(4):
            for nu in range(4):
                s = 0.0
                for sigma in range(4):
                    term = d_g(mu, sigma, nu) + d_g(nu, sigma, mu) - d_g(sigma, mu, nu)
                    s += invg[rho, sigma] * term
                Gamma[rho, mu, nu] = 0.5 * s
    return Gamma


def _ricci_scalar(metric_at: MetricFn, p: Tuple[float, float, float], h: float) -> CurvatureResult:
    """Compute Ricci scalar R at p using finite differences of Γ."""
    g0 = metric_at(p)
    detg = float(np.linalg.det(g0))
    invg0 = np.linalg.inv(g0)
    dg0 = _finite_diff_metric_derivs(metric_at, p, h)
    Gamma0 = _christoffel(g0, dg0)

    # Precompute Γ at shifted points for ∂_i Γ^ρ_{μν}
    # We compute dGamma[i, rho, mu, nu] = ∂_i Γ^rho_{mu nu}
    dGamma = np.zeros((3, 4, 4, 4), dtype=float)
    x, y, z = (float(p[0]), float(p[1]), float(p[2]))
    shifts = ((h, 0.0, 0.0), (0.0, h, 0.0), (0.0, 0.0, h))
    for i, dp in enumerate(shifts):
        pp = (x + dp[0], y + dp[1], z + dp[2])
        pm = (x - dp[0], y - dp[1], z - dp[2])
        dg_p = _finite_diff_metric_derivs(metric_at, pp, h)
        dg_m = _finite_diff_metric_derivs(metric_at, pm, h)
        Gamma_p = _christoffel(metric_at(pp), dg_p)
        Gamma_m = _christoffel(metric_at(pm), dg_m)
        dGamma[i] = (Gamma_p - Gamma_m) / (2.0 * h)

    # Ricci tensor
    Ric = np.zeros((4, 4), dtype=float)

    def d_Gamma(coord_index: int, rho: int, mu: int, nu: int) -> float:
        if coord_index == 0:
            return 0.0
        return float(dGamma[coord_index - 1, rho, mu, nu])

    for mu in range(4):
        for nu in range(4):
            # ∂_α Γ^α_{μν}
            term1 = 0.0
            for alpha in range(4):
                term1 += d_Gamma(alpha, alpha, mu, nu)

            # ∂_ν Γ^α_{μα}
            term2 = 0.0
            for alpha in range(4):
                term2 += d_Gamma(nu, alpha, mu, alpha)

            # Γ^α_{αβ} Γ^β_{μν}
            term3 = 0.0
            for alpha in range(4):
                for beta in range(4):
                    term3 += Gamma0[alpha, alpha, beta] * Gamma0[beta, mu, nu]

            # Γ^α_{μβ} Γ^β_{αν}
            term4 = 0.0
            for alpha in range(4):
                for beta in range(4):
                    term4 += Gamma0[alpha, mu, beta] * Gamma0[beta, alpha, nu]

            Ric[mu, nu] = term1 - term2 + term3 - term4

    R = float(np.sum(invg0 * Ric))
    return CurvatureResult(ricci_scalar=R, metric_det=detg)


def ricci_scalar_static(metric_at: MetricFn, p: Tuple[float, float, float], *, h: float = 1e-3) -> CurvatureResult:
    if h <= 0:
        raise ValueError('h must be positive')
    return _ricci_scalar(metric_at, p, h)
