from app.geodesics import trace_schwarzschild_batch


def test_null_formal_batch():
    source = (0.0, 1.0, 0.0)
    dirs = [(1.0, 0.0, 0.0), (1.0, 0.1, 0.0)]
    res = trace_schwarzschild_batch(source, dirs, mass=0.001, params={'method': 'null_formal', 'npoints': 32, 'step': 1e-6})
    assert isinstance(res, list)
    assert len(res) == len(dirs)
    assert len(res[0]) == 32
