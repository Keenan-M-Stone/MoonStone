from app.geodesics import trace_flat, trace_schwarzschild_weak, trace_null_formal, kerr_r, kerr_metric_cartesian
import numpy as np


def test_trace_flat_straight_line():
    src = (0.0, 0.0, 0.0)
    d = (1.0, 0.0, 0.0)
    pts = trace_flat(src, d, params={'npoints':10, 'step':0.1})
    # points should be at multiples of step along x
    xs = [p[0] for p in pts]
    assert xs[0] == 0.0
    assert np.allclose(xs, [i * 0.1 for i in range(10)])


def test_schwarzschild_deflection_small():
    src = (-1.0, 1.0, 0.0)
    d = (1.0, 0.0, 0.0)
    pts = trace_schwarzschild_weak(src, d, mass=0.5, params={'npoints':100, 'step':0.02})
    ys = [p[1] for p in pts]
    # Expect a small monotonic change in y due to deflection
    assert abs(ys[-1] - ys[0]) > 0
    assert len(pts) == 100


def test_null_formal_deflection_angle():
    """Quantitative test: weak-field Schwarzschild light deflection.

    For a photon with impact parameter b passing a mass M in the weak field,
    the GR prediction is δφ = 4M/b (geometric units G=c=1).

    We use the post-Newtonian formal integrator with M=0.01, b=10,
    so expected δφ ≈ 4×0.01/10 = 0.004 rad.
    """
    M = 0.01
    b = 10.0
    expected_deflection = 4.0 * M / b  # 0.004 rad

    # Photon starts far left, impact parameter b in y-direction
    src = (-200.0, b, 0.0)
    d = (1.0, 0.0, 0.0)
    pts = trace_null_formal(src, d, mass=M, params={'npoints': 4000, 'step': 0.1})

    # Compute deflection angle from the final direction
    # Use last few points to estimate exit direction
    p_end = np.array(pts[-1])
    p_near_end = np.array(pts[-20])
    exit_dir = p_end - p_near_end
    exit_dir = exit_dir / np.linalg.norm(exit_dir)

    # Deflection angle = angle between exit direction and initial direction (1,0,0)
    cos_angle = exit_dir[0]  # dot product with (1,0,0)
    deflection = np.arccos(np.clip(cos_angle, -1.0, 1.0))

    # Allow 20% tolerance for the numerical integrator
    assert abs(deflection - expected_deflection) < 0.2 * expected_deflection, \
        f"Deflection {deflection:.6f} rad, expected {expected_deflection:.6f} rad"


def test_kerr_r_closed_form_correctness():
    """kerr_r should exactly solve the quartic r⁴ - ρ² r² - a² z² = 0."""
    test_cases = [
        (5.0, 3.0, 4.0, 0.5),
        (1.0, 1.0, 1.0, 0.9),
        (10.0, 0.0, 0.0, 0.3),
        (0.0, 0.0, 5.0, 2.0),
    ]
    for px, py, pz, a in test_cases:
        r = kerr_r(px, py, pz, a)
        rho2 = px**2 + py**2 + pz**2 - a**2
        residual = r**4 - rho2 * r**2 - (a**2) * (pz**2)
        assert abs(residual) < 1e-10, f"Quartic residual {residual} for point ({px},{py},{pz}), a={a}"
        assert r > 0, f"r must be positive, got {r}"


def test_kerr_r_reduces_to_euclidean_for_zero_spin():
    """When a=0, kerr_r should return the Euclidean distance."""
    for point in [(1, 0, 0), (0, 3, 4), (1, 2, 3)]:
        r = kerr_r(*point, 0.0)
        expected = np.sqrt(sum(x**2 for x in point))
        assert np.isclose(r, expected, rtol=1e-12)


def test_kerr_metric_limits():
    """Kerr with a=0 should match Schwarzschild Kerr-Schild form."""
    from app.metrics import schwarzschild_metric
    for r_val in [5.0, 10.0, 50.0]:
        g_kerr = kerr_metric_cartesian(r_val, 0.0, 0.0, 1.0, 0.0)
        g_schw = schwarzschild_metric((r_val, 0.0, 0.0), 1.0)
        assert np.allclose(g_kerr, g_schw, atol=1e-10), \
            f"Kerr(a=0) != Schwarzschild at r={r_val}"
