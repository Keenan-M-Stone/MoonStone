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
from typing import Tuple, Dict, Any, List
import numpy as np

# Metric-field cache (id -> (meta, g)) to keep GUI interactions snappy.
_METRIC_FIELD_CACHE: Dict[str, tuple] = {}


def validate_metric_cfg(metric_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a metric config.

    This is intentionally lightweight: we keep compatibility with existing
    callers that pass arbitrary dicts, but we ensure errors surface as 4xx
    rather than 5xx in API handlers.
    """
    if metric_cfg is None:
        return {'type': 'flat'}
    if not isinstance(metric_cfg, dict):
        raise ValueError('metric must be an object/dict')

    out = dict(metric_cfg)
    out.setdefault('type', 'flat')
    out.setdefault('mapping', 'sunstone')
    return out


def metric_cfg_warnings(metric_cfg: Dict[str, Any]) -> List[str]:
    """Return non-fatal guidance about compatibility/assumptions."""
    warnings: List[str] = []
    mtype = metric_cfg.get('type', 'flat')
    mapping = metric_cfg.get('mapping', 'sunstone')
    gravity_model = metric_cfg.get('gravity_model')

    if gravity_model not in (None, 'gr', 'gr_weakfield_static'):
        if mtype in ('schwarzschild', 'galadriel'):
            warnings.append(
                f'gravity_model="{gravity_model}" is not applied to analytic metric type "{mtype}"; provide a metric field/matrix if you want a non-GR model'
            )
        else:
            warnings.append(
                f'gravity_model="{gravity_model}" is treated as metadata only; MoonStone does not (yet) solve field equations for modified gravity'
            )

    if mtype in ('field', 'matrix'):
        warnings.append(
            'geodesic tracing over this metric type uses a finite-difference Christoffel integrator (static ∂_t g = 0); expect it to be slower and approximate, and tune params.fd_step/params.step if needed'
        )

    if mapping == 'boston' and mtype not in ('galadriel',):
        warnings.append('mapping="boston" is a convention-specific MP mapping; ensure it matches your intended constitutive convention')

    return warnings


def metric_at(point: Tuple[float, float, float], metric_cfg: Dict[str, Any]) -> np.ndarray:
    """Return the 4x4 covariant metric matrix g_{μν} at a 3D point.

    Notes:
    - All metrics are currently treated as static in time (∂_t g = 0).
    - For metric.type='matrix', this returns the provided constant matrix.
    - For metric.type='field', this interpolates the imported grid field.
    """
    metric_cfg = validate_metric_cfg(metric_cfg)
    mtype = metric_cfg.get('type', 'flat')

    if mtype == 'schwarzschild':
        mass = metric_cfg.get('mass', 1.0)
        return schwarzschild_metric(point, mass)

    if mtype == 'galadriel':
        f = metric_cfg.get('f', 1.0)
        b = metric_cfg.get('b', 0.0)
        r2_floor = float(metric_cfg.get('r2_floor', 1e-12))
        return galadriel_metric(point, f=f, b=b, r2_floor=r2_floor)

    if mtype == 'matrix':
        g_in = metric_cfg.get('g')
        g = np.asarray(g_in, dtype=float)
        if g.shape != (4, 4):
            raise ValueError('matrix metric requires metric_cfg.g as a 4x4 array')
        return g

    if mtype == 'field':
        field_id = metric_cfg.get('field_id')
        if not isinstance(field_id, str) or not field_id:
            raise ValueError('field metric requires metric_cfg.field_id')

        cached = _METRIC_FIELD_CACHE.get(field_id)
        if cached is None:
            from .metric_fields import load_metric_field

            meta, g_grid = load_metric_field(field_id)
            cached = (meta, g_grid)
            _METRIC_FIELD_CACHE[field_id] = cached

        meta, g_grid = cached
        from .metric_fields import sample_metric_field

        return sample_metric_field(point, meta, g_grid, clamp=True)

    return flat_metric(point)

# NOTE: use geometric (G=c=1) units or document unit choices clearly.


def schwarzschild_metric(point: Tuple[float, float, float], mass: float) -> np.ndarray:
    """Return a 4x4 Schwarzschild metric in Kerr-Schild Cartesian coordinates.

    Uses the Kerr-Schild form with spin a=0:
        g_{μν} = η_{μν} + 2(M/r) l_μ l_ν
    where l^μ = (1, x/r, y/r, z/r) is the ingoing null vector.

    This form:
    - Is regular everywhere except r=0
    - Has signature (-,+,+,+) at spatial infinity
    - Reduces to Minkowski for M→0
    - Matches the Kerr-Schild form used by the Kerr integrator (a→0 limit)
    """
    x, y, z = point
    r = np.sqrt(x * x + y * y + z * z)
    r = max(r, 1e-12)
    m = float(mass)
    H = m / r
    # Kerr-Schild null vector l_μ = (1, x/r, y/r, z/r)
    l = np.array([1.0, x / r, y / r, z / r], dtype=float)
    g = np.diag([-1.0, 1.0, 1.0, 1.0])
    for mu in range(4):
        for nu in range(4):
            g[mu, nu] += 2.0 * H * l[mu] * l[nu]
    return g


def flat_metric(_: Tuple[float, float, float]) -> np.ndarray:
    g = np.diag([-1.0, 1.0, 1.0, 1.0])
    return g


def galadriel_metric(
    point: Tuple[float, float, float],
    f: float,
    b: float,
    *,
    r2_floor: float = 1e-12,
) -> np.ndarray:
    """Return SR Boston "Galadriel's Mirror" metric g_{μν} in Cartesian components.

    Transcription (paper Eq. 37 as provided in the repo docs):
      r^2 = x^2 + y^2
      g_{00} = -1
      g_{01} = - f y / r^2
      g_{02} = + f x / r^2
      g_{03} = 0
      g_{11} = 1 - (1 - b/r^2) * (y^2 / r^2)
      g_{12} = (1 - b/r^2) * (x y / r^2)
      g_{22} = 1 - (1 - b/r^2) * (x^2 / r^2)
      g_{33} = 1

    Notes:
    - This metric is singular at r->0; we apply a small floor to r^2 for numerical stability.
    - The paper appears to use r^2 = x^2 + y^2 (not including z).
    - Signature assumed (-,+,+,+).
    """
    x, y, z = point
    r2 = float(x * x + y * y)
    r2 = max(r2, float(r2_floor))

    g = np.zeros((4, 4), dtype=float)

    g[0, 0] = -1.0
    g01 = -(float(f) * y) / r2
    g02 = (float(f) * x) / r2
    g[0, 1] = g01
    g[1, 0] = g01
    g[0, 2] = g02
    g[2, 0] = g02

    one_minus_b_over_r2 = 1.0 - (float(b) / r2)
    g11 = 1.0 - one_minus_b_over_r2 * (y * y / r2)
    g22 = 1.0 - one_minus_b_over_r2 * (x * x / r2)
    g12 = one_minus_b_over_r2 * (x * y / r2)
    g[1, 1] = g11
    g[2, 2] = g22
    g[1, 2] = g12
    g[2, 1] = g12

    g[3, 3] = 1.0
    _ = z  # z does not enter r^2 in this metric

    return g


def plebanski_mapping(metric: np.ndarray) -> Dict[str, np.ndarray]:
    """Compute Plebanski constitutive tensors (eps, mu, xi, zeta) from a 4x4 metric g_{μν}.

    Implements the vacuum constitutive relation in curved spacetime:
        H^{μν} = √(-g) g^{μα} g^{νβ} F_{αβ}
    decomposed into 3x3 blocks via the (E,B) -> (D,H) split.

    Convention:
    - Metric signature (-,+,+,+)
    - Flat Minkowski → eps = mu = -I, xi = zeta = 0.

    This follows Plebanski (1960) / Hehl & Obukhov (2003, Ch. D.5),
    where the mapping is obtained by probing with unit field-strength
    basis vectors and reading off the constitutive response.

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


def plebanski_boston_mapping(metric: np.ndarray) -> Dict[str, np.ndarray]:
        """Compute MPs using SR Boston / Plebanski equations as written in the paper.

        The paper uses (with (-+++) signature, c=1):

            ε^{ab} = μ^{ab} = - sqrt(|g|) / g_{00} * g^{ab}
            γ1^{ab} = (γ2^T)^{ab} = ε^{acb} * g_{0c} / g_{00}

        and constitutive relations

            D_a = ε^{ab} E_b + γ1^{ab} H_b
            B_a = μ^{ab} H_b + γ2^{ab} E_b

        We return a dict that is compatible with existing MoonStone code:
            - eps, mu, xi, zeta (3x3)
            - gamma1, gamma2 (3x3) as aliases for xi/zeta

        Notes:
        - This is a convention-specific mapping intended for validating the paper.
        - Index placement matters in rigorous treatments; we follow the paper's usage directly.
        """
        g4 = np.asarray(metric, dtype=float)
        if g4.shape != (4, 4):
                raise ValueError('metric must be 4x4')

        detg = float(np.linalg.det(g4))
        sqrt_abs_g = float(np.sqrt(abs(detg)))
        invg = np.linalg.inv(g4)

        g00 = float(g4[0, 0])
        if abs(g00) < 1e-18:
                raise ValueError('g00 is too close to 0; mapping is singular')

        # Spatial inverse metric g^{ab} (a,b in {1,2,3})
        g_inv_spatial = invg[1:4, 1:4].copy()

        eps_mat = -(sqrt_abs_g / g00) * g_inv_spatial
        mu_mat = eps_mat.copy()

        # Levi-Civita with indices (x,y,z) -> (0,1,2)
        eps3 = np.zeros((3, 3, 3), dtype=float)
        eps3[0, 1, 2] = 1.0
        eps3[0, 2, 1] = -1.0
        eps3[1, 0, 2] = -1.0
        eps3[1, 2, 0] = 1.0
        eps3[2, 0, 1] = 1.0
        eps3[2, 1, 0] = -1.0

        g0 = g4[0, 1:4].copy()  # g_{0c}
        gamma1 = np.zeros((3, 3), dtype=float)
        for a in range(3):
                for b in range(3):
                        s = 0.0
                        for c in range(3):
                                # ε^{acb} g_{0c} / g00
                                s += eps3[a, c, b] * g0[c]
                        gamma1[a, b] = s / g00

        gamma2 = gamma1.T

        return {
                'eps': eps_mat,
                'mu': mu_mat,
                'xi': gamma1,
                'zeta': gamma2,
                'gamma1': gamma1,
                'gamma2': gamma2,
        }


# Utility: sample constitutive tensor for a metric name + params
def constitutive_at(point: Tuple[float, float, float], metric_cfg: Dict) -> Dict[str, np.ndarray]:
    metric_cfg = validate_metric_cfg(metric_cfg)
    mapping = metric_cfg.get('mapping', 'sunstone')
    g = metric_at(point, metric_cfg)

    if mapping == 'boston':
        return plebanski_boston_mapping(g)
    return plebanski_mapping(g)
