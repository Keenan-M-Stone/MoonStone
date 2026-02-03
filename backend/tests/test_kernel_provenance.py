from app.main import app
from fastapi.testclient import TestClient
from importlib import import_module

client = TestClient(app)


def test_kernel_provenance_flags_present_after_trace():
    # Request an analytic GPU trace (may fallback if no GPU present)
    body = {
        'source': {'x': 10.0, 'y': 0.0, 'z': 0.0},
        'directions': [{'x': -1.0, 'y': 0.0, 'z': 0.0}],
        'metric': {'type': 'schwarzschild', 'mass': 1.0},
        'params': {'method': 'kerr_formal', 'npoints': 8, 'step': 1e-3, 'spin': (0.0,0.0,0.1), 'device': 'gpu', 'analytic': True}
    }
    r = client.post('/moon/trace', json=body)
    assert r.status_code == 200
    # check the module-level provenance placeholder
    prov = import_module('app.accelerated_cuda')._LAST_KERNEL_INFO
    # requested flag should be present; its value depends on whether CUDA path was taken
    assert 'requested_analytic' in prov
    assert 'executed_analytic' in prov and isinstance(prov['executed_analytic'], bool)
    # if CUDA available on this test host, requested should be True
    try:
        from stardust.gpu import is_cuda_available
        if is_cuda_available():
            assert prov['requested_analytic'] is True
    except Exception:
        # GPU helper not available in this environment - accept either value
        pass
