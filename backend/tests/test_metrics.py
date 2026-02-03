import numpy as np
from app.metrics import flat_metric, schwarzschild_metric, plebanski_mapping, constitutive_at


def test_flat_metric_and_mapping():
    g = flat_metric((0.0, 0.0, 0.0))
    assert g.shape == (4, 4)
    tensors = plebanski_mapping(g)
    assert 'eps' in tensors and 'mu' in tensors and 'xi' in tensors
    assert np.allclose(tensors['eps'], tensors['mu'])
    assert tensors['eps'].shape == (3, 3)
    assert tensors['xi'].shape == (3, 3)


def test_schwarzschild_metric_and_mapping():
    g = schwarzschild_metric((1.0, 0.0, 0.0), mass=1.0)
    tensors = plebanski_mapping(g)
    assert tensors['eps'].shape == (3, 3)
    assert np.all(np.isfinite(tensors['eps']))


def test_constitutive_at_endpoint_behavior():
    for point in [(1e-6, 0, 0), (1.0, 0.0, 0.0)]:
        t = constitutive_at(point, {'type': 'schwarzschild', 'mass': 0.1})
        assert 'eps' in t and 'mu' in t and 'xi' in t
        assert np.array(t['eps']).shape == (3, 3)
