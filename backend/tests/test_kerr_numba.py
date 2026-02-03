import pytest
try:
    from app import geodesics
    from app import accelerated as ac
    HAS_NUMBA = ac._NUMBA_OK
except Exception:
    HAS_NUMBA = False

@pytest.mark.skipif(not HAS_NUMBA, reason='Numba not available')
def test_kerr_numba_matches_cpu():
    src = (10.0, 0.0, 0.0)
    dir = (-1.0, -0.05, 0.0)
    cpu = geodesics.trace_kerr_formal(src, dir, mass=1.0, spin=(0.0,0.0,0.3), params={'npoints': 48, 'step': 1e-3, 'formal': True, 'use_numba': False})
    numby = ac.trace_kerr_numba(src[0], src[1], src[2], dir[0], dir[1], dir[2], 1.0, 0.0, 0.0, 0.3, 48, 1e-3, 0.3)
    assert len(cpu) == len(numby)
    # allow loose elementwise tolerance
    diffs = [((cpu[i][0]-numby[i][0])**2 + (cpu[i][1]-numby[i][1])**2 + (cpu[i][2]-numby[i][2])**2)**0.5 for i in range(len(cpu))]
    assert max(diffs) < 1e-2
