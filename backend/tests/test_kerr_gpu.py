import pytest
import numpy as np
try:
    from backend.app import accelerated_cuda as ac
    HAS_CUDA = ac.NUMBA_CUDA_OK
except Exception:
    HAS_CUDA = False

@pytest.mark.skipif(not HAS_CUDA, reason='CUDA not available')
def test_trace_kerr_gpu_basic():
    sources = np.array([[10.0, 0.0, 0.0], [10.0, 1.0, 0.0]], dtype=float)
    dirs = np.array([[-1.0, 0.0, 0.0], [-0.99, -0.1, 0.0]], dtype=float)
    masses = np.array([1.0, 1.0], dtype=float)
    params = {'npoints': 32, 'step': 1e-3, 'spin': (0.0, 0.0, 0.2)}
    res = ac.trace_kerr_gpu(sources, dirs, masses, params)
    assert isinstance(res, list)
    assert len(res) == 2
    assert all(len(r) == 32 for r in res)
    assert any(r[1] != r[0] for r in res[0])
