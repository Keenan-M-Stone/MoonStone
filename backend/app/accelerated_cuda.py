"""CUDA-accelerated geodesic kernels (POC).

This module provides GPU kernels for simple batched ray sampling. It's a
proof-of-concept and implements a vectorized, per-ray per-sample sampling
kernel for flat rays and a simple weak-field Schwarzschild lateral deflection.

Note: The kernel is intentionally simple for demonstration and benchmarking.
A production-grade solver (adaptive RK, Carter constants, horizon crossing)
would require a much more sophisticated implementation.
"""
from typing import Tuple, List, Dict
import numpy as np

try:
    from numba import cuda, float64, int32
    NUMBA_CUDA_OK = True
except Exception:
    NUMBA_CUDA_OK = False

# Tracks what was requested and what actually executed in wrappers/kernels (provenance)
_LAST_KERNEL_INFO = {'requested_analytic': False, 'executed_analytic': False}


if NUMBA_CUDA_OK:
    @cuda.jit
    def _kernel_flat(sx_arr, sy_arr, sz_arr, dx_arr, dy_arr, dz_arr, npoints, step, outx, outy, outz):
        i = cuda.grid(1)
        nrays = sx_arr.size
        if i >= nrays:
            return
        sx = sx_arr[i]; sy = sy_arr[i]; sz = sz_arr[i]
        dx = dx_arr[i]; dy = dy_arr[i]; dz = dz_arr[i]
        # normalize
        norm = (dx*dx + dy*dy + dz*dz) ** 0.5
        if norm == 0.0:
            norm = 1.0
        dx /= norm; dy /= norm; dz /= norm
        base = i * npoints
        for j in range(npoints):
            t = j * step
            outx[base + j] = sx + dx * t
            outy[base + j] = sy + dy * t
            outz[base + j] = sz + dz * t

    @cuda.jit
    def _kernel_schw(sx_arr, sy_arr, sz_arr, dx_arr, dy_arr, dz_arr, mass_arr, npoints, step, outx, outy, outz):
        i = cuda.grid(1)
        nrays = sx_arr.size
        if i >= nrays:
            return
        sx = sx_arr[i]; sy = sy_arr[i]; sz = sz_arr[i]
        dx = dx_arr[i]; dy = dy_arr[i]; dz = dz_arr[i]
        m = mass_arr[i]
        # normalize
        norm = (dx*dx + dy*dy + dz*dz) ** 0.5
        if norm == 0.0:
            norm = 1.0
        dx /= norm; dy /= norm; dz /= norm
        base = i * npoints
        for j in range(npoints):
            t = j * step
            x = sx + dx * t
            y = sy + dy * t
            z = sz + dz * t
            b = (y*y + z*z) ** 0.5 + 1e-12
            alpha = 4.0 * m / b
            # simple time-dependent small deflection term
            y += alpha * (t / (npoints * step + 1e-12)) * 1e-7
            outx[base + j] = x
            outy[base + j] = y
            outz[base + j] = z


def trace_flat_gpu(sources: np.ndarray, dirs: np.ndarray, params: Dict) -> List[List[Tuple[float,float,float]]]:
    if not NUMBA_CUDA_OK:
        raise RuntimeError('Numba CUDA not available')
    n_rays = sources.shape[0]
    npoints = int(params.get('npoints', 256))
    step = float(params.get('step', 1e-6))

    sx = sources[:,0].astype(np.float64)
    sy = sources[:,1].astype(np.float64)
    sz = sources[:,2].astype(np.float64)
    dx = dirs[:,0].astype(np.float64)
    dy = dirs[:,1].astype(np.float64)
    dz = dirs[:,2].astype(np.float64)

    outx = np.zeros(n_rays * npoints, dtype=np.float64)
    outy = np.zeros(n_rays * npoints, dtype=np.float64)
    outz = np.zeros(n_rays * npoints, dtype=np.float64)

    d_sx = cuda.to_device(sx)
    d_sy = cuda.to_device(sy)
    d_sz = cuda.to_device(sz)
    d_dx = cuda.to_device(dx)
    d_dy = cuda.to_device(dy)
    d_dz = cuda.to_device(dz)
    d_outx = cuda.to_device(outx)
    d_outy = cuda.to_device(outy)
    d_outz = cuda.to_device(outz)

    threads = 64
    blocks = (n_rays + threads - 1) // threads
    _kernel_flat[blocks, threads](d_sx, d_sy, d_sz, d_dx, d_dy, d_dz, npoints, step, d_outx, d_outy, d_outz)

    d_outx.copy_to_host(outx)
    d_outy.copy_to_host(outy)
    d_outz.copy_to_host(outz)

    results = []
    for i in range(n_rays):
        base = i * npoints
        pts = [ (float(outx[base + j]), float(outy[base + j]), float(outz[base + j])) for j in range(npoints) ]
        results.append(pts)
    return results


def trace_schwarzschild_gpu(sources: np.ndarray, dirs: np.ndarray, masses: np.ndarray, params: Dict) -> List[List[Tuple[float,float,float]]]:
    if not NUMBA_CUDA_OK:
        raise RuntimeError('Numba CUDA not available')
    n_rays = sources.shape[0]
    npoints = int(params.get('npoints', 256))
    step = float(params.get('step', 1e-6))

    sx = sources[:,0].astype(np.float64)
    sy = sources[:,1].astype(np.float64)
    sz = sources[:,2].astype(np.float64)
    dx = dirs[:,0].astype(np.float64)
    dy = dirs[:,1].astype(np.float64)
    dz = dirs[:,2].astype(np.float64)
    mass_arr = masses.astype(np.float64)

    outx = np.zeros(n_rays * npoints, dtype=np.float64)
    outy = np.zeros(n_rays * npoints, dtype=np.float64)
    outz = np.zeros(n_rays * npoints, dtype=np.float64)

    d_sx = cuda.to_device(sx)
    d_sy = cuda.to_device(sy)
    d_sz = cuda.to_device(sz)
    d_dx = cuda.to_device(dx)
    d_dy = cuda.to_device(dy)
    d_dz = cuda.to_device(dz)
    d_mass = cuda.to_device(mass_arr)
    d_outx = cuda.to_device(outx)
    d_outy = cuda.to_device(outy)
    d_outz = cuda.to_device(outz)

    threads = 64
    blocks = (n_rays + threads - 1) // threads
    _kernel_schw[blocks, threads](d_sx, d_sy, d_sz, d_dx, d_dy, d_dz, d_mass, npoints, step, d_outx, d_outy, d_outz)

    d_outx.copy_to_host(outx)
    d_outy.copy_to_host(outy)
    d_outz.copy_to_host(outz)

    results = []
    for i in range(n_rays):
        base = i * npoints
        pts = [ (float(outx[base + j]), float(outy[base + j]), float(outz[base + j])) for j in range(npoints) ]
        results.append(pts)
    return results

# RK4-style POC GPU wrappers (simple stepping for demonstration)
if NUMBA_CUDA_OK:
    @cuda.jit
    def _kernel_flat_rk4(sx_arr, sy_arr, sz_arr, dx_arr, dy_arr, dz_arr, npoints, step, outx, outy, outz):
        i = cuda.grid(1)
        nrays = sx_arr.size
        if i >= nrays:
            return
        sx = sx_arr[i]; sy = sy_arr[i]; sz = sz_arr[i]
        dx = dx_arr[i]; dy = dy_arr[i]; dz = dz_arr[i]
        # normalize
        norm = (dx*dx + dy*dy + dz*dz) ** 0.5
        if norm == 0.0:
            norm = 1.0
        dx /= norm; dy /= norm; dz /= norm
        base = i * npoints
        for j in range(npoints):
            t = j * step
            outx[base + j] = sx + dx * t
            outy[base + j] = sy + dy * t
            outz[base + j] = sz + dz * t

    def trace_flat_rk4_gpu(sources: np.ndarray, dirs: np.ndarray, params: Dict):
        # reuse simple kernel for POC (full RK4 would need ODE system)
        return trace_flat_gpu(sources, dirs, params)

    def trace_schwarzschild_rk4_gpu(sources: np.ndarray, dirs: np.ndarray, masses: np.ndarray, params: Dict):
        # Implement a simple RK4 integrator on GPU (batched per-ray)
        n_rays = sources.shape[0]
        npoints = int(params.get('npoints', 256))
        step = float(params.get('step', 1e-6))

        sx = sources[:,0].astype(np.float64)
        sy = sources[:,1].astype(np.float64)
        sz = sources[:,2].astype(np.float64)
        vx = dirs[:,0].astype(np.float64)
        vy = dirs[:,1].astype(np.float64)
        vz = dirs[:,2].astype(np.float64)
        mass_arr = masses.astype(np.float64)

        outx = np.zeros(n_rays * npoints, dtype=np.float64)
        outy = np.zeros(n_rays * npoints, dtype=np.float64)
        outz = np.zeros(n_rays * npoints, dtype=np.float64)

        d_sx = cuda.to_device(sx)
        d_sy = cuda.to_device(sy)
        d_sz = cuda.to_device(sz)
        d_vx = cuda.to_device(vx)
        d_vy = cuda.to_device(vy)
        d_vz = cuda.to_device(vz)
        d_mass = cuda.to_device(mass_arr)
        d_outx = cuda.to_device(outx)
        d_outy = cuda.to_device(outy)
        d_outz = cuda.to_device(outz)

        threads = 64
        blocks = (n_rays + threads - 1) // threads
        _kernel_schw_rk4[blocks, threads](d_sx, d_sy, d_sz, d_vx, d_vy, d_vz, d_mass, npoints, step, d_outx, d_outy, d_outz)

        d_outx.copy_to_host(outx)
        d_outy.copy_to_host(outy)
        d_outz.copy_to_host(outz)

        results = []
        for i in range(n_rays):
            base = i * npoints
            pts = [ (float(outx[base + j]), float(outy[base + j]), float(outz[base + j])) for j in range(npoints) ]
            results.append(pts)
        return results

    # --- POC Kerr GPU kernel & wrappers ---
    @cuda.jit
    def _kernel_kerr(sx_arr, sy_arr, sz_arr, dx_arr, dy_arr, dz_arr, sx_spin, sy_spin, sz_spin, mass_arr, npoints, step, outx, outy, outz):
        i = cuda.grid(1)
        nrays = sx_arr.size
        if i >= nrays:
            return
        sx = sx_arr[i]; sy = sy_arr[i]; sz = sz_arr[i]
        dx = dx_arr[i]; dy = dy_arr[i]; dz = dz_arr[i]
        Sx = sx_spin[i]; Sy = sy_spin[i]; Sz = sz_spin[i]
        m = mass_arr[i]
        # normalize
        norm = (dx*dx + dy*dy + dz*dz) ** 0.5
        if norm == 0.0:
            norm = 1.0
        dx /= norm; dy /= norm; dz /= norm
        base = i * npoints
        for j in range(npoints):
            t = j * step
            x = sx + dx * t
            y = sy + dy * t
            z = sz + dz * t
            # simple impact parameter deflection
            b = (y*y + z*z) ** 0.5 + 1e-12
            alpha = 4.0 * m / b
            # frame-dragging approximation: shift proportional to spin z-component and inverse r^3
            r = (x*x + y*y + z*z) ** 0.5 + 1e-12
            fd = Sz / (r**3 + 1e-12) * 1e-6
            y += alpha * (t / (npoints * step + 1e-12)) * 1e-7 + fd * (t / (npoints * step + 1e-12))
            # include small orthogonal deflection from Sx,Sy as toy model
            x += (Sx * 1e-8) * (t / (npoints * step + 1e-12))
            z += (Sy * 1e-8) * (t / (npoints * step + 1e-12))
            outx[base + j] = x
            outy[base + j] = y
            outz[base + j] = z

    def trace_kerr_gpu(sources: np.ndarray, dirs: np.ndarray, masses: np.ndarray, params: Dict):
        if not NUMBA_CUDA_OK:
            raise RuntimeError('Numba CUDA not available')
        n_rays = sources.shape[0]
        npoints = int(params.get('npoints', 256))
        step = float(params.get('step', 1e-6))

        sx = sources[:,0].astype(np.float64)
        sy = sources[:,1].astype(np.float64)
        sz = sources[:,2].astype(np.float64)
        dx = dirs[:,0].astype(np.float64)
        dy = dirs[:,1].astype(np.float64)
        dz = dirs[:,2].astype(np.float64)
        mass_arr = masses.astype(np.float64)
        # spin may be provided in params as a 3-tuple; broadcast
        spin = params.get('spin', (0.0, 0.0, 0.0))
        sx_spin = np.array([spin[0] for _ in range(n_rays)], dtype=np.float64)
        sy_spin = np.array([spin[1] for _ in range(n_rays)], dtype=np.float64)
        sz_spin = np.array([spin[2] for _ in range(n_rays)], dtype=np.float64)

        outx = np.zeros(n_rays * npoints, dtype=np.float64)
        outy = np.zeros(n_rays * npoints, dtype=np.float64)
        outz = np.zeros(n_rays * npoints, dtype=np.float64)

        d_sx = cuda.to_device(sx)
        d_sy = cuda.to_device(sy)
        d_sz = cuda.to_device(sz)
        d_dx = cuda.to_device(dx)
        d_dy = cuda.to_device(dy)
        d_dz = cuda.to_device(dz)
        d_sx_spin = cuda.to_device(sx_spin)
        d_sy_spin = cuda.to_device(sy_spin)
        d_sz_spin = cuda.to_device(sz_spin)
        d_mass = cuda.to_device(mass_arr)
        d_outx = cuda.to_device(outx)
        d_outy = cuda.to_device(outy)
        d_outz = cuda.to_device(outz)

        threads = 64
        blocks = (n_rays + threads - 1) // threads
        _kernel_kerr[blocks, threads](d_sx, d_sy, d_sz, d_dx, d_dy, d_dz, d_sx_spin, d_sy_spin, d_sz_spin, d_mass, npoints, step, d_outx, d_outy, d_outz)

        d_outx.copy_to_host(outx)
        d_outy.copy_to_host(outy)
        d_outz.copy_to_host(outz)

        results = []
        for i in range(n_rays):
            base = i * npoints
            pts = [ (float(outx[base + j]), float(outy[base + j]), float(outz[base + j])) for j in range(npoints) ]
            results.append(pts)
        return results

    def trace_kerr_rk4_gpu(sources: np.ndarray, dirs: np.ndarray, masses: np.ndarray, params: Dict):
        """GPU RK4 Kerr trace. If params['analytic'] is True (default), use fully-analytic device kernel.
        Set 'analytic' to False to use the faster approximate kernel.
        """
        if not NUMBA_CUDA_OK:
            raise RuntimeError('Numba CUDA not available')
        n_rays = sources.shape[0]
        npoints = int(params.get('npoints', 256))
        step = float(params.get('step', 1e-6))
        analytic = bool(params.get('analytic', True))

        sx = sources[:,0].astype(np.float64)
        sy = sources[:,1].astype(np.float64)
        sz = sources[:,2].astype(np.float64)
        dx = dirs[:,0].astype(np.float64)
        dy = dirs[:,1].astype(np.float64)
        dz = dirs[:,2].astype(np.float64)
        mass_arr = masses.astype(np.float64)
        spin = params.get('spin', (0.0, 0.0, 0.0))
        sx_spin = np.array([spin[0] for _ in range(n_rays)], dtype=np.float64)
        sy_spin = np.array([spin[1] for _ in range(n_rays)], dtype=np.float64)
        sz_spin = np.array([spin[2] for _ in range(n_rays)], dtype=np.float64)

        outx = np.zeros(n_rays * npoints, dtype=np.float64)
        outy = np.zeros(n_rays * npoints, dtype=np.float64)
        outz = np.zeros(n_rays * npoints, dtype=np.float64)

        d_sx = cuda.to_device(sx)
        d_sy = cuda.to_device(sy)
        d_sz = cuda.to_device(sz)
        d_dx = cuda.to_device(dx)
        d_dy = cuda.to_device(dy)
        d_dz = cuda.to_device(dz)
        d_sx_spin = cuda.to_device(sx_spin)
        d_sy_spin = cuda.to_device(sy_spin)
        d_sz_spin = cuda.to_device(sz_spin)
        d_mass = cuda.to_device(mass_arr)
        d_outx = cuda.to_device(outx)
        d_outy = cuda.to_device(outy)
        d_outz = cuda.to_device(outz)

        # heuristic threads tuning
        threads = 128 if n_rays < 1024 else 256
        blocks = (n_rays + threads - 1) // threads
        # provenance: record request and actual execution
        global _LAST_KERNEL_INFO
        _LAST_KERNEL_INFO['requested_analytic'] = analytic
        _LAST_KERNEL_INFO['executed_analytic'] = False
        if analytic:
            try:
                _kernel_kerr_rk4_analytic[blocks, threads](d_sx, d_sy, d_sz, d_dx, d_dy, d_dz, d_sx_spin, d_sy_spin, d_sz_spin, d_mass, npoints, step, d_outx, d_outy, d_outz)
                _LAST_KERNEL_INFO['executed_analytic'] = True
            except Exception:
                # fallback: try approximate kernel
                try:
                    _kernel_kerr_rk4_approx[blocks, threads](d_sx, d_sy, d_sz, d_dx, d_dy, d_dz, d_sx_spin, d_sy_spin, d_sz_spin, d_mass, npoints, step, d_outx, d_outy, d_outz)
                    _LAST_KERNEL_INFO['executed_analytic'] = False
                except Exception:
                    _LAST_KERNEL_INFO['executed_analytic'] = False
                    raise
        else:
            _kernel_kerr_rk4_approx[blocks, threads](d_sx, d_sy, d_sz, d_dx, d_dy, d_dz, d_sx_spin, d_sy_spin, d_sz_spin, d_mass, npoints, step, d_outx, d_outy, d_outz)
            _LAST_KERNEL_INFO['executed_analytic'] = False

        d_outx.copy_to_host(outx)
        d_outy.copy_to_host(outy)
        d_outz.copy_to_host(outz)

        results = []
        for i in range(n_rays):
            base = i * npoints
            pts = [ (float(outx[base + j]), float(outy[base + j]), float(outz[base + j])) for j in range(npoints) ]
            results.append(pts)
        return results

    # Higher-fidelity device RK4 kernel (approx analytic on-device)
    @cuda.jit
    def _kernel_kerr_rk4_approx(sx_arr, sy_arr, sz_arr, vx_arr, vy_arr, vz_arr, spinx, spiny, spinz, mass_arr, npoints, step, outx, outy, outz):
        i = cuda.grid(1)
        nrays = sx_arr.size
        if i >= nrays:
            return

        def kerr_r_newton(px, py, pz, a_local):
            r = ( (px*px + py*py + pz*pz) ** 0.5 )
            if r <= 0.0:
                r = 1e-6
            for _ in range(12):
                rho2 = px*px + py*py + pz*pz - a_local*a_local
                F = r**4 - rho2 * r*r - (a_local*a_local) * (pz*pz)
                dF = 4.0 * r**3 - 2.0 * rho2 * r
                if dF == 0.0:
                    break
                dr = F / dF
                r -= dr
                if dr > -1e-12 and dr < 1e-12:
                    break
            if r <= 0.0:
                r = 1e-6
            return r

        def kerr_H_l(px, py, pz, a_local, m_local):
            r = kerr_r_newton(px, py, pz, a_local)
            denom = (r**4 + (a_local*a_local) * (pz*pz)) + 1e-24
            H = m_local * (r**3) / denom
            d2 = r*r + a_local*a_local + 1e-12
            l0 = 1.0
            lx = (r * px + a_local * py) / d2
            ly = (r * py - a_local * px) / d2
            lz = pz / r
            return H, l0, lx, ly, lz

        sx = sx_arr[i]; sy = sy_arr[i]; sz = sz_arr[i]
        ux = vx_arr[i]; uy = vy_arr[i]; uz = vz_arr[i]
        Sx = spinx[i]; Sy = spiny[i]; Sz = spinz[i]
        m = mass_arr[i]
        base = i * npoints

        # normalize direction
        norm = (ux*ux + uy*uy + uz*uz) ** 0.5
        if norm == 0.0:
            norm = 1.0
        ux /= norm; uy /= norm; uz /= norm

        # choose scalar a from spin vector (use z-component if dominant)
        if abs(Sz) >= abs(Sx) and abs(Sz) >= abs(Sy):
            a_local = Sz
        else:
            a_local = Sx if abs(Sx) >= abs(Sy) else Sy

        # initial state
        x = sx; y = sy; z = sz
        vx_l = ux; vy_l = uy; vz_l = uz
        outx[base + 0] = x
        outy[base + 0] = y
        outz[base + 0] = z

        cnt = 1
        steps = 0
        max_steps = npoints * 8
        eps = 1e-5
        while cnt < npoints and steps < max_steps:
            H, l0, lx, ly, lz = kerr_H_l(x, y, z, a_local, m)
            # analytic dr/dx, dr/dy, dr/dz via implicit derivative of quartic
            r = kerr_r_newton(x, y, z, a_local)
            rho2 = x*x + y*y + z*z - a_local*a_local
            dF_dr = 4.0 * r**3 - 2.0 * rho2 * r
            if abs(dF_dr) < 1e-12:
                drdx = 0.0; drdy = 0.0; drdz = 0.0
            else:
                dF_dx = -2.0 * x * r*r
                dF_dy = -2.0 * y * r*r
                dF_dz = -2.0 * z * r*r - 2.0 * (a_local*a_local) * z
                drdx = -dF_dx / dF_dr
                drdy = -dF_dy / dF_dr
                drdz = -dF_dz / dF_dr
            # derivatives of denom = r^4 + a^2 z^2
            denom = (r**4 + (a_local*a_local) * (z*z)) + 1e-24
            ddenom_dx = 4.0 * r**3 * drdx
            ddenom_dy = 4.0 * r**3 * drdy
            ddenom_dz = 4.0 * r**3 * drdz + 2.0 * a_local*a_local * z
            # dH/dx etc using product/quotient rule
            dHdx = m * (3.0 * r*r * drdx * denom - r**3 * ddenom_dx) / (denom*denom)
            dHdy = m * (3.0 * r*r * drdy * denom - r**3 * ddenom_dy) / (denom*denom)
            dHdz = m * (3.0 * r*r * drdz * denom - r**3 * ddenom_dz) / (denom*denom)
            # derivatives of l components using dr partials
            d2 = r*r + a_local*a_local + 1e-12
            # dlx/dx
            dlx_dx = ((drdx * x + r) * d2 - (r*x + a_local*y) * (2.0 * r * drdx)) / (d2*d2)
            dlx_dy = ((drdy * x + 0.0) * d2 - (r*x + a_local*y) * (2.0 * r * drdy) - a_local * d2) / (d2*d2)
            dlx_dz = ((drdz * x + 0.0) * d2 - (r*x + a_local*y) * (2.0 * r * drdz)) / (d2*d2)
            dly_dx = ((drdx * y + 0.0) * d2 - (r*y - a_local*x) * (2.0 * r * drdx) + a_local * d2) / (d2*d2)
            dly_dy = ((drdy * y + r) * d2 - (r*y - a_local*x) * (2.0 * r * drdy)) / (d2*d2)
            dly_dz = ((drdz * y + 0.0) * d2 - (r*y - a_local*x) * (2.0 * r * drdz)) / (d2*d2)
            dlz_dx = - z * drdx / (r*r)
            dlz_dy = - z * drdy / (r*r)
            dlz_dz = (r - z * drdz) / (r*r)

            # analytic gradient of H*l_mu*l_nu projected to acceleration estimate
            # compute d(H*l_i*l_j)/dxj ~ dHdx * l_i*l_j + H*(dl_i_dxj * l_j + l_i * dl_j_dxj)
            # project to acceleration components (toy model)
            # For simplicity, compute scalar projections
            acc_x = -2.0 * (dHdx * lx * lx + dHdy * lx * ly + dHdz * lx * lz
                             + H * (dlx_dx * lx + lx * dlx_dx + dlx_dy * ly + lx * dly_dx + dlx_dz * lz + lx * dlz_dx)) * 1e-6
            acc_y = -2.0 * (dHdx * ly * lx + dHdy * ly * ly + dHdz * ly * lz
                             + H * (dly_dx * lx + ly * dlx_dx + dly_dy * ly + ly * dly_dy + dly_dz * lz + ly * dlz_dy)) * 1e-6
            acc_z = -2.0 * (dHdx * lz * lx + dHdy * lz * ly + dHdz * lz * lz
                             + H * (dlz_dx * lx + lz * dlx_dx + dlz_dy * ly + lz * dly_dy + dlz_dz * lz + lz * dlz_dz)) * 1e-6
            # RK4 for position and velocity (simplified 2nd-order integration)
            k1_vx = acc_x; k1_vy = acc_y; k1_vz = acc_z
            k1_x = vx_l; k1_y = vy_l; k1_z = vz_l

            xm = x + 0.5 * step * k1_x; ym = y + 0.5 * step * k1_y; zm = z + 0.5 * step * k1_z
            Hm = kerr_H_l(xm, ym, zm, a_local, m)[0]
            acc_x2 = -2.0 * ( (kerr_H_l(xm+eps,ym,zm,a_local,m)[0] - Hm)/eps * lx * lx ) * 1e-6
            acc_y2 = -2.0 * ( (kerr_H_l(xm,ym+eps,zm,a_local,m)[0] - Hm)/eps * ly * ly ) * 1e-6
            acc_z2 = -2.0 * ( (kerr_H_l(xm,ym,zm+eps,a_local,m)[0] - Hm)/eps * lz * lz ) * 1e-6
            k2_vx = acc_x2; k2_vy = acc_y2; k2_vz = acc_z2
            k2_x = vx_l + 0.5 * step * k1_vx; k2_y = vy_l + 0.5 * step * k1_vy; k2_z = vz_l + 0.5 * step * k1_vz

            xm = x + 0.5 * step * k2_x; ym = y + 0.5 * step * k2_y; zm = z + 0.5 * step * k2_z
            Hm = kerr_H_l(xm, ym, zm, a_local, m)[0]
            acc_x3 = -2.0 * ( (kerr_H_l(xm+eps,ym,zm,a_local,m)[0] - Hm)/eps * lx * lx ) * 1e-6
            acc_y3 = -2.0 * ( (kerr_H_l(xm,ym+eps,zm,a_local,m)[0] - Hm)/eps * ly * ly ) * 1e-6
            acc_z3 = -2.0 * ( (kerr_H_l(xm,ym,zm+eps,a_local,m)[0] - Hm)/eps * lz * lz ) * 1e-6
            k3_vx = acc_x3; k3_vy = acc_y3; k3_vz = acc_z3
            k3_x = vx_l + 0.5 * step * k2_vx; k3_y = vy_l + 0.5 * step * k2_vy; k3_z = vz_l + 0.5 * step * k2_vz

            xm = x + step * k3_x; ym = y + step * k3_y; zm = z + step * k3_z
            Hm = kerr_H_l(xm, ym, zm, a_local, m)[0]
            acc_x4 = -2.0 * ( (kerr_H_l(xm+eps,ym,zm,a_local,m)[0] - Hm)/eps * lx * lx ) * 1e-6
            acc_y4 = -2.0 * ( (kerr_H_l(xm,ym+eps,zm,a_local,m)[0] - Hm)/eps * ly * ly ) * 1e-6
            acc_z4 = -2.0 * ( (kerr_H_l(xm,ym,zm+eps,a_local,m)[0] - Hm)/eps * lz * lz ) * 1e-6
            k4_vx = acc_x4; k4_vy = acc_y4; k4_vz = acc_z4
            k4_x = vx_l + step * k3_vx; k4_y = vy_l + step * k3_vy; k4_z = vz_l + step * k3_vz

            vx_l = vx_l + (step/6.0) * (k1_vx + 2.0*k2_vx + 2.0*k3_vx + k4_vx)
            vy_l = vy_l + (step/6.0) * (k1_vy + 2.0*k2_vy + 2.0*k3_vy + k4_vy)
            vz_l = vz_l + (step/6.0) * (k1_vz + 2.0*k2_vz + 2.0*k3_vz + k4_vz)

            x = x + (step/6.0) * (k1_x + 2.0*k2_x + 2.0*k3_x + k4_x)
            y = y + (step/6.0) * (k1_y + 2.0*k2_y + 2.0*k3_y + k4_y)
            z = z + (step/6.0) * (k1_z + 2.0*k2_z + 2.0*k3_z + k4_z)

            outx[base + cnt] = x
            outy[base + cnt] = y
            outz[base + cnt] = z
            cnt += 1
            steps += 1

    # Fully-analytic device RK4 kernel (computes analytic dH/dx and dl/dx at each evaluation)
    @cuda.jit
    def _kernel_kerr_rk4_analytic(sx_arr, sy_arr, sz_arr, vx_arr, vy_arr, vz_arr, spinx, spiny, spinz, mass_arr, npoints, step, outx, outy, outz):
        i = cuda.grid(1)
        nrays = sx_arr.size
        if i >= nrays:
            return

        def kerr_r_newton(px, py, pz, a_local):
            r = ( (px*px + py*py + pz*pz) ** 0.5 )
            if r <= 0.0:
                r = 1e-6
            for _ in range(12):
                rho2 = px*px + py*py + pz*pz - a_local*a_local
                F = r**4 - rho2 * r*r - (a_local*a_local) * (pz*pz)
                dF = 4.0 * r**3 - 2.0 * rho2 * r
                if dF == 0.0:
                    break
                dr = F / dF
                r -= dr
                if dr > -1e-12 and dr < 1e-12:
                    break
            if r <= 0.0:
                r = 1e-6
            return r

        def kerr_H_l_and_partials(px, py, pz, a_local, m_local):
            # returns H,lx,ly,lz and partial derivatives dH/dx_j and dl_i/dx_j
            r = kerr_r_newton(px, py, pz, a_local)
            # dr/dx,y,z via implicit differentiation of the quartic
            rho2 = px*px + py*py + pz*pz - a_local*a_local
            dF_dr = 4.0 * r**3 - 2.0 * rho2 * r
            if abs(dF_dr) < 1e-12:
                drdx = 0.0; drdy = 0.0; drdz = 0.0
            else:
                dF_dx = -2.0 * px * r*r
                dF_dy = -2.0 * py * r*r
                dF_dz = -2.0 * pz * r*r - 2.0 * (a_local*a_local) * pz
                drdx = -dF_dx / dF_dr
                drdy = -dF_dy / dF_dr
                drdz = -dF_dz / dF_dr
            denom = (r**4 + (a_local*a_local) * (pz*pz)) + 1e-24
            H = m_local * (r**3) / denom
            # d denom partials
            ddenom_dx = 4.0 * r**3 * drdx
            ddenom_dy = 4.0 * r**3 * drdy
            ddenom_dz = 4.0 * r**3 * drdz + 2.0 * a_local*a_local * pz
            # dH/dx via quotient rule
            dHdx = m_local * (3.0 * r*r * drdx * denom - r**3 * ddenom_dx) / (denom*denom)
            dHdy = m_local * (3.0 * r*r * drdy * denom - r**3 * ddenom_dy) / (denom*denom)
            dHdz = m_local * (3.0 * r*r * drdz * denom - r**3 * ddenom_dz) / (denom*denom)
            d2 = r*r + a_local*a_local + 1e-12
            lx = (r * px + a_local * py) / d2
            ly = (r * py - a_local * px) / d2
            lz = pz / r
            # dl derivatives
            # dlx/dx etc
            dlx_dx = ((drdx * px + r) * d2 - (r*px + a_local*py) * (2.0 * r * drdx)) / (d2*d2)
            dlx_dy = ((drdy * px + 0.0) * d2 - (r*px + a_local*py) * (2.0 * r * drdy) - a_local * d2) / (d2*d2)
            dlx_dz = ((drdz * px + 0.0) * d2 - (r*px + a_local*py) * (2.0 * r * drdz)) / (d2*d2)
            dly_dx = ((drdx * py + 0.0) * d2 - (r*py - a_local*px) * (2.0 * r * drdx) + a_local * d2) / (d2*d2)
            dly_dy = ((drdy * py + r) * d2 - (r*py - a_local*px) * (2.0 * r * drdy)) / (d2*d2)
            dly_dz = ((drdz * py + 0.0) * d2 - (r*py - a_local*px) * (2.0 * r * drdz)) / (d2*d2)
            dlz_dx = - pz * drdx / (r*r)
            dlz_dy = - pz * drdy / (r*r)
            dlz_dz = (r - pz * drdz) / (r*r)
            return H, lx, ly, lz, dHdx, dHdy, dHdz, dlx_dx, dlx_dy, dlx_dz, dly_dx, dly_dy, dly_dz, dlz_dx, dlz_dy, dlz_dz

        sx = sx_arr[i]; sy = sy_arr[i]; sz = sz_arr[i]
        ux = vx_arr[i]; uy = vy_arr[i]; uz = vz_arr[i]
        Sx = spinx[i]; Sy = spiny[i]; Sz = spinz[i]
        m = mass_arr[i]
        base = i * npoints

        # normalize direction
        norm = (ux*ux + uy*uy + uz*uz) ** 0.5
        if norm == 0.0:
            norm = 1.0
        ux /= norm; uy /= norm; uz /= norm

        # choose scalar a from spin vector
        if abs(Sz) >= abs(Sx) and abs(Sz) >= abs(Sy):
            a_local = Sz
        else:
            a_local = Sx if abs(Sx) >= abs(Sy) else Sy

        x = sx; y = sy; z = sz
        vx_l = ux; vy_l = uy; vz_l = uz
        outx[base + 0] = x
        outy[base + 0] = y
        outz[base + 0] = z

        cnt = 1
        steps = 0
        max_steps = npoints * 8
        scale = 1e-6
        while cnt < npoints and steps < max_steps:
            # compute analytic H,l and derivatives at current
            H, lx, ly, lz, dHdx, dHdy, dHdz, dlx_dx, dlx_dy, dlx_dz, dly_dx, dly_dy, dly_dz, dlz_dx, dlz_dy, dlz_dz = kerr_H_l_and_partials(x, y, z, a_local, m)
            # Build inverse metric g^{mu nu} for Kerr-Schild: g^{-1} = eta^{-1} - 2 H l^mu l^nu (KS property)
            # raise l_mu via flat Minkowski (eta^{00}=-1, eta^{ii}=1)
            lcu0 = -1.0 * 1.0  # l0 is 1.0, so raised l^0 = -1.0
            lcu1 = lx; lcu2 = ly; lcu3 = lz
            # g^{-1} components (only need rows for spatial mu=1..3)
            ginv00 = -1.0 - 2.0 * H * (lcu0 * lcu0)
            ginv01 = 0.0 - 2.0 * H * (lcu0 * lcu1)
            ginv02 = 0.0 - 2.0 * H * (lcu0 * lcu2)
            ginv03 = 0.0 - 2.0 * H * (lcu0 * lcu3)
            ginv11 = 1.0 - 2.0 * H * (lcu1 * lcu1)
            ginv12 = 0.0 - 2.0 * H * (lcu1 * lcu2)
            ginv13 = 0.0 - 2.0 * H * (lcu1 * lcu3)
            ginv22 = 1.0 - 2.0 * H * (lcu2 * lcu2)
            ginv23 = 0.0 - 2.0 * H * (lcu2 * lcu3)
            ginv33 = 1.0 - 2.0 * H * (lcu3 * lcu3)
            # helper: get dH/dcoord
            dH = [dHdx, dHdy, dHdz]
            # helper: dl components derivatives mapping: dlx_dx etc
            # indexing: coord 0->x,1->y,2->z
            dl = (
                (0.0, 0.0, 0.0),
                (dlx_dx, dlx_dy, dlx_dz),
                (dly_dx, dly_dy, dly_dz),
                (dlz_dx, dlz_dy, dlz_dz)
            )
            # l components
            l = (l0, lx, ly, lz)
            # u^a approximation (time ~1, spatial = vx_l, vy_l, vz_l)
            u0 = 1.0; u1 = vx_l; u2 = vy_l; u3 = vz_l
            u = (u0, u1, u2, u3)

            # function to compute partial derivative of g_{a b} w.r.t coordinate idx (0=x,1=y,2=z)
            def dg_ab_coord(a_idx, b_idx, coord_idx):
                if coord_idx < 0:
                    return 0.0
                dh = dH[coord_idx]
                # dl_a_coord
                if a_idx == 0:
                    dla = 0.0
                else:
                    dla = dl[a_idx][coord_idx]
                if b_idx == 0:
                    dlb = 0.0
                else:
                    dlb = dl[b_idx][coord_idx]
                return 2.0 * (dh * l[a_idx] * l[b_idx] + H * (dla * l[b_idx] + l[a_idx] * dlb))

            # compute Gamma^i_{ab} u^a u^b for i=1..3
            acc_x = 0.0; acc_y = 0.0; acc_z = 0.0
            # helper to get ginv[i][alpha]
            def ginv_i_alpha(i, alpha):
                if i == 1:
                    if alpha == 0: return ginv01
                    if alpha == 1: return ginv11
                    if alpha == 2: return ginv12
                    return ginv13
                if i == 2:
                    if alpha == 0: return ginv02
                    if alpha == 1: return ginv12
                    if alpha == 2: return ginv22
                    return ginv23
                # i == 3
                if alpha == 0: return ginv03
                if alpha == 1: return ginv13
                if alpha == 2: return ginv23
                return ginv33

            for i_mu, acc_var in ((1, 0), (2, 1), (3, 2)):
                # compute Gamma^i_mu_ab contraction
                total = 0.0
                for a_idx in range(4):
                    for b_idx in range(4):
                        # partial index for coord derivative
                        # if derivative wrt time (index 0), treat as zero (stationary metric)
                        idx_nu = -1 if a_idx == 0 else (a_idx - 1)
                        idx_rho = -1 if b_idx == 0 else (b_idx - 1)
                        # sum over alpha
                        gamma = 0.0
                        for alpha in range(4):
                            alpha_idx = -1 if alpha == 0 else (alpha - 1)
                            term = 0.0
                            # d_g_{alpha b}/dx_nu + d_g_{alpha nu}/dx_b - d_g_{b nu}/dx_alpha
                            term += dg_ab_coord(alpha, b_idx, idx_nu) if idx_nu >= 0 else 0.0
                            term += dg_ab_coord(alpha, a_idx, idx_rho) if idx_rho >= 0 else 0.0
                            term -= dg_ab_coord(a_idx, b_idx, alpha_idx) if alpha_idx >= 0 else 0.0
                            gamma += 0.5 * ginv_i_alpha(i_mu, alpha) * term
                        total += gamma * u[a_idx] * u[b_idx]
                # subtract because a^i = - Gamma^i_ab u^a u^b
                if i_mu == 1:
                    acc_x = -total * scale
                elif i_mu == 2:
                    acc_y = -total * scale
                else:
                    acc_z = -total * scale

            # RK4 step (positions + velocities)
            k1_vx = acc_x; k1_vy = acc_y; k1_vz = acc_z
            k1_x = vx_l; k1_y = vy_l; k1_z = vz_l

            xm = x + 0.5 * step * k1_x; ym = y + 0.5 * step * k1_y; zm = z + 0.5 * step * k1_z
            Hm, lxm, lym, lzm, dHdxm, dHdym, dHdzm, dlxm_dx, dlxm_dy, dlxm_dz, dlym_dx, dlym_dy, dlym_dz, dlzm_dx, dlzm_dy, dlzm_dz = kerr_H_l_and_partials(xm, ym, zm, a_local, m)
            acc_x2 = -2.0 * (dHdxm * lxm * lxm + dHdym * lxm * lym + dHdzm * lxm * lzm + Hm * (dlxm_dx * lxm + dlxm_dy * lym + dlxm_dz * lzm + lxm * (dlxm_dx * lxm + dlym_dx * lym + dlzm_dx * lzm))) * scale
            acc_y2 = -2.0 * (dHdxm * lym * lxm + dHdym * lym * lym + dHdzm * lym * lzm + Hm * (dlym_dx * lxm + dlym_dy * lym + dlym_dz * lzm + lym * (dlxm_dy * lxm + dlym_dy * lym + dlzm_dy * lzm))) * scale
            acc_z2 = -2.0 * (dHdxm * lzm * lxm + dHdym * lzm * lym + dHdzm * lzm * lzm + Hm * (dlzm_dx * lxm + dlzm_dy * lym + dlzm_dz * lzm + lzm * (dlxm_dz * lxm + dlym_dz * lym + dlzm_dz * lzm))) * scale
            k2_vx = acc_x2; k2_vy = acc_y2; k2_vz = acc_z2
            k2_x = vx_l + 0.5 * step * k1_vx; k2_y = vy_l + 0.5 * step * k1_vy; k2_z = vz_l + 0.5 * step * k1_vz

            xm = x + 0.5 * step * k2_x; ym = y + 0.5 * step * k2_y; zm = z + 0.5 * step * k2_z
            Hm, lxm, lym, lzm, dHdxm, dHdym, dHdzm, dlxm_dx, dlxm_dy, dlxm_dz, dlym_dx, dlym_dy, dlym_dz, dlzm_dx, dlzm_dy, dlzm_dz = kerr_H_l_and_partials(xm, ym, zm, a_local, m)
            acc_x3 = -2.0 * (dHdxm * lxm * lxm + dHdym * lxm * lym + dHdzm * lxm * lzm + Hm * (dlxm_dx * lxm + dlxm_dy * lym + dlxm_dz * lzm + lxm * (dlxm_dx * lxm + dlym_dx * lym + dlzm_dx * lzm))) * scale
            acc_y3 = -2.0 * (dHdxm * lym * lxm + dHdym * lym * lym + dHdzm * lym * lzm + Hm * (dlym_dx * lxm + dlym_dy * lym + dlym_dz * lzm + lym * (dlxm_dy * lxm + dlym_dy * lym + dlzm_dy * lzm))) * scale
            acc_z3 = -2.0 * (dHdxm * lzm * lxm + dHdym * lzm * lym + dHdzm * lzm * lzm + Hm * (dlzm_dx * lxm + dlzm_dy * lym + dlzm_dz * lzm + lzm * (dlxm_dz * lxm + dlym_dz * lym + dlzm_dz * lzm))) * scale
            k3_vx = acc_x3; k3_vy = acc_y3; k3_vz = acc_z3
            k3_x = vx_l + 0.5 * step * k2_vx; k3_y = vy_l + 0.5 * step * k2_vy; k3_z = vz_l + 0.5 * step * k2_vz

            xm = x + step * k3_x; ym = y + step * k3_y; zm = z + step * k3_z
            Hm, lxm, lym, lzm, dHdxm, dHdym, dHdzm, dlxm_dx, dlxm_dy, dlxm_dz, dlym_dx, dlym_dy, dlym_dz, dlzm_dx, dlzm_dy, dlzm_dz = kerr_H_l_and_partials(xm, ym, zm, a_local, m)
            acc_x4 = -2.0 * (dHdxm * lxm * lxm + dHdym * lxm * lym + dHdzm * lxm * lzm + Hm * (dlxm_dx * lxm + dlxm_dy * lym + dlxm_dz * lzm + lxm * (dlxm_dx * lxm + dlym_dx * lym + dlzm_dx * lzm))) * scale
            acc_y4 = -2.0 * (dHdxm * lym * lxm + dHdym * lym * lym + dHdzm * lym * lzm + Hm * (dlym_dx * lxm + dlym_dy * lym + dlym_dz * lzm + lym * (dlxm_dy * lxm + dlym_dy * lym + dlzm_dy * lzm))) * scale
            acc_z4 = -2.0 * (dHdxm * lzm * lxm + dHdym * lzm * lym + dHdzm * lzm * lzm + Hm * (dlzm_dx * lxm + dlzm_dy * lym + dlzm_dz * lzm + lzm * (dlxm_dz * lxm + dlym_dz * lym + dlzm_dz * lzm))) * scale
            k4_vx = acc_x4; k4_vy = acc_y4; k4_vz = acc_z4
            k4_x = vx_l + step * k3_vx; k4_y = vy_l + step * k3_vy; k4_z = vz_l + step * k3_vz

            vx_l = vx_l + (step/6.0) * (k1_vx + 2.0*k2_vx + 2.0*k3_vx + k4_vx)
            vy_l = vy_l + (step/6.0) * (k1_vy + 2.0*k2_vy + 2.0*k3_vy + k4_vy)
            vz_l = vz_l + (step/6.0) * (k1_vz + 2.0*k2_vz + 2.0*k3_vz + k4_vz)

            x = x + (step/6.0) * (k1_x + 2.0*k2_x + 2.0*k3_x + k4_x)
            y = y + (step/6.0) * (k1_y + 2.0*k2_y + 2.0*k3_y + k4_y)
            z = z + (step/6.0) * (k1_z + 2.0*k2_z + 2.0*k3_z + k4_z)

            outx[base + cnt] = x
            outy[base + cnt] = y
            outz[base + cnt] = z
            cnt += 1
            steps += 1

    def trace_schwarzschild_rk4_adaptive_gpu(sources: np.ndarray, dirs: np.ndarray, masses: np.ndarray, params: Dict):
        """Per-ray adaptive GPU RK4 via selective refinement (improved POC).

        Strategy:
        - Start with an initial coarse pass for all rays.
        - Compute a finer pass and compare per-ray error.
        - Only re-run higher-resolution passes for rays that fail the tolerance.
        - Repeat per-ray refinement up to max_refine_factor.
        """
        if not NUMBA_CUDA_OK:
            raise RuntimeError('Numba CUDA not available')
        n_rays = sources.shape[0]
        npoints = int(params.get('npoints', 256))
        base_step = float(params.get('step', 1e-6))
        tol = float(params.get('tol', 1e-6))
        max_factor = int(params.get('max_refine_factor', 8))

        # initial coarse resolution
        current_factor = 1
        # track per-ray results and which rays still need refinement
        results = [None] * n_rays
        need_refine = list(range(n_rays))

        while current_factor <= max_factor and len(need_refine) > 0:
            # pick a working resolution based on factor
            n_work = max(8, npoints // (2 * current_factor))
            n_fine = n_work * 2
            params_coarse = {'npoints': n_work, 'step': base_step * (npoints / n_work)}
            params_fine = {'npoints': n_fine, 'step': base_step * (npoints / n_fine)}

            # prepare subset arrays for rays needing refinement
            sub_sources = sources[need_refine]
            sub_dirs = dirs[need_refine]
            sub_masses = masses[need_refine]

            coarse_sub = trace_schwarzschild_rk4_gpu(sub_sources, sub_dirs, sub_masses, params_coarse)
            fine_sub = trace_schwarzschild_rk4_gpu(sub_sources, sub_dirs, sub_masses, params_fine)

            # evaluate per-ray errors and accept or mark for further refinement
            next_need = []
            for idx_sub, global_idx in enumerate(need_refine):
                cpts = coarse_sub[idx_sub]
                fpts = fine_sub[idx_sub]
                # compare at mapped indices
                max_err = 0.0
                for j in range(min(len(cpts), len(fpts)//2)):
                    fj = 2*j
                    dx = cpts[j][0] - fpts[fj][0]
                    dy = cpts[j][1] - fpts[fj][1]
                    dz = cpts[j][2] - fpts[fj][2]
                    err = (dx*dx + dy*dy + dz*dz) ** 0.5
                    if err > max_err:
                        max_err = err
                    if err > tol:
                        break
                if max_err <= tol:
                    # accept fine_sub but resample to requested npoints
                    import numpy as _np
                    arr = _np.array(fpts)
                    idx = _np.linspace(0, arr.shape[0]-1, npoints).astype(int)
                    results[global_idx] = [ (float(x), float(y), float(z)) for x,y,z in arr[idx] ]
                else:
                    # needs further refinement
                    next_need.append(global_idx)
            need_refine = next_need
            current_factor *= 2

        # For any rays still unresolved, compute final high-res pass and trim
        if len(need_refine) > 0:
            sub_sources = sources[need_refine]
            sub_dirs = dirs[need_refine]
            sub_masses = masses[need_refine]
            params_final = {'npoints': npoints * min(current_factor, max_factor), 'step': base_step / min(current_factor, max_factor)}
            final_sub = trace_schwarzschild_rk4_gpu(sub_sources, sub_dirs, sub_masses, params_final)
            for idx_sub, global_idx in enumerate(need_refine):
                pts = final_sub[idx_sub][:npoints]
                results[global_idx] = [ (float(x), float(y), float(z)) for x,y,z in pts ]

        # ensure any None entries (should not happen) fall back to coarse compute
        for i in range(n_rays):
            if results[i] is None:
                # compute at requested resolution
                s = sources[i:i+1]
                d = dirs[i:i+1]
                m = masses[i:i+1]
                pts = trace_schwarzschild_rk4_gpu(s, d, m, {'npoints': npoints, 'step': base_step})[0]
                results[i] = [ (float(x), float(y), float(z)) for x,y,z in pts ]

        return results
    @cuda.jit
    def _kernel_schw_rk4(sx_arr, sy_arr, sz_arr, vx_arr, vy_arr, vz_arr, mass_arr, npoints, step, outx, outy, outz):
        i = cuda.grid(1)
        nrays = sx_arr.size
        if i >= nrays:
            return
        # initial state
        x = sx_arr[i]; y = sy_arr[i]; z = sz_arr[i]
        vx = vx_arr[i]; vy = vy_arr[i]; vz = vz_arr[i]
        m = mass_arr[i]
        base = i * npoints
        # store initial
        outx[base + 0] = x
        outy[base + 0] = y
        outz[base + 0] = z
        for j in range(1, npoints):
            # compute acceleration approx (weak-field radial attraction scaled small)
            rx = x; ry = y; rz = z
            r = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            # acceleration toward origin scaled by 4*m/r^2 but damped for stability
            ax = -4.0 * m * rx / (r**3 + 1e-12) * 1e-7
            ay = -4.0 * m * ry / (r**3 + 1e-12) * 1e-7
            az = -4.0 * m * rz / (r**3 + 1e-12) * 1e-7
            # RK4 steps for velocity and position
            k1_vx = ax; k1_vy = ay; k1_vz = az
            k1_x = vx; k1_y = vy; k1_z = vz

            # mid1
            xm = x + 0.5 * step * k1_x
            ym = y + 0.5 * step * k1_y
            zm = z + 0.5 * step * k1_z
            rx = xm; ry = ym; rz = zm
            r = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            ax2 = -4.0 * m * rx / (r**3 + 1e-12) * 1e-7
            ay2 = -4.0 * m * ry / (r**3 + 1e-12) * 1e-7
            az2 = -4.0 * m * rz / (r**3 + 1e-12) * 1e-7
            k2_vx = ax2; k2_vy = ay2; k2_vz = az2
            k2_x = vx + 0.5 * step * k1_vx; k2_y = vy + 0.5 * step * k1_vy; k2_z = vz + 0.5 * step * k1_vz

            # mid2
            xm = x + 0.5 * step * k2_x
            ym = y + 0.5 * step * k2_y
            zm = z + 0.5 * step * k2_z
            rx = xm; ry = ym; rz = zm
            r = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            ax3 = -4.0 * m * rx / (r**3 + 1e-12) * 1e-7
            ay3 = -4.0 * m * ry / (r**3 + 1e-12) * 1e-7
            az3 = -4.0 * m * rz / (r**3 + 1e-12) * 1e-7
            k3_vx = ax3; k3_vy = ay3; k3_vz = az3
            k3_x = vx + 0.5 * step * k2_vx; k3_y = vy + 0.5 * step * k2_vy; k3_z = vz + 0.5 * step * k2_vz

            # end
            xm = x + step * k3_x
            ym = y + step * k3_y
            zm = z + step * k3_z
            rx = xm; ry = ym; rz = zm
            r = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            ax4 = -4.0 * m * rx / (r**3 + 1e-12) * 1e-7
            ay4 = -4.0 * m * ry / (r**3 + 1e-12) * 1e-7
            az4 = -4.0 * m * rz / (r**3 + 1e-12) * 1e-7
            k4_vx = ax4; k4_vy = ay4; k4_vz = az4
            k4_x = vx + step * k3_vx; k4_y = vy + step * k3_vy; k4_z = vz + step * k3_vz

            vx = vx + (step/6.0) * (k1_vx + 2.0*k2_vx + 2.0*k3_vx + k4_vx)
            vy = vy + (step/6.0) * (k1_vy + 2.0*k2_vy + 2.0*k3_vy + k4_vy)
            vz = vz + (step/6.0) * (k1_vz + 2.0*k2_vz + 2.0*k3_vz + k4_vz)

            x = x + (step/6.0) * (k1_x + 2.0*k2_x + 2.0*k3_x + k4_x)
            y = y + (step/6.0) * (k1_y + 2.0*k2_y + 2.0*k3_y + k4_y)
            z = z + (step/6.0) * (k1_z + 2.0*k2_z + 2.0*k3_z + k4_z)

            outx[base + j] = x
            outy[base + j] = y
            outz[base + j] = z

    @cuda.jit
    def _kernel_schw_rk4_dev_adaptive(sx_arr, sy_arr, sz_arr, vx_arr, vy_arr, vz_arr, mass_arr, npoints, base_step, tol, max_steps, outx, outy, outz):
        i = cuda.grid(1)
        nrays = sx_arr.size
        if i >= nrays:
            return
        x = sx_arr[i]; y = sy_arr[i]; z = sz_arr[i]
        vx = vx_arr[i]; vy = vy_arr[i]; vz = vz_arr[i]
        m = mass_arr[i]
        base = i * npoints
        # store initial
        outx[base + 0] = x
        outy[base + 0] = y
        outz[base + 0] = z
        cnt = 1
        steps = 0
        h = base_step
        while cnt < npoints and steps < max_steps:
            # approximate acceleration magnitude
            rx = x; ry = y; rz = z
            r = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            ax = -4.0 * m * rx / (r**3 + 1e-12) * 1e-7
            ay = -4.0 * m * ry / (r**3 + 1e-12) * 1e-7
            az = -4.0 * m * rz / (r**3 + 1e-12) * 1e-7
            # adapt step based on local accel magnitude
            acc_mag = (ax*ax + ay*ay + az*az) ** 0.5
            if acc_mag > 0:
                h = base_step * (1.0 / (1.0 + acc_mag / (tol + 1e-16)))
            else:
                h = base_step
            # --- Step-doubling error control: compute full step and two half-steps ---
            # Full step
            # k1 full
            k1_vx = ax; k1_vy = ay; k1_vz = az
            k1_x = vx; k1_y = vy; k1_z = vz
            xm = x + 0.5 * h * k1_x; ym = y + 0.5 * h * k1_y; zm = z + 0.5 * h * k1_z
            rx = xm; ry = ym; rz = zm
            rmid = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            ax2 = -4.0 * m * rx / (rmid**3 + 1e-12) * 1e-7
            ay2 = -4.0 * m * ry / (rmid**3 + 1e-12) * 1e-7
            az2 = -4.0 * m * rz / (rmid**3 + 1e-12) * 1e-7
            k2_vx = ax2; k2_vy = ay2; k2_vz = az2
            k2_x = vx + 0.5 * h * k1_vx; k2_y = vy + 0.5 * h * k1_vy; k2_z = vz + 0.5 * h * k1_vz
            xm = x + 0.5 * h * k2_x; ym = y + 0.5 * h * k2_y; zm = z + 0.5 * h * k2_z
            rx = xm; ry = ym; rz = zm
            rmid = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            ax3 = -4.0 * m * rx / (rmid**3 + 1e-12) * 1e-7
            ay3 = -4.0 * m * ry / (rmid**3 + 1e-12) * 1e-7
            az3 = -4.0 * m * rz / (rmid**3 + 1e-12) * 1e-7
            k3_vx = ax3; k3_vy = ay3; k3_vz = az3
            k3_x = vx + 0.5 * h * k2_vx; k3_y = vy + 0.5 * h * k2_vy; k3_z = vz + 0.5 * h * k2_vz
            xm = x + h * k3_x; ym = y + h * k3_y; zm = z + h * k3_z
            rx = xm; ry = ym; rz = zm
            rmid = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            ax4 = -4.0 * m * rx / (rmid**3 + 1e-12) * 1e-7
            ay4 = -4.0 * m * ry / (rmid**3 + 1e-12) * 1e-7
            az4 = -4.0 * m * rz / (rmid**3 + 1e-12) * 1e-7
            k4_vx = ax4; k4_vy = ay4; k4_vz = az4
            k4_x = vx + h * k3_vx; k4_y = vy + h * k3_vy; k4_z = vz + h * k3_vz
            vx_full = vx + (h/6.0) * (k1_vx + 2.0*k2_vx + 2.0*k3_vx + k4_vx)
            vy_full = vy + (h/6.0) * (k1_vy + 2.0*k2_vy + 2.0*k3_vy + k4_vy)
            vz_full = vz + (h/6.0) * (k1_vz + 2.0*k2_vz + 2.0*k3_vz + k4_vz)
            x_full = x + (h/6.0) * (k1_x + 2.0*k2_x + 2.0*k3_x + k4_x)
            y_full = y + (h/6.0) * (k1_y + 2.0*k2_y + 2.0*k3_y + k4_y)
            z_full = z + (h/6.0) * (k1_z + 2.0*k2_z + 2.0*k3_z + k4_z)
            # Two half-steps
            h2 = 0.5 * h
            # first half
            # k1h
            rx = x; ry = y; rz = z
            r = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            axh = -4.0 * m * rx / (r**3 + 1e-12) * 1e-7
            ayh = -4.0 * m * ry / (r**3 + 1e-12) * 1e-7
            azh = -4.0 * m * rz / (r**3 + 1e-12) * 1e-7
            k1_vx_h = axh; k1_vy_h = ayh; k1_vz_h = azh
            k1_x_h = vx; k1_y_h = vy; k1_z_h = vz
            xm = x + 0.5 * h2 * k1_x_h; ym = y + 0.5 * h2 * k1_y_h; zm = z + 0.5 * h2 * k1_z_h
            rx = xm; ry = ym; rz = zm
            rmid = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            ax2h = -4.0 * m * rx / (rmid**3 + 1e-12) * 1e-7
            ay2h = -4.0 * m * ry / (rmid**3 + 1e-12) * 1e-7
            az2h = -4.0 * m * rz / (rmid**3 + 1e-12) * 1e-7
            k2_vx_h = ax2h; k2_vy_h = ay2h; k2_vz_h = az2h
            k2_x_h = vx + 0.5 * h2 * k1_vx_h; k2_y_h = vy + 0.5 * h2 * k1_vy_h; k2_z_h = vz + 0.5 * h2 * k1_vz_h
            xm = x + 0.5 * h2 * k2_x_h; ym = y + 0.5 * h2 * k2_y_h; zm = z + 0.5 * h2 * k2_z_h
            rx = xm; ry = ym; rz = zm
            rmid = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            ax3h = -4.0 * m * rx / (rmid**3 + 1e-12) * 1e-7
            ay3h = -4.0 * m * ry / (rmid**3 + 1e-12) * 1e-7
            az3h = -4.0 * m * rz / (rmid**3 + 1e-12) * 1e-7
            k3_vx_h = ax3h; k3_vy_h = ay3h; k3_vz_h = az3h
            k3_x_h = vx + 0.5 * h2 * k2_vx_h; k3_y_h = vy + 0.5 * h2 * k2_vy_h; k3_z_h = vz + 0.5 * h2 * k2_vz_h
            xm = x + h2 * k3_x_h; ym = y + h2 * k3_y_h; zm = z + h2 * k3_z_h
            rx = xm; ry = ym; rz = zm
            rmid = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            ax4h = -4.0 * m * rx / (rmid**3 + 1e-12) * 1e-7
            ay4h = -4.0 * m * ry / (rmid**3 + 1e-12) * 1e-7
            az4h = -4.0 * m * rz / (rmid**3 + 1e-12) * 1e-7
            k4_vx_h = ax4h; k4_vy_h = ay4h; k4_vz_h = az4h
            k4_x_h = vx + h2 * k3_vx_h; k4_y_h = vy + h2 * k3_vy_h; k4_z_h = vz + h2 * k3_vz_h
            vx_mid = vx + (h2/6.0) * (k1_vx_h + 2.0*k2_vx_h + 2.0*k3_vx_h + k4_vx_h)
            vy_mid = vy + (h2/6.0) * (k1_vy_h + 2.0*k2_vy_h + 2.0*k3_vy_h + k4_vy_h)
            vz_mid = vz + (h2/6.0) * (k1_vz_h + 2.0*k2_vz_h + 2.0*k3_vz_h + k4_vz_h)
            x_mid = x + (h2/6.0) * (k1_x_h + 2.0*k2_x_h + 2.0*k3_x_h + k4_x_h)
            y_mid = y + (h2/6.0) * (k1_y_h + 2.0*k2_y_h + 2.0*k3_y_h + k4_y_h)
            z_mid = z + (h2/6.0) * (k1_z_h + 2.0*k2_z_h + 2.0*k3_z_h + k4_z_h)
            # second half using mid as start
            rx = x_mid; ry = y_mid; rz = z_mid
            r = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            axh2 = -4.0 * m * rx / (r**3 + 1e-12) * 1e-7
            ayh2 = -4.0 * m * ry / (r**3 + 1e-12) * 1e-7
            azh2 = -4.0 * m * rz / (r**3 + 1e-12) * 1e-7
            k1_vx_h2 = axh2; k1_vy_h2 = ayh2; k1_vz_h2 = azh2
            k1_x_h2 = vx_mid; k1_y_h2 = vy_mid; k1_z_h2 = vz_mid
            xm = x_mid + 0.5 * h2 * k1_x_h2; ym = y_mid + 0.5 * h2 * k1_y_h2; zm = z_mid + 0.5 * h2 * k1_z_h2
            rx = xm; ry = ym; rz = zm
            rmid = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            ax2h2 = -4.0 * m * rx / (rmid**3 + 1e-12) * 1e-7
            ay2h2 = -4.0 * m * ry / (rmid**3 + 1e-12) * 1e-7
            az2h2 = -4.0 * m * rz / (rmid**3 + 1e-12) * 1e-7
            k2_vx_h2 = ax2h2; k2_vy_h2 = ay2h2; k2_vz_h2 = az2h2
            k2_x_h2 = vx_mid + 0.5 * h2 * k1_vx_h2; k2_y_h2 = vy_mid + 0.5 * h2 * k1_vy_h2; k2_z_h2 = vz_mid + 0.5 * h2 * k1_vz_h2
            xm = x_mid + 0.5 * h2 * k2_x_h2; ym = y_mid + 0.5 * h2 * k2_y_h2; zm = z_mid + 0.5 * h2 * k2_z_h2
            rx = xm; ry = ym; rz = zm
            rmid = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            ax3h2 = -4.0 * m * rx / (rmid**3 + 1e-12) * 1e-7
            ay3h2 = -4.0 * m * ry / (rmid**3 + 1e-12) * 1e-7
            az3h2 = -4.0 * m * rz / (rmid**3 + 1e-12) * 1e-7
            k3_vx_h2 = ax3h2; k3_vy_h2 = ay3h2; k3_vz_h2 = az3h2
            k3_x_h2 = vx_mid + 0.5 * h2 * k2_vx_h2; k3_y_h2 = vy_mid + 0.5 * h2 * k2_vy_h2; k3_z_h2 = vz_mid + 0.5 * h2 * k2_vz_h2
            xm = x_mid + h2 * k3_x_h2; ym = y_mid + h2 * k3_y_h2; zm = z_mid + h2 * k3_z_h2
            rx = xm; ry = ym; rz = zm
            rmid = (rx*rx + ry*ry + rz*rz) ** 0.5 + 1e-12
            ax4h2 = -4.0 * m * rx / (rmid**3 + 1e-12) * 1e-7
            ay4h2 = -4.0 * m * ry / (rmid**3 + 1e-12) * 1e-7
            az4h2 = -4.0 * m * rz / (rmid**3 + 1e-12) * 1e-7
            k4_vx_h2 = ax4h2; k4_vy_h2 = ay4h2; k4_vz_h2 = az4h2
            k4_x_h2 = vx_mid + h2 * k3_vx_h2; k4_y_h2 = vy_mid + h2 * k3_vy_h2; k4_z_h2 = vz_mid + h2 * k3_vz_h2
            vx_half = vx_mid + (h2/6.0) * (k1_vx_h2 + 2.0*k2_vx_h2 + 2.0*k3_vx_h2 + k4_vx_h2)
            vy_half = vy_mid + (h2/6.0) * (k1_vy_h2 + 2.0*k2_vy_h2 + 2.0*k3_vy_h2 + k4_vy_h2)
            vz_half = vz_mid + (h2/6.0) * (k1_vz_h2 + 2.0*k2_vz_h2 + 2.0*k3_vz_h2 + k4_vz_h2)
            x_half = x_mid + (h2/6.0) * (k1_x_h2 + 2.0*k2_x_h2 + 2.0*k3_x_h2 + k4_x_h2)
            y_half = y_mid + (h2/6.0) * (k1_y_h2 + 2.0*k2_y_h2 + 2.0*k3_y_h2 + k4_y_h2)
            z_half = z_mid + (h2/6.0) * (k1_z_h2 + 2.0*k2_z_h2 + 2.0*k3_z_h2 + k4_z_h2)
            # error estimate (RK4 -> O(h^5) -> factor ~1/15)
            dx = x_full - x_half
            dy = y_full - y_half
            dz = z_full - z_half
            err = (dx*dx + dy*dy + dz*dz) ** 0.5
            if err <= tol:
                # accept half-step result
                vx = vx_half; vy = vy_half; vz = vz_half
                x = x_half; y = y_half; z = z_half
                outx[base + cnt] = x
                outy[base + cnt] = y
                outz[base + cnt] = z
                cnt += 1
                # gentle increase of h
                h = min(2.0*h, base_step*4.0)
                steps += 1
            else:
                # reduce h and retry
                h = 0.5 * h
                steps += 1

    def trace_schwarzschild_rk4_device_adaptive_error(sources: np.ndarray, dirs: np.ndarray, masses: np.ndarray, params: Dict):
        if not NUMBA_CUDA_OK:
            raise RuntimeError('Numba CUDA not available')
        n_rays = sources.shape[0]
        npoints = int(params.get('npoints', 256))
        base_step = float(params.get('step', 1e-6))
        tol = float(params.get('tol', 1e-6))
        max_steps = int(params.get('max_steps', 10000))

        sx = sources[:,0].astype(np.float64)
        sy = sources[:,1].astype(np.float64)
        sz = sources[:,2].astype(np.float64)
        vx = dirs[:,0].astype(np.float64)
        vy = dirs[:,1].astype(np.float64)
        vz = dirs[:,2].astype(np.float64)
        mass_arr = masses.astype(np.float64)

        outx = np.zeros(n_rays * npoints, dtype=np.float64)
        outy = np.zeros(n_rays * npoints, dtype=np.float64)
        outz = np.zeros(n_rays * npoints, dtype=np.float64)

        d_sx = cuda.to_device(sx)
        d_sy = cuda.to_device(sy)
        d_sz = cuda.to_device(sz)
        d_vx = cuda.to_device(vx)
        d_vy = cuda.to_device(vy)
        d_vz = cuda.to_device(vz)
        d_mass = cuda.to_device(mass_arr)
        d_outx = cuda.to_device(outx)
        d_outy = cuda.to_device(outy)
        d_outz = cuda.to_device(outz)

        threads = 64
        blocks = (n_rays + threads - 1) // threads
        _kernel_schw_rk4_dev_adaptive[blocks, threads](d_sx, d_sy, d_sz, d_vx, d_vy, d_vz, d_mass, npoints, base_step, tol, max_steps, d_outx, d_outy, d_outz)

        d_outx.copy_to_host(outx)
        d_outy.copy_to_host(outy)
        d_outz.copy_to_host(outz)

        results = []
        for i in range(n_rays):
            base = i * npoints
            pts = [ (float(outx[base + j]), float(outy[base + j]), float(outz[base + j])) for j in range(npoints) ]
            results.append(pts)
        return results

    def trace_flat_gpu(*args, **kwargs):
        raise RuntimeError('Numba CUDA not available')
    def trace_schwarzschild_gpu(*args, **kwargs):
        raise RuntimeError('Numba CUDA not available')


    def trace_schwarzschild_rk4_device_adaptive(sources: np.ndarray, dirs: np.ndarray, masses: np.ndarray, params: Dict):
        if not NUMBA_CUDA_OK:
            raise RuntimeError('Numba CUDA not available')
        n_rays = sources.shape[0]
        npoints = int(params.get('npoints', 256))
        base_step = float(params.get('step', 1e-6))
        tol = float(params.get('tol', 1e-6))
        max_steps = int(params.get('max_steps', 10000))

        sx = sources[:,0].astype(np.float64)
        sy = sources[:,1].astype(np.float64)
        sz = sources[:,2].astype(np.float64)
        vx = dirs[:,0].astype(np.float64)
        vy = dirs[:,1].astype(np.float64)
        vz = dirs[:,2].astype(np.float64)
        mass_arr = masses.astype(np.float64)

        outx = np.zeros(n_rays * npoints, dtype=np.float64)
        outy = np.zeros(n_rays * npoints, dtype=np.float64)
        outz = np.zeros(n_rays * npoints, dtype=np.float64)

        d_sx = cuda.to_device(sx)
        d_sy = cuda.to_device(sy)
        d_sz = cuda.to_device(sz)
        d_vx = cuda.to_device(vx)
        d_vy = cuda.to_device(vy)
        d_vz = cuda.to_device(vz)
        d_mass = cuda.to_device(mass_arr)
        d_outx = cuda.to_device(outx)
        d_outy = cuda.to_device(outy)
        d_outz = cuda.to_device(outz)

        threads = 64
        blocks = (n_rays + threads - 1) // threads
        _kernel_schw_rk4_dev_adaptive[blocks, threads](d_sx, d_sy, d_sz, d_vx, d_vy, d_vz, d_mass, npoints, base_step, tol, max_steps, d_outx, d_outy, d_outz)

        d_outx.copy_to_host(outx)
        d_outy.copy_to_host(outy)
        d_outz.copy_to_host(outz)

        results = []
        for i in range(n_rays):
            base = i * npoints
            pts = [ (float(outx[base + j]), float(outy[base + j]), float(outz[base + j])) for j in range(npoints) ]
            results.append(pts)
        return results

    def trace_flat_gpu(*args, **kwargs):
        raise RuntimeError('Numba CUDA not available')
    def trace_schwarzschild_gpu(*args, **kwargs):
        raise RuntimeError('Numba CUDA not available')

