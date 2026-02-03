from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_bench_multi():
    r = client.post('/moon/bench', json={'solvers': ['weak','rk4'] , 'params': {'npoints': 64, 'ntest': 2}})
    assert r.status_code == 200
    j = r.json()
    assert 'results' in j and 'weak' in j['results'] and 'rk4' in j['results']
