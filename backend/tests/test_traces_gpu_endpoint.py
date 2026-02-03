from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_gpu_endpoint_exists():
    r = client.get('/moon/gpu')
    assert r.status_code == 200
    j = r.json()
    assert 'cuda' in j
    assert isinstance(j['cuda'], bool)
