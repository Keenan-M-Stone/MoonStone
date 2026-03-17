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


def test_flat_plebanski_identity():
    """Flat Minkowski → eps = mu = -I, xi = zeta = 0 (exact)."""
    g = flat_metric((0.0, 0.0, 0.0))
    t = plebanski_mapping(g)
    assert np.allclose(t['eps'], -np.eye(3), atol=1e-14)
    assert np.allclose(t['mu'], -np.eye(3), atol=1e-14)
    assert np.allclose(t['xi'], np.zeros((3, 3)), atol=1e-14)
    assert np.allclose(t['zeta'], np.zeros((3, 3)), atol=1e-14)


def test_schwarzschild_metric_and_mapping():
    g = schwarzschild_metric((1.0, 0.0, 0.0), mass=1.0)
    tensors = plebanski_mapping(g)
    assert tensors['eps'].shape == (3, 3)
    assert np.all(np.isfinite(tensors['eps']))


def test_schwarzschild_kerr_schild_properties():
    """Schwarzschild in Kerr-Schild form has det(g) = -1 and correct g_{00}."""
    for r_val in [5.0, 10.0, 100.0]:
        g = schwarzschild_metric((r_val, 0.0, 0.0), mass=1.0)
        # det(g) = -1 for Kerr-Schild metrics
        assert abs(np.linalg.det(g) + 1.0) < 1e-10, f"det(g)={np.linalg.det(g)} at r={r_val}"
        # g_{00} = -(1 - 2M/r) for Kerr-Schild along x-axis
        expected_g00 = -(1.0 - 2.0 / r_val)
        assert abs(g[0, 0] - expected_g00) < 1e-10, f"g00={g[0,0]}, expected={expected_g00}"


def test_schwarzschild_reduces_to_minkowski():
    """At large r, Schwarzschild approaches Minkowski."""
    g = schwarzschild_metric((1e6, 0.0, 0.0), mass=1.0)
    eta = np.diag([-1.0, 1.0, 1.0, 1.0])
    assert np.allclose(g, eta, atol=1e-5)


def test_schwarzschild_plebanski_approaches_flat():
    """At large r, Plebanski mapping of Schwarzschild approaches flat vacuum."""
    g = schwarzschild_metric((1e4, 0.0, 0.0), mass=1.0)
    t = plebanski_mapping(g)
    assert np.allclose(t['eps'], -np.eye(3), atol=1e-3)
    assert np.allclose(t['mu'], -np.eye(3), atol=1e-3)
    assert np.allclose(t['xi'], np.zeros((3, 3)), atol=1e-3)
    assert np.allclose(t['zeta'], np.zeros((3, 3)), atol=1e-3)


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


def test_plebanski_grid_endpoint():
    """The /moon/plebanski-grid endpoint returns a constitutive tensor grid."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.post('/moon/plebanski-grid', json={
        'metric': {'type': 'flat'},
        'bounds': {'xmin': -1, 'xmax': 1, 'ymin': -1, 'ymax': 1},
        'nx': 4, 'ny': 4, 'z': 0,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data['nx'] == 4 and data['ny'] == 4
    assert len(data['grid']) == 16
    # Flat metric → eps = mu = -identity (Plebanski sign convention), xi = zeta = 0
    sample = data['grid'][0]
    assert 'eps' in sample and 'mu' in sample
    eps_flat = [sample['eps'][i][j] for i in range(3) for j in range(3)]
    neg_identity = [-1,0,0, 0,-1,0, 0,0,-1]
    assert all(abs(a - b) < 1e-6 for a, b in zip(eps_flat, neg_identity))
    xi_flat = [sample['xi'][i][j] for i in range(3) for j in range(3)]
    assert all(abs(v) < 1e-6 for v in xi_flat)
