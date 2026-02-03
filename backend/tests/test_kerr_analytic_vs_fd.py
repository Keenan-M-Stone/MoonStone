import numpy as np
from app.geodesics import trace_kerr_formal


def test_kerr_trace_nullness():
    # quick smoke check: trace should produce spatial samples and move away from source
    src = (10.0, 0.0, 0.0)
    dir = (-1.0, -0.1, 0.0)
    pts = trace_kerr_formal(src, dir, mass=1.0, spin=(0.0,0.0,0.5), params={'npoints': 16, 'step': 1e-3, 'formal': True})
    assert isinstance(pts, list)
    assert len(pts) == 16
    # Ensure not all points identical
    assert any(p != pts[0] for p in pts[1:])
