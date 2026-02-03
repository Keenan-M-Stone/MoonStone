from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_bench_endpoint():
    r = client.post('/moon/bench', json={'solver': 'weak', 'params': {'npoints': 64, 'ntest': 2}})
    assert r.status_code == 200
    j = r.json()
    assert 'mean_sec' in j and 'estimate' in j
