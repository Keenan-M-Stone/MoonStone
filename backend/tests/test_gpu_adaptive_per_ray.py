import pytest
import numpy as np

try:
    from stardust.gpu import is_cuda_available
    HAS_CUDA = is_cuda_available()
except Exception:
    HAS_CUDA = False


@pytest.mark.skipif(not HAS_CUDA, reason="CUDA not available")
def test_gpu_adaptive_per_ray():
    from app.accelerated_cuda import trace_schwarzschild_rk4_adaptive_gpu
    sources = np.array([[0.0,1.0,0.0],[0.0,2.0,0.0]])
    dirs = np.array([[1.0,0.0,0.0],[1.0,0.1,0.0]])
    masses = np.array([0.001,0.01])
    params = {'npoints': 128, 'step': 1e-6, 'tol': 1e-7, 'max_refine_factor': 4}
    res = trace_schwarzschild_rk4_adaptive_gpu(sources, dirs, masses, params)
    assert isinstance(res, list)
    assert len(res) == 2
    assert len(res[0]) == 128
    assert len(res[1]) == 128
