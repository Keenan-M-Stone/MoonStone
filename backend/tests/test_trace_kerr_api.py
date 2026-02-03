from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_trace_kerr_api():
    body = {
        'source': {'x': 10.0, 'y': 0.0, 'z': 0.0},
        'directions': [{'x': -1.0, 'y': 0.0, 'z': 0.0}],
        'metric': {'type': 'schwarzschild', 'mass': 1.0},
        'params': {'method': 'kerr_formal', 'npoints': 32, 'step': 1e-3, 'spin': (0.0,0.0,0.1)}
    }
    r = client.post('/moon/trace', json=body)
    assert r.status_code == 200
    j = r.json()
    assert 'points' in j
    assert len(j['points']) == 32
