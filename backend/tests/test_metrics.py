import numpy as np
from app.metrics import (
    flat_metric,
    schwarzschild_metric,
    galadriel_metric,
    plebanski_mapping,
    plebanski_boston_mapping,
    constitutive_at,
)


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


def test_boston_mapping_gamma_shapes_and_symmetries():
    g = galadriel_metric((1.0, 2.0, 0.0), f=3.0, b=0.5)
    t = plebanski_boston_mapping(g)
    assert t['eps'].shape == (3, 3)
    assert t['mu'].shape == (3, 3)
    assert t['gamma1'].shape == (3, 3)
    assert t['gamma2'].shape == (3, 3)
    assert np.allclose(t['mu'], t['eps'])
    assert np.allclose(t['gamma2'], t['gamma1'].T)


def test_constitutive_at_supports_boston_mapping_selector():
    t = constitutive_at((1.0, 2.0, 0.0), {'type': 'galadriel', 'f': 3.0, 'b': 0.5, 'mapping': 'boston'})
    assert 'eps' in t and 'mu' in t and 'xi' in t and 'zeta' in t
    assert 'gamma1' in t and 'gamma2' in t
    assert np.allclose(t['mu'], t['eps'])
    assert np.allclose(t['zeta'], t['xi'].T)
