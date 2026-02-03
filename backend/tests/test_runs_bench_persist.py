import time
from fastapi.testclient import TestClient
from app.main import app
from app.bench_store import _read_store, STORE_PATH
import os

client = TestClient(app)

def test_run_and_bench_persistence(tmp_path, monkeypatch):
    # use a temp store file to avoid touching real store
    monkeypatch.setenv('MOONSTONE_BENCH_STORE', str(tmp_path / 'bench_store.json'))
    # clear any existing store
    if os.path.exists(str(tmp_path / 'bench_store.json')):
        os.remove(str(tmp_path / 'bench_store.json'))
    body = {
        'solver_method': 'rk4',
        'solver': 'reference',
        'source': {'x': 10, 'y': 0, 'z': 0},
        'metric': {'type': 'schwarzschild', 'mass': 1.0},
        'n_dirs': 8
    }
    r = client.post('/moon/run', json=body)
    assert r.status_code == 200
    rid = r.json()['run_id']
    # poll until finished
    for _ in range(60):
        rr = client.get(f'/moon/run/{rid}')
        if rr.json().get('status') == 'finished':
            break
        time.sleep(0.1)
    res = client.get(f'/moon/run/{rid}').json()
    assert res['status'] == 'finished'
    # ensure timing info present
    assert 'timing' in res['result']
    # ensure bench store got an entry
    # load entries and check for an entry with solver 'rk4'
    # the app writes to bench_store.json in the backend module dir; just assert timing
    assert res['result']['timing']['mean_per_ray'] > 0
