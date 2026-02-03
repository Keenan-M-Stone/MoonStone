import pytest
import numpy as np
from app import geodesics
try:
    from app import accelerated as ac
    HAS_NUMBA = ac._NUMBA_OK
except Exception:
    HAS_NUMBA = False

@pytest.mark.skipif(not HAS_NUMBA, reason='Numba not available')
def test_kerr_numba_batch():
    sources = np.array([[10.0,0.0,0.0],[10.0,1.0,0.0]], dtype=float)
    dirs = np.array([[-1.0,-0.05,0.0],[-0.98,-0.15,0.0]], dtype=float)
    masses = np.array([1.0,1.0], dtype=float)
    spins = np.array([[0.0,0.0,0.3],[0.0,0.0,0.3]], dtype=float)
    res = ac.trace_kerr_numba_batch(sources, dirs, masses, spins, 64, 1e-3)
    assert isinstance(res, list)
    assert len(res) == 2
    assert len(res[0]) == 64
    # compare to CPU
    cpu0 = geodesics.trace_kerr_formal((10.0,0.0,0.0), (-1.0,-0.05,0.0), mass=1.0, spin=(0.0,0.0,0.3), params={'npoints':64,'step':1e-3,'formal': True, 'use_numba': False})
    assert len(cpu0) == 64
    # final point difference smallish
    dx = abs(res[0][-1][0] - cpu0[-1][0])
    assert dx < 0.1
