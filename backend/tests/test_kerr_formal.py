import pytest
from app.geodesics import trace_kerr_formal


def test_kerr_formal_basic():
    src = (10.0, 0.0, 0.0)
    dir = (-1.0, 0.0, 0.0)
    pts = trace_kerr_formal(src, dir, mass=1.0, spin=(0.0, 0.0, 0.1), params={'npoints': 20, 'step': 1e-3})
    assert isinstance(pts, list)
    assert len(pts) == 20
    # points should not be all identical
    assert any(p != pts[0] for p in pts[1:])
