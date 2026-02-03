import pytest
import numpy as np
try:
    from backend.app import accelerated_cuda as ac
    HAS_CUDA = ac.NUMBA_CUDA_OK
except Exception:
    HAS_CUDA = False

@pytest.mark.skipif(not HAS_CUDA, reason='CUDA not available')
def test_device_adaptive_error_control():
    sources = np.array([[10.0, 0.0, 0.0], [10.0, 1.0, 0.0]], dtype=float)
    dirs = np.array([[-1.0, 0.0, 0.0], [-0.99, -0.1, 0.0]], dtype=float)
    masses = np.array([1.0, 1.0], dtype=float)
    params = {'npoints': 32, 'step': 1e-3, 'tol': 1e-6, 'max_steps': 1000}
    res = ac.trace_schwarzschild_rk4_device_adaptive_error(sources, dirs, masses, params)
    assert isinstance(res, list)
    assert len(res) == 2
    assert all(len(r) == 32 for r in res)
    # ensure rays moved
    assert any(r[1] != r[0] for r in res[0])
