from app.geodesics import trace_flat, trace_schwarzschild_weak
import numpy as np


def test_trace_flat_straight_line():
    src = (0.0, 0.0, 0.0)
    d = (1.0, 0.0, 0.0)
    pts = trace_flat(src, d, npoints=10, step=0.1)
    # points should be at multiples of step along x
    xs = [p[0] for p in pts]
    assert xs[0] == 0.0
    assert np.allclose(xs, [i * 0.1 for i in range(10)])


def test_schwarzschild_deflection_small():
    src = (-1.0, 1.0, 0.0)
    d = (1.0, 0.0, 0.0)
    pts = trace_schwarzschild_weak(src, d, mass=0.5, npoints=100, step=0.02)
    ys = [p[1] for p in pts]
    # Expect a small monotonic change in y due to deflection
    assert abs(ys[-1] - ys[0]) > 0
    assert len(pts) == 100
