from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_trace_response_includes_device_analytic_flag():
    body = {
        'source': {'x': 10.0, 'y': 0.0, 'z': 0.0},
        'directions': [{'x': -1.0, 'y': 0.0, 'z': 0.0}],
        'metric': {'type': 'schwarzschild', 'mass': 1.0},
        # use slightly different params to avoid hitting cache from other tests
        'params': {'method': 'kerr_formal', 'npoints': 13, 'step': 1e-4, 'spin': (0.0,0.0,0.1), 'device': 'gpu', 'analytic': True}
    }
    r = client.post('/moon/trace', json=body)
    assert r.status_code == 200
    j = r.json()
    assert 'meta' in j
    # new meta includes requested/executed flags
    assert j['meta'].get('device_analytic_requested', False) is True
    assert 'device_analytic_executed' in j['meta'] and isinstance(j['meta']['device_analytic_executed'], bool)
