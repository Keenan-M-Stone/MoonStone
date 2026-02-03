import numpy as np
import pytest
from app.geodesics import trace_schwarzschild_weak, trace_schwarzschild_rk4


def test_rk4_vs_weak_small_mass():
    src = (0.0, 1.0, 0.0)
    d = (1.0, 0.0, 0.0)
    params = {'npoints': 512, 'step': 1e-6}
    mass = 0.001
    a = trace_schwarzschild_weak(src, d, mass, params)
    b = trace_schwarzschild_rk4(src, d, mass, params)
    # Compare final y-deflection: they should be small and comparable
    ay = a[-1][1]
    by = b[-1][1]
    assert abs(ay - by) < 1e-4
    # trajectories should be similar (L2 norm small)
    diffs = [np.sqrt((px - qx)**2 + (py - qy)**2 + (pz - qz)**2) for (px,py,pz),(qx,qy,qz) in zip(a, b)]
    assert np.mean(diffs) < 1e-4
