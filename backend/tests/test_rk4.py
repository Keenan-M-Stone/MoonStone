import pytest
from app.geodesics import trace_flat, trace_flat_rk4


def test_flat_rk4_agrees_basic():
    src = (0.0, 0.0, 0.0)
    d = (1.0, 0.0, 0.0)
    params = {'npoints': 10, 'step': 0.1}
    a = trace_flat(src, d, params)
    b = trace_flat_rk4(src, d, params)
    assert len(a) == len(b)
    # for straight-line propagation the RK4 POC should match simple stepping
    for i in range(len(a)):
        assert a[i][0] == pytest.approx(b[i][0])
        assert a[i][1] == pytest.approx(b[i][1])
        assert a[i][2] == pytest.approx(b[i][2])
