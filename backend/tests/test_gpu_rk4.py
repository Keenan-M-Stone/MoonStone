import pytest
import numpy as np

try:
    from stardust.gpu import is_cuda_available
    HAS_CUDA = is_cuda_available()
except Exception:
    HAS_CUDA = False


@pytest.mark.skipif(not HAS_CUDA, reason="CUDA not available")
def test_gpu_rk4_matches_cpu():
    from app.geodesics import trace_schwarzschild_rk4
    from app.accelerated_cuda import trace_schwarzschild_rk4_gpu
    src = np.array([[0.0, 1.0, 0.0]])
    dirs = np.array([[1.0, 0.0, 0.0]])
    mass = np.array([0.001])
    params = {'npoints': 256, 'step': 1e-6}
    cpu = trace_schwarzschild_rk4((0.0,1.0,0.0), (1.0,0.0,0.0), 0.001, params)
    gpu = trace_schwarzschild_rk4_gpu(src, dirs, mass, params)
    assert len(gpu) == 1
    g = gpu[0]
    assert len(g) == len(cpu)
    # endpoints close
    assert g[-1][1] == pytest.approx(cpu[-1][1], rel=1e-3, abs=1e-6)
