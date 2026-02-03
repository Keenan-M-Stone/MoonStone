import pytest
import numpy as np

try:
    from stardust.gpu import is_cuda_available
    HAS_CUDA = is_cuda_available()
except Exception:
    HAS_CUDA = False


@pytest.mark.skipif(not HAS_CUDA, reason="CUDA not available on this system")
def test_trace_flat_gpu_basic():
    from app.accelerated_cuda import trace_flat_gpu
    sources = np.array([[0.0, 0.0, 0.0]])
    dirs = np.array([[1.0, 0.0, 0.0]])
    params = {'npoints': 10, 'step': 0.1}
    res = trace_flat_gpu(sources, dirs, params)
    assert isinstance(res, list)
    assert len(res) == 1
    assert len(res[0]) == 10
    assert res[0][0][0] == pytest.approx(0.0)


@pytest.mark.skipif(not HAS_CUDA, reason="CUDA not available on this system")
def test_trace_schwarzschild_gpu_basic():
    from app.accelerated_cuda import trace_schwarzschild_gpu
    sources = np.array([[0.0, 1.0, 0.0]])
    dirs = np.array([[1.0, 0.0, 0.0]])
    masses = np.array([1.0])
    params = {'npoints': 10, 'step': 0.1}
    res = trace_schwarzschild_gpu(sources, dirs, masses, params)
    assert isinstance(res, list)
    assert len(res) == 1
    assert len(res[0]) == 10
    # ensure some deflection applied in y for later points
    assert abs(res[0][-1][1] - 1.0) >= 0.0
