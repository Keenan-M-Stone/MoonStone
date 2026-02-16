from fastapi.testclient import TestClient

from app.main import app
import json


client = TestClient(app)


def test_metric_registry_exists():
    r = client.get('/moon/metric-registry')
    assert r.status_code == 200
    j = r.json()
    assert 'metric_types' in j
    assert 'field' in j['metric_types']
    assert 'matrix' in j['metric_types']
    assert 'mappings' in j


def test_metric_validate_returns_warnings_for_modified_gravity_metadata():
    r = client.post('/moon/metric/validate', json={'metric': {'type': 'schwarzschild', 'mass': 1.0, 'gravity_model': 'fR'}})
    assert r.status_code == 200
    j = r.json()
    assert 'warnings' in j
    assert any('gravity_model' in w for w in j['warnings'])


def test_metric_sample_matrix_ok_and_invalid_field_404():
    # matrix metric works for sampling
    r = client.post(
        '/moon/metric',
        json={'x': 0.0, 'y': 0.0, 'z': 0.0},
        params={'metric': json.dumps({'type': 'matrix', 'g': [[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]})},
    )
    assert r.status_code == 200
    j = r.json()
    assert 'eps' in j and 'warnings' in j

    # field id not found should 404
    r2 = client.post(
        '/moon/metric',
        json={'x': 0.0, 'y': 0.0, 'z': 0.0},
        params={'metric': json.dumps({'type': 'field', 'field_id': 'does-not-exist'})},
    )
    assert r2.status_code == 404


def test_trace_rejects_matrix_metric_type():
    body = {
        'source': {'x': 0.0, 'y': 0.0, 'z': 0.0},
        'directions': [{'x': 1.0, 'y': 0.0, 'z': 0.0}],
        'metric': {'type': 'matrix', 'g': [[-1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]},
        'params': {'npoints': 10, 'step': 1e-3, 'fd_step': 1e-3},
    }
    r = client.post('/moon/trace', json=body)
    assert r.status_code == 200
    j = r.json()
    assert 'points' in j
    assert len(j['points']) == 10
    # Minkowski metric should produce a straight line in +x
    last = j['points'][-1]
    assert abs(last['x'] - 9e-3) < 1e-6
    assert abs(last['y']) < 1e-9
    assert abs(last['z']) < 1e-9


def test_trace_field_id_not_found_404():
    body = {
        'source': {'x': 0.0, 'y': 0.0, 'z': 0.0},
        'directions': [{'x': 1.0, 'y': 0.0, 'z': 0.0}],
        'metric': {'type': 'field', 'field_id': 'does-not-exist'},
        'params': {'npoints': 10, 'step': 1e-3, 'fd_step': 1e-3},
    }
    r = client.post('/moon/trace', json=body)
    assert r.status_code == 404
