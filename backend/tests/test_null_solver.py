from app.geodesics import trace_null_geodesic


def test_null_solver_basic():
    src = (0.0, 1.0, 0.0)
    d = (1.0, 0.0, 0.0)
    res = trace_null_geodesic(src, d, mass=0.001, params={'npoints': 32, 'step': 1e-6})
    assert isinstance(res, list)
    assert len(res) == 32
    # Ensure it produces non-identical points
    assert res[0] != res[-1]
