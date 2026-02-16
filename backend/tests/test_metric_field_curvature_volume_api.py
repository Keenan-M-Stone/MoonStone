import numpy as np
from fastapi.testclient import TestClient


def test_metric_field_ricci_scalar_volume_endpoints(tmp_path, monkeypatch):
    # Use isolated metric field directory
    monkeypatch.setenv('MOONSTONE_METRIC_FIELD_DIR', str(tmp_path))

    from app.main import app

    client = TestClient(app)

    # Create a tiny Minkowski metric field (2x2x2) via sampling a constant matrix.
    nx, ny, nz = 2, 2, 2
    minkowski = [
        [-1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    gen = client.post(
        '/moon/metric-field/generate/sample',
        json={
            'grid': {'origin': [0.0, 0.0, 0.0], 'spacing': [1.0, 1.0, 1.0], 'shape': [nx, ny, nz]},
            'metric': {'type': 'matrix', 'g': minkowski},
        },
    )
    assert gen.status_code == 200, gen.text
    field_id = gen.json()['id']

    # Compute derived curvature volume
    compute = client.post(
        f'/moon/metric-field/{field_id}/curvature/ricci-scalar',
        params={'h': 1e-2, 'force': True},
    )
    assert compute.status_code == 200, compute.text
    meta = compute.json()
    assert meta['field_id'] == field_id
    assert meta['kind'] == 'curvature_volume'

    # Meta endpoint should return cached meta
    meta_resp = client.get(
        f'/moon/metric-field/{field_id}/curvature/ricci-scalar/meta',
        params={'h': 1e-2},
    )
    assert meta_resp.status_code == 200, meta_resp.text

    # Data endpoint should return an npz with array named 'R'
    data_resp = client.get(
        f'/moon/metric-field/{field_id}/curvature/ricci-scalar/data',
        params={'h': 1e-2},
    )
    assert data_resp.status_code == 200, data_resp.text
    import io

    arr = np.load(io.BytesIO(data_resp.content))
    R = arr['R']
    assert R.shape == (nx, ny, nz)
    # Minkowski should be ~0 everywhere (numerical noise allowed)
    assert np.max(np.abs(R)) < 1e-6
