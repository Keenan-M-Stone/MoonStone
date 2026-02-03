from app.geodesics import trace_flat, trace_schwarzschild_weak
import numpy as np

def test_flat_straight_line():
    pts = trace_flat((0,0,0),(1,0,0), params={'npoints':10, 'step':0.1})
    assert len(pts) == 10
    # x increases linearly, y,z ~ 0
    xs = [p[0] for p in pts]
    assert np.allclose(xs, np.linspace(0, 0.9, 10))

def test_schwarzschild_deflects():
    pts = trace_schwarzschild_weak((0,1e-3,0),(1,0,0), mass=1.0, params={'npoints':10, 'step':0.1})
    # With mass, y should change slightly from its initial value
    ys = [p[1] for p in pts]
    assert not all(np.isclose(y, ys[0]) for y in ys)
