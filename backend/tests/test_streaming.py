from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_trace_stream_ws():
    with client.websocket_connect('/moon/trace/ws') as ws:
        payload = {
            'source': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'directions': [{'x': 1.0, 'y': 0.0, 'z': 0.0}],
            'metric': {'type': 'flat'},
            'params': {'npoints': 8, 'step': 0.1}
        }
        ws.send_json(payload)
        msg = ws.receive_json()
        # expect a partial message first
        assert msg['type'] == 'partial'
        assert 'points' in msg
        assert len(msg['points']) == 8
        done = ws.receive_json()
        assert done['type'] == 'done'
