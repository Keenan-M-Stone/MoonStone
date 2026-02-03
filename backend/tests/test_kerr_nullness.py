import pytest
import numpy as np
from app.geodesics import trace_kerr_formal, kerr_metric_cartesian as kerr_metric, kerr_r
try:
    from backend.app import accelerated_cuda as ac
    HAS_CUDA = ac.NUMBA_CUDA_OK
except Exception:
    HAS_CUDA = False


def null_residual_from_state(state, mass=1.0, a_param=0.3):
    # state: (x,y,z, ut, ux, uy, uz)
    x, y, z, ut, ux, uy, uz = float(state[0]), float(state[1]), float(state[2]), float(state[3]), float(state[4]), float(state[5]), float(state[6])
    g = kerr_metric(x, y, z, mass, a_param)
    # u vector: [ut, ux, uy, uz]
    u = np.array([ut, ux, uy, uz], dtype=float)
    res = 0.0
    for a in range(4):
        for b in range(4):
            res += g[a,b] * u[a] * u[b]
    return abs(res)


def test_kerr_nullness_cpu():
    src = (10.0, 0.0, 0.0)
    dir = (-1.0, -0.05, 0.0)
    states = trace_kerr_formal(src, dir, mass=1.0, spin=(0.0,0.0,0.3), params={'npoints': 64, 'step': 1e-3, 'formal': True, 'return_state': True})
    # each state is (x,y,z,ut,ux,uy,uz)
    residuals = [null_residual_from_state(s, mass=1.0, a_param=0.3) for s in states]
    assert max(residuals) < 1e-2

@pytest.mark.skipif(not HAS_CUDA, reason='CUDA not available')
def test_kerr_nullness_gpu():
    sources = np.array([[10.0, 0.0, 0.0]], dtype=float)
    dirs = np.array([[-1.0, -0.05, 0.0]], dtype=float)
    masses = np.array([1.0], dtype=float)
    params = {'npoints': 64, 'step': 1e-3, 'spin': (0.0,0.0,0.3)}
    res = ac.trace_kerr_rk4_gpu(sources, dirs, masses, params)
    pts = res[0]
    # approximate u via finite differences and compute ut solving quadratic: A ut^2 + B ut + C = 0
    max_res = 0.0
    for i in range(len(pts)-1):
        x1,y1,z1 = pts[i]
        x2,y2,z2 = pts[i+1]
        vx = (x2 - x1) / params['step']
        vy = (y2 - y1) / params['step']
        vz = (z2 - z1) / params['step']
        g = kerr_metric(x1, y1, z1)
        A = g[0,0]
        B = 2.0 * (g[0,1]*vx + g[0,2]*vy + g[0,3]*vz)
        C = g[1,1]*vx*vx + 2.0*g[1,2]*vx*vy + 2.0*g[1,3]*vx*vz + g[2,2]*vy*vy + 2.0*g[2,3]*vy*vz + g[3,3]*vz*vz
        disc = B*B - 4.0*A*C
        if disc < 0:
            disc = abs(disc)
        ut1 = (-B + np.sqrt(disc)) / (2.0 * A) if abs(2.0*A) > 1e-12 else 1.0
        ut = ut1 if ut1 > 0 else abs(ut1)
        u = np.array([ut, vx, vy, vz])
        resv = 0.0
        for a in range(4):
            for b in range(4):
                resv += g[a,b] * u[a] * u[b]
        max_res = max(max_res, abs(resv))
    assert max_res < 1e-1
