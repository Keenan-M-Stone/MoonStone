import pytest
import numpy as np
from app import geodesics
try:
    from backend.app import accelerated_cuda as ac
    HAS_CUDA = ac.NUMBA_CUDA_OK
except Exception:
    HAS_CUDA = False

@pytest.mark.skipif(not HAS_CUDA, reason='CUDA not available')
def test_kerr_rk4_gpu_exact():
    sources = np.array([[8.0, 0.0, 0.0]], dtype=float)
    dirs = np.array([[-1.0, -0.05, 0.0]], dtype=float)
    masses = np.array([1.0], dtype=float)
    params = {'npoints': 64, 'step': 1e-3, 'spin': (0.0,0.0,0.5)}
    gpu_res = ac.trace_kerr_rk4_gpu(sources, dirs, masses, params)
    cpu_res = geodesics.trace_kerr_formal((8.0,0.0,0.0), (-1.0, -0.05, 0.0), mass=1.0, spin=(0.0,0.0,0.5), params={'npoints':64, 'step':1e-3, 'formal': True})
    assert len(gpu_res) == 1
    gr = gpu_res[0]
    assert len(gr) == len(cpu_res)
    dx = abs(gr[-1][0] - cpu_res[-1][0])
    dy = abs(gr[-1][1] - cpu_res[-1][1])
    dz = abs(gr[-1][2] - cpu_res[-1][2])
    assert (dx*dx + dy*dy + dz*dz)**0.5 < 0.5
