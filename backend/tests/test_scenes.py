from fastapi.testclient import TestClient
from app.main import app
from app import scenes

client = TestClient(app)


def test_scene_save_and_load(tmp_path, monkeypatch):
    # redirect scene dir
    monkeypatch.setattr(scenes, 'SCENE_DIR', tmp_path)
    body = {'name': 'test-scene', 'objects': [{'id':'o1', 'type':'pointmass', 'pos':[0,0,0], 'mass':1.0}]}
    r = client.post('/moon/scene', json=body)
    assert r.status_code == 200
    sid = r.json()['id']
    r2 = client.get(f'/moon/scene/{sid}')
    assert r2.status_code == 200
    assert r2.json()['name'] == 'test-scene'
    rlist = client.get('/moon/scenes')
    assert sid in rlist.json()['scenes']
