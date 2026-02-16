import json

import numpy as np
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_curvature_flat_is_near_zero():
    r = client.post('/moon/curvature', json={'x': 0.0, 'y': 0.0, 'z': 0.0}, params={'metric': json.dumps({'type': 'flat'}), 'h': 1e-3})
    assert r.status_code == 200
    j = r.json()
    assert 'ricci_scalar' in j
    assert abs(float(j['ricci_scalar'])) < 1e-6


def test_curvature_matrix_minkowski_is_near_zero():
    mink = [[-1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0], [0, 0, 0, 1.0]]
    r = client.post('/moon/curvature', json={'x': 0.0, 'y': 0.0, 'z': 0.0}, params={'metric': json.dumps({'type': 'matrix', 'g': mink}), 'h': 1e-3})
    assert r.status_code == 200
    j = r.json()
    assert abs(float(j['ricci_scalar'])) < 1e-6


def test_metric_field_generate_sample_creates_field_and_can_be_sampled():
    # sample a flat metric into a tiny field
    body = {
        'grid': {'origin': [0.0, 0.0, 0.0], 'spacing': [1.0, 1.0, 1.0], 'shape': [2, 2, 2]},
        'metric': {'type': 'flat'},
    }
    r = client.post('/moon/metric-field/generate/sample', json=body)
    assert r.status_code == 200
    fid = r.json()['id']

    try:
        # curvature from the field should also be ~0
        r2 = client.post('/moon/curvature', json={'x': 0.5, 'y': 0.5, 'z': 0.5}, params={'metric': json.dumps({'type': 'field', 'field_id': fid}), 'h': 1e-3})
        assert r2.status_code == 200
        j2 = r2.json()
        assert abs(float(j2['ricci_scalar'])) < 1e-6
    finally:
        client.delete(f'/moon/metric-field/{fid}')
