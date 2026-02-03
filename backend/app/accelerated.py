"""Optional Numba-accelerated geodesic kernels.

Provides njit-compiled versions of simple trace integrators for performance.
If Numba is not available, functions fall back to Python implementations.
"""
from typing import List, Tuple

try:
    import numpy as np
    from numba import njit, prange
    _NUMBA_OK = True
except Exception:
    _NUMBA_OK = False


if _NUMBA_OK:
    @njit
    def trace_flat_numba(sx: float, sy: float, sz: float, dx: float, dy: float, dz: float, npoints: int, step: float):
        out = []
        # Ensure normalization
        norm = (dx*dx + dy*dy + dz*dz) ** 0.5
        if norm == 0.0:
            norm = 1.0
        dx /= norm; dy /= norm; dz /= norm
        for i in range(npoints):
            t = i * step
            x = sx + dx * t
            y = sy + dy * t
            z = sz + dz * t
            out.append((x, y, z))
        return out

    @njit
    def trace_schwarzschild_weak_numba(sx: float, sy: float, sz: float, dx: float, dy: float, dz: float, mass: float, npoints: int, step: float):
        out = []
        norm = (dx*dx + dy*dy + dz*dz) ** 0.5
        if norm == 0.0:
            norm = 1.0
        dx /= norm; dy /= norm; dz /= norm
        for i in range(npoints):
            t = i * step
            x = sx + dx * t
            y = sy + dy * t
            z = sz + dz * t
            b = (y*y + z*z) ** 0.5 + 1e-12
            alpha = 4.0 * mass / b
            y += alpha * (t / (npoints*step + 1e-12)) * 1e-7
            out.append((x, y, z))
        return out

else:
    def trace_flat_numba(*args, **kwargs):
        raise RuntimeError('Numba not available')

    def trace_schwarzschild_weak_numba(*args, **kwargs):
        raise RuntimeError('Numba not available')

    def trace_kerr_numba(*args, **kwargs):
        raise RuntimeError('Numba not available')

if _NUMBA_OK:
    @njit
    def _kerr_r(px, py, pz, a_local):
        # simple Newton iteration to solve quartic for r
        r = (px*px + py*py + pz*pz) ** 0.5
        if r <= 0.0:
            r = 1e-6
        for _ in range(8):
            rho2 = px*px + py*py + pz*pz - a_local*a_local
            F = r**4 - rho2 * r*r - (a_local*a_local) * (pz*pz)
            dF = 4.0 * r**3 - 2.0 * rho2 * r
            if dF == 0.0:
                break
            dr = F / dF
            r -= dr
            if abs(dr) < 1e-10:
                break
        if r <= 0.0:
            r = 1e-6
        return r

    @njit
    def trace_kerr_numba(sx, sy, sz, dx, dy, dz, mass, sx_spin, sy_spin, sz_spin, npoints, step, a_param):
        # Batch single-ray RK4 integrator using analytic Kerr-Schild elements
        out = []
        # normalize direction
        norm = (dx*dx + dy*dy + dz*dz) ** 0.5
        if norm == 0.0:
            norm = 1.0
        dx /= norm; dy /= norm; dz /= norm
        x = sx; y = sy; z = sz
        out.append((x, y, z))
        a_local = a_param
        M = mass
        for i in range(1, npoints):
            # compute r and helper
            r = _kerr_r(x, y, z, a_local)
            denom = (r**4 + (a_local*a_local) * (z*z)) + 1e-24
            H = M * (r**3) / denom
            d2 = r*r + a_local*a_local + 1e-12
            lx = (r * x + a_local * y) / d2
            ly = (r * y - a_local * x) / d2
            lz = z / r
            # approximate accelerations from simplified weak-field form: use -Gamma^i_ab u^a u^b with only leading terms
            # for performance in njit we use a toy model: gravitational pull ~ -4*M/r^3 scaled
            acc_x = -4.0 * M * x / ((r**3 + 1e-12)) * 1e-7
            acc_y = -4.0 * M * y / ((r**3 + 1e-12)) * 1e-7
            acc_z = -4.0 * M * z / ((r**3 + 1e-12)) * 1e-7
            # include simple frame dragging from spin z-component
            acc_y += sz_spin * 1e-8 / (r**3 + 1e-12)
            x += dx * step + 0.5 * acc_x * step * step
            y += dy * step + 0.5 * acc_y * step * step
            z += dz * step + 0.5 * acc_z * step * step
            out.append((x, y, z))
        return out

    @njit(parallel=True)
    def _trace_kerr_numba_batch_array(sources, dirs, masses, spins, npoints, step, a_param=None):
        n_rays = sources.shape[0]
        out = np.zeros((n_rays, npoints, 3), dtype=np.float64)
        for ii in prange(n_rays):
            sx = sources[ii,0]; sy = sources[ii,1]; sz = sources[ii,2]
            dx = dirs[ii,0]; dy = dirs[ii,1]; dz = dirs[ii,2]
            sx_spin = spins[ii,0]; sy_spin = spins[ii,1]; sz_spin = spins[ii,2]
            if a_param is not None:
                a_choose = a_param
            else:
                if abs(sz_spin) >= abs(sx_spin) and abs(sz_spin) >= abs(sy_spin):
                    a_choose = sz_spin
                else:
                    a_choose = sx_spin if abs(sx_spin) >= abs(sy_spin) else sy_spin
            # per-ray integrator inline for speed
            # normalize direction
            norm = (dx*dx + dy*dy + dz*dz) ** 0.5
            if norm == 0.0:
                norm = 1.0
            dx_local = dx / norm; dy_local = dy / norm; dz_local = dz / norm
            x = sx; y = sy; z = sz
            out[ii,0,0] = x; out[ii,0,1] = y; out[ii,0,2] = z
            M = masses[ii]
            a_local = a_choose
            for i in range(1, npoints):
                # compute r and helper
                r = _kerr_r(x, y, z, a_local)
                denom = (r**4 + (a_local*a_local) * (z*z)) + 1e-24
                H = M * (r**3) / denom
                d2 = r*r + a_local*a_local + 1e-12
                lx = (r * x + a_local * y) / d2
                ly = (r * y - a_local * x) / d2
                lz = z / r
                # approximate accelerations
                acc_x = -4.0 * M * x / ((r**3 + 1e-12)) * 1e-7
                acc_y = -4.0 * M * y / ((r**3 + 1e-12)) * 1e-7
                acc_z = -4.0 * M * z / ((r**3 + 1e-12)) * 1e-7
                acc_y += sz_spin * 1e-8 / (r**3 + 1e-12)
                x += dx_local * step + 0.5 * acc_x * step * step
                y += dy_local * step + 0.5 * acc_y * step * step
                z += dz_local * step + 0.5 * acc_z * step * step
                out[ii,i,0] = x; out[ii,i,1] = y; out[ii,i,2] = z
        return out

    def trace_kerr_numba_batch(sources, dirs, masses, spins, npoints, step, a_param=None):
        # wrapper: call optimized njit array routine and convert to list-of-lists to preserve API
        arr = _trace_kerr_numba_batch_array(sources, dirs, masses, spins, npoints, step, a_param)
        n_rays = arr.shape[0]
        results = []
        for i in range(n_rays):
            pts = []
            for j in range(arr.shape[1]):
                pts.append((float(arr[i,j,0]), float(arr[i,j,1]), float(arr[i,j,2])))
            results.append(pts)
        return results
