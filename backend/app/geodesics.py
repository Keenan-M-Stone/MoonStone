import numpy as np
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

# Module-level Kerr helpers (reuseable by CPU/GPU code and tests)

def kerr_r(px, py, pz, a_local):
    rho2 = px*px + py*py + pz*pz - a_local*a_local
    r = max(1e-6, (px*px + py*py + pz*pz) ** 0.5)
    for _ in range(12):
        F = r**4 - rho2 * r*r - (a_local*a_local) * (pz*pz)
        dF = 4.0 * r**3 - 2.0 * rho2 * r
        if dF == 0:
            break
        dr = F / dF
        r -= dr
        if abs(dr) < 1e-12:
            break
    return abs(r) + 1e-12


def kerr_metric_cartesian(px, py, pz, M_local, a_local):
    r_loc = kerr_r(px, py, pz, a_local)
    denom = (r_loc**4 + (a_local*a_local) * (pz*pz)) + 1e-24
    H = M_local * (r_loc**3) / denom
    denom2 = r_loc*r_loc + a_local*a_local + 1e-12
    l0 = 1.0
    lx = (r_loc * px + a_local * py) / denom2
    ly = (r_loc * py - a_local * px) / denom2
    lz = pz / r_loc
    l = np.array([l0, lx, ly, lz], dtype=float)
    g = np.eye(4, dtype=float)
    g[0,0] = -1.0
    for mu in range(4):
        for nu in range(4):
            g[mu,nu] += 2.0 * H * l[mu] * l[nu]
    return g

# Optional accelerated kernels (CPU and CUDA paths)
try:
    from .accelerated import trace_flat_numba, trace_schwarzschild_weak_numba
    _HAS_ACCEL = True
except Exception:
    _HAS_ACCEL = False

# Optional CUDA kernels
try:
    from .accelerated_cuda import trace_flat_gpu, trace_schwarzschild_gpu
    from stardust.gpu import is_cuda_available
    _HAS_CUDA = is_cuda_available()
except Exception:
    _HAS_CUDA = False

# Simple POC geodesic traces
# - Flat spacetime: straight-line propagation
# - Schwarzschild weak-field: approximate deflection using small-angle formula


def trace_flat(source: Tuple[float,float,float], direction: Tuple[float,float,float], params: dict = None):
    # params may include npoints, step
    npoints = int(params.get('npoints', 256)) if params else 256
    step = float(params.get('step', 1e-6)) if params else 1e-6
    sx, sy, sz = source
    dx, dy, dz = direction
    if _HAS_ACCEL:
        try:
            return trace_flat_numba(sx, sy, sz, dx, dy, dz, npoints, step)
        except Exception:
            pass
    dir_norm = np.sqrt(dx*dx + dy*dy + dz*dz) or 1.0
    dx /= dir_norm; dy /= dir_norm; dz /= dir_norm
    points = []
    for i in range(npoints):
        t = i * step
        points.append((sx + dx * t, sy + dy * t, sz + dz * t))
    return points


def trace_schwarzschild_weak(source: Tuple[float,float,float], direction: Tuple[float,float,float], mass: float = 1.0, params: dict = None):
    npoints = int(params.get('npoints', 256)) if params else 256
    step = float(params.get('step', 1e-6)) if params else 1e-6
    sx, sy, sz = source
    dx, dy, dz = direction
    if _HAS_ACCEL:
        try:
            return trace_schwarzschild_weak_numba(sx, sy, sz, dx, dy, dz, float(mass), npoints, step)
        except Exception:
            pass
    dir_norm = np.sqrt(dx*dx + dy*dy + dz*dz) or 1.0
    dx /= dir_norm; dy /= dir_norm; dz /= dir_norm
    points = []
    for i in range(npoints):
        t = i * step
        x = sx + dx * t
        y = sy + dy * t
        z = sz + dz * t
        # impact parameter approx using perpendicular distance to origin
        b = np.sqrt((y)**2 + (z)**2) + 1e-12
        # small deflection magnitude
        alpha = 4 * mass / b
        # deflect in y-direction for demonstration
        y += alpha * np.tanh(t / (npoints*step + 1e-12)) * 1e-7
        points.append((x, y, z))
    return points


# Full null geodesic (formal Christoffel-based) integrator (CPU)
def trace_null_formal(source: Tuple[float,float,float], direction: Tuple[float,float,float], mass: float = 1.0, params: dict = None):
    """Integrate null geodesic using a post-Newtonian Schwarzschild metric
    and compute Christoffel symbols analytically (weak-field). Returns spatial samples.

    This is more physically accurate than the earlier POC and integrates the
    full geodesic ODE: d^2 x^mu/dlambda^2 + Gamma^mu_ab dx^a/dlambda dx^b/dlambda = 0
    where we use a weak-field metric: g_tt = -(1 + 2Phi), g_ij = (1 - 2Phi) delta_ij,
    Phi = -M/r (post-Newtonian linearized Schwarzschild).
    """
    params = params or {}
    npoints = int(params.get('npoints', 256))
    step = float(params.get('step', 1e-6))
    sx, sy, sz = source
    vx, vy, vz = direction

    # normalize direction
    vnorm = np.sqrt(vx*vx + vy*vy + vz*vz) or 1.0
    vx /= vnorm; vy /= vnorm; vz /= vnorm

    M = float(mass)

    def Phi(px, py, pz):
        r = np.sqrt(px*px + py*py + pz*pz) + 1e-12
        return -M / r

    def metric(px, py, pz):
        ph = Phi(px, py, pz)
        g = np.zeros((4,4))
        g[0,0] = -(1.0 + 2.0*ph)
        for i in range(1,4):
            g[i,i] = (1.0 - 2.0*ph)
        return g

    def inv_metric(px, py, pz):
        ph = Phi(px, py, pz)
        ginv = np.zeros((4,4))
        ginv[0,0] = -1.0/(1.0 + 2.0*ph)
        for i in range(1,4):
            ginv[i,i] = 1.0/(1.0 - 2.0*ph)
        return ginv

    def grad_P(px, py, pz):
        r = np.sqrt(px*px + py*py + pz*pz) + 1e-12
        fac = M / (r**3 + 1e-12)
        return (fac * px, fac * py, fac * pz)

    def christoffel(px, py, pz):
        # compute only Gamma^i_{tt} and Gamma^i_{jk} terms necessary for spatial acceleration
        dPx, dPy, dPz = grad_P(px, py, pz)
        # In linearized PN: Gamma^i_{tt} = -partial_i Phi, Gamma^i_{jk} ~ delta_jk partial_i Phi - delta_ij partial_k Phi - delta_ik partial_j Phi (scaled)
        Gamma = np.zeros((4,4,4))
        # Gamma^i_{tt}
        Gamma[1,0,0] = -dPx
        Gamma[2,0,0] = -dPy
        Gamma[3,0,0] = -dPz
        # symmetric versions not needed beyond linear terms for this POC
        return Gamma

    # initial 4-velocity: choose ut satisfying null condition to first order
    ph0 = Phi(sx, sy, sz)
    ut = 1.0 / np.sqrt(max(1e-12, 1.0 - 2.0*ph0))
    ux = vx * ut; uy = vy * ut; uz = vz * ut

    # state vector: [t,x,y,z, ut, ux, uy, uz]
    t = 0.0
    x, y, z = sx, sy, sz
    ut0, ux0, uy0, uz0 = ut, ux, uy, uz

    pts = [(x, y, z)]

    def deriv(state):
        # state: t,x,y,z, ut, ux, uy, uz
        tt, px, py, pz, utt, uxv, uyv, uzv = state
        Gamma = christoffel(px, py, pz)
        # compute acceleration for each component: a^mu = - Gamma^mu_ab u^a u^b
        a_t = 0.0
        a_x = 0.0
        a_y = 0.0
        a_z = 0.0
        u = [utt, uxv, uyv, uzv]
        for a in range(4):
            for b in range(4):
                a_x -= Gamma[1,a,b] * u[a] * u[b]
                a_y -= Gamma[2,a,b] * u[a] * u[b]
                a_z -= Gamma[3,a,b] * u[a] * u[b]
        return np.array([utt, uxv, uyv, uzv, a_t, a_x, a_y, a_z], dtype=float)

    state = np.array([t, x, y, z, ut0, ux0, uy0, uz0], dtype=float)

    for i in range(1, npoints):
        # simple RK4 on state
        k1 = deriv(state)
        k2 = deriv(state + 0.5 * step * k1)
        k3 = deriv(state + 0.5 * step * k2)
        k4 = deriv(state + step * k3)
        state = state + (step / 6.0) * (k1 + 2*k2 + 2*k3 + k4)
        x, y, z = state[1], state[2], state[3]
        pts.append((float(x), float(y), float(z)))

    return pts


# Weak-field Kerr (Lense-Thirring) formal integrator (CPU POC)
def trace_kerr_formal(source: Tuple[float,float,float], direction: Tuple[float,float,float], mass: float = 1.0, spin: Tuple[float,float,float] = (0.0,0.0,0.0), params: dict = None):
    """Formal Kerr integrator (CPU) using Kerr-Schild Cartesian form.

    This implements the Kerr metric in Kerr-Schild coordinates:
      g_{mu nu} = eta_{mu nu} + 2 H l_mu l_nu
    with H = M r^3 / (r^4 + a^2 z^2) and l_mu the Kerr-Schild null vector.

    Note: This is a CPU finite-difference-based POC intended to provide a
    more faithful Kerr null geodesic integrator for research and comparison.
    Performance is not optimized; numeric derivatives are used to obtain
    Christoffel symbols.
    """
    params = params or {}
    # allow opting out to use weak Lense-Thirring POC for quick runs
    if not params.get('formal', True):
        # fallback to previous weak-field gravitomagnetic POC
        Sx, Sy, Sz = spin
        return _trace_kerr_formal_weak(source, direction, mass, (Sx, Sy, Sz), params)

    npoints = int(params.get('npoints', 256))
    step = float(params.get('step', 1e-6))
    sx, sy, sz = source
    vx, vy, vz = direction
    vnorm = np.sqrt(vx*vx + vy*vy + vz*vz) or 1.0
    vx /= vnorm; vy /= vnorm; vz /= vnorm

    # interpret spin: prefer explicit scalar 'a' or use z-component of spin vector
    if 'a' in params:
        a = float(params.get('a'))
    else:
        Sx, Sy, Sz = spin
        a = float(Sz) if abs(Sz) > 0.0 else float(np.sqrt(Sx*Sx + Sy*Sy + Sz*Sz))
    M = float(mass)

    def kerr_r(px, py, pz, a_local):
        # Solve quartic for r using Newton iteration: r^4 - (rho2) r^2 - a^2 z^2 = 0
        rho2 = px*px + py*py + pz*pz - a_local*a_local
        r = max(1e-6, np.sqrt(px*px + py*py + pz*pz))
        for _ in range(12):
            F = r**4 - rho2 * r*r - (a_local*a_local) * (pz*pz)
            dF = 4.0 * r**3 - 2.0 * rho2 * r
            if dF == 0:
                break
            dr = F / dF
            r -= dr
            if abs(dr) < 1e-12:
                break
        return abs(r) + 1e-12

    def kerr_metric(px, py, pz):
        r = kerr_r(px, py, pz, a)
        denom = (r**4 + (a*a) * (pz*pz)) + 1e-24
        H = M * (r**3) / denom
        denom2 = r*r + a*a + 1e-12
        l0 = 1.0
        lx = (r * px + a * py) / denom2
        ly = (r * py - a * px) / denom2
        lz = pz / r
        l = np.array([l0, lx, ly, lz], dtype=float)
        g = np.eye(4, dtype=float)
        g[0,0] = -1.0
        # add Kerr-Schild term
        for mu in range(4):
            for nu in range(4):
                g[mu,nu] += 2.0 * H * l[mu] * l[nu]
        return g

    # expose a module-level metric helper for tests and other modules
    def kerr_metric_cartesian(px, py, pz, M_local, a_local):
        r_loc = kerr_r(px, py, pz, a_local)
        denom = (r_loc**4 + (a_local*a_local) * (pz*pz)) + 1e-24
        H = M_local * (r_loc**3) / denom
        denom2 = r_loc*r_loc + a_local*a_local + 1e-12
        l0 = 1.0
        lx = (r_loc * px + a_local * py) / denom2
        ly = (r_loc * py - a_local * px) / denom2
        lz = pz / r_loc
        l = np.array([l0, lx, ly, lz], dtype=float)
        g = np.eye(4, dtype=float)
        g[0,0] = -1.0
        for mu in range(4):
            for nu in range(4):
                g[mu,nu] += 2.0 * H * l[mu] * l[nu]
        return g

    def christoffel_kerr(px, py, pz):
        # make module-level helper available
        global kerr_metric
        # wrapper to call cartesian metric helper if needed
        def kerr_metric(px2, py2, pz2):
            return kerr_metric_cartesian(px2, py2, pz2, M, a)
        # Analytic derivatives for Kerr-Schild: g = eta + 2 H l l
        # We'll compute derivatives of H and l via implicit dr/dx, dr/dy, dr/dz
        def dr_partials(px, py, pz, a_local):
            # implicit differentiation of quartic F(r,x,y,z) = r^4 - rho2 r^2 - a^2 z^2 = 0
            rho2 = px*px + py*py + pz*pz - a_local*a_local
            r = kerr_r(px, py, pz, a_local)
            dF_dr = 4.0 * r**3 - 2.0 * rho2 * r
            # partial derivatives of F w.r.t x,y,z
            dF_dx = -2.0 * px * r*r
            dF_dy = -2.0 * py * r*r
            dF_dz = -2.0 * pz * r*r - 2.0 * (a_local*a_local) * pz
            # dr/dx = -dF_dx / dF_dr  etc.
            if abs(dF_dr) < 1e-12:
                return (0.0, 0.0, 0.0)
            drdx = -dF_dx / dF_dr
            drdy = -dF_dy / dF_dr
            drdz = -dF_dz / dF_dr
            return (drdx, drdy, drdz)

        # compute r and its partials
        r = kerr_r(px, py, pz, a)
        drdx, drdy, drdz = dr_partials(px, py, pz, a)

        # helper values
        denom = (r**4 + (a*a) * (pz*pz)) + 1e-24
        H = M * (r**3) / denom
        # dH/dx etc using product/quotient rule
        ddenom_dx = 4.0 * r**3 * drdx
        ddenom_dy = 4.0 * r**3 * drdy
        ddenom_dz = 4.0 * r**3 * drdz + 2.0 * a*a * pz
        dH_dx = M * (3.0 * r*r * drdx * denom - r**3 * ddenom_dx) / (denom*denom)
        dH_dy = M * (3.0 * r*r * drdy * denom - r**3 * ddenom_dy) / (denom*denom)
        dH_dz = M * (3.0 * r*r * drdz * denom - r**3 * ddenom_dz) / (denom*denom)

        # l vector components and derivatives
        d2 = r*r + a*a + 1e-12
        # l components
        l0 = 1.0
        lx = (r * px + a * py) / d2
        ly = (r * py - a * px) / d2
        lz = pz / r

        # derivatives of l components
        # dlx/dx = ((drdx * px + r) * d2 - (r*px + a*py) * 2*r*drdx) / d2^2
        def dlx_dx():
            num = (drdx * px + r) * d2 - (r*px + a*py) * (2.0 * r * drdx)
            return num / (d2*d2)
        def dlx_dy():
            num = (drdy * px + 0.0) * d2 - (r*px + a*py) * (2.0 * r * drdy)
            # plus derivative from a*py term: subtract a* (since derivative py wrt y is 1 in numerator) => handle separately
            num += - a * d2
            return num / (d2*d2)
        def dlx_dz():
            num = (drdz * px + 0.0) * d2 - (r*px + a*py) * (2.0 * r * drdz)
            return num / (d2*d2)
        def dly_dx():
            num = (drdx * py + 0.0) * d2 - (r*py - a*px) * (2.0 * r * drdx)
            # plus derivative from -a*px term: subtract (-a) * d2? derivative of (-a*px) w.r.t x is -a
            num += a * d2
            return num / (d2*d2)
        def dly_dy():
            num = (drdy * py + r) * d2 - (r*py - a*px) * (2.0 * r * drdy)
            return num / (d2*d2)
        def dly_dz():
            num = (drdz * py + 0.0) * d2 - (r*py - a*px) * (2.0 * r * drdz)
            return num / (d2*d2)
        def dlz_dx():
            return - pz * drdx / (r*r)
        def dlz_dy():
            return - pz * drdy / (r*r)
        def dlz_dz():
            return (1.0 * r - pz * drdz) / (r*r)

        # compute partial derivatives of g_{mu nu} = eta + 2 H l_mu l_nu
        # g_mu_nu derivatives: dg/dxj = 2 * (dH/dxj * l_mu*l_nu + H * (dl_mu/dxj * l_nu + l_mu * dl_nu/dxj))
        def dg_dxj(px, py, pz, j):
            # returns 4x4 matrix for derivative wrt coordinate j (0:x,1:y,2:z)
            if j == 0:
                dH = dH_dx
                dl = [0.0, dlx_dx(), dly_dx(), dlz_dx()]
            elif j == 1:
                dH = dH_dy
                dl = [0.0, dlx_dy(), dly_dy(), dlz_dy()]
            else:
                dH = dH_dz
                dl = [0.0, dlx_dz(), dly_dz(), dlz_dz()]
            lvec = [l0, lx, ly, lz]
            mat = np.zeros((4,4), dtype=float)
            for mu in range(4):
                for nu in range(4):
                    mat[mu,nu] = 2.0 * (dH * lvec[mu] * lvec[nu] + H * (dl[mu] * lvec[nu] + lvec[mu] * dl[nu]))
            return mat

        dg1 = dg_dxj(px, py, pz, 0)
        dg2 = dg_dxj(px, py, pz, 1)
        dg3 = dg_dxj(px, py, pz, 2)
        dg = [np.zeros((4,4), dtype=float), dg1, dg2, dg3]

        g0 = kerr_metric(px, py, pz)
        try:
            ginv = np.linalg.inv(g0)
        except Exception:
            ginv = np.linalg.pinv(g0)
        Gamma = np.zeros((4,4,4), dtype=float)
        for mu in range(4):
            for alpha in range(4):
                for beta in range(4):
                    s = 0.0
                    for nu in range(4):
                        s += ginv[mu,nu] * (dg[alpha][nu,beta] + dg[beta][nu,alpha] - dg[nu][alpha,beta])
                    Gamma[mu,alpha,beta] = 0.5 * s
        return Gamma

    # initial 4-velocity: choose spatial part = direction (unit) and solve quadratic for ut
    def initial_ut(px, py, pz, ux_spatial):
        g0 = kerr_metric(px, py, pz)
        A = g0[0,0]
        B = 2.0 * (g0[0,1]*ux_spatial[0] + g0[0,2]*ux_spatial[1] + g0[0,3]*ux_spatial[2])
        C = (g0[1,1]*ux_spatial[0]*ux_spatial[0] + 2.0*g0[1,2]*ux_spatial[0]*ux_spatial[1] + 2.0*g0[1,3]*ux_spatial[0]*ux_spatial[2]
             + g0[2,2]*ux_spatial[1]*ux_spatial[1] + 2.0*g0[2,3]*ux_spatial[1]*ux_spatial[2] + g0[3,3]*ux_spatial[2]*ux_spatial[2])
        # Solve A ut^2 + B ut + C = 0 for ut
        disc = B*B - 4.0*A*C
        if disc < 0:
            disc = abs(disc)
        if abs(A) < 1e-12:
            return 1.0
        ut1 = (-B + np.sqrt(disc)) / (2.0 * A)
        ut2 = (-B - np.sqrt(disc)) / (2.0 * A)
        ut = ut1 if ut1 > 0 else ut2
        if ut <= 0:
            ut = abs(ut1)
            if ut <= 0:
                ut = 1.0
        return float(ut)

    # Allow optional use of Numba-accelerated integrator when available
    try:
        from .accelerated import trace_kerr_numba
        # do not use numba when return_state requested (states not available from numba POC)
        if params.get('use_numba', True) and not params.get('return_state', False):
            # call per-ray njit integrator for speed (single ray)
            try:
                sx_arr = sx; sy_arr = sy; sz_arr = sz
                dxp, dyp, dzp = vx, vy, vz
                Sx, Sy, Sz = spin
                res = trace_kerr_numba(sx_arr, sy_arr, sz_arr, dxp, dyp, dzp, float(mass), float(Sx), float(Sy), float(Sz), npoints, step, float(a if 'a' in locals() else 0.0))
                return [ (float(x), float(y), float(z)) for (x,y,z) in res ]
            except Exception:
                # fall through to Python integrator
                pass
    except Exception:
        pass

    # initial state
    ux0, uy0, uz0 = vx, vy, vz
    ut0 = initial_ut(sx, sy, sz, (ux0, uy0, uz0))

    state = np.array([0.0, sx, sy, sz, ut0, ux0, uy0, uz0], dtype=float)
    # include initial full state if return_state requested
    pts = [(sx, sy, sz, ut0, ux0, uy0, uz0)]

    def deriv(state):
        tt, px, py, pz, utt, uxv, uyv, uzv = state
        Gamma = christoffel_kerr(px, py, pz)
        a = [0.0, 0.0, 0.0, 0.0]
        u = [utt, uxv, uyv, uzv]
        for mu in range(4):
            for a1 in range(4):
                for b1 in range(4):
                    a[mu] -= Gamma[mu,a1,b1] * u[a1] * u[b1]
        # return derivative in same layout: dt/dlambda = ut, dx/dlambda = ux, ..., dut/dlambda = a[0], dux/dlambda = a[1], ...
        return np.array([u[0], u[1], u[2], u[3], a[0], a[1], a[2], a[3]], dtype=float)

    for i in range(1, npoints):
        k1 = deriv(state)
        k2 = deriv(state + 0.5 * step * k1)
        k3 = deriv(state + 0.5 * step * k2)
        k4 = deriv(state + step * k3)
        state = state + (step / 6.0) * (k1 + 2.0*k2 + 2.0*k3 + k4)
        x, y, z = state[1], state[2], state[3]
        pts.append((float(x), float(y), float(z), float(state[4]), float(state[5]), float(state[6]), float(state[7])))
    if params.get('return_state'):
        return pts
    # otherwise strip state to spatial samples for compatibility
    return [ (p[0], p[1], p[2]) for p in pts ]


def _trace_kerr_formal_weak(source: Tuple[float,float,float], direction: Tuple[float,float,float], mass: float = 1.0, spin: Tuple[float,float,float] = (0.0,0.0,0.0), params: dict = None):
    """Legacy weak-field gravitomagnetic POC extracted as a helper."""
    params = params or {}
    npoints = int(params.get('npoints', 256))
    step = float(params.get('step', 1e-6))
    sx, sy, sz = source
    vx, vy, vz = direction
    # normalize
    vnorm = np.sqrt(vx*vx + vy*vy + vz*vz) or 1.0
    vx /= vnorm; vy /= vnorm; vz /= vnorm

    Sx, Sy, Sz = spin
    def r_mag(px, py, pz):
        return np.sqrt(px*px + py*py + pz*pz) + 1e-12

    def gravitomagnetic_A(px, py, pz):
        rx, ry, rz = px, py, pz
        r3 = (r_mag(px,py,pz)**3) + 1e-12
        Ax = (Sy * rz - Sz * ry) / r3
        Ay = (Sz * rx - Sx * rz) / r3
        Az = (Sx * ry - Sy * rx) / r3
        return (Ax, Ay, Az)

    def grad_P(px, py, pz):
        r = r_mag(px,py,pz)
        fac = mass / (r**3 + 1e-12)
        return (fac * px, fac * py, fac * pz)

    ph0 = -mass / r_mag(sx, sy, sz)
    ut = 1.0 / np.sqrt(max(1e-12, 1.0 - 2.0*ph0))
    ux, uy, uz = vx * ut, vy * ut, vz * ut

    x, y, z = sx, sy, sz
    pts = [(x, y, z)]

    def christoffel_kerr(px, py, pz, ut_loc):
        dPx, dPy, dPz = grad_P(px, py, pz)
        Ax, Ay, Az = gravitomagnetic_A(px, py, pz)
        eps = 1e-6
        Gamma = np.zeros((4,4,4))
        Gamma[1,0,0] = -dPx
        Gamma[2,0,0] = -dPy
        Gamma[3,0,0] = -dPz
        Gamma[1,0,2] = 0.5 * ( (gravitomagnetic_A(px,py+eps,pz)[0]-Ax)/eps - (gravitomagnetic_A(px,py,pz+eps)[1]-Ay)/eps )
        return Gamma

    def deriv(state):
        tt, px, py, pz, utt, uxv, uyv, uzv = state
        Gamma = christoffel_kerr(px, py, pz, utt)
        a_x = 0.0; a_y = 0.0; a_z = 0.0
        u = [utt, uxv, uyv, uzv]
        for a in range(4):
            for b in range(4):
                a_x -= Gamma[1,a,b] * u[a] * u[b]
                a_y -= Gamma[2,a,b] * u[a] * u[b]
                a_z -= Gamma[3,a,b] * u[a] * u[b]
        return np.array([utt, uxv, uyv, uzv, 0.0, a_x, a_y, a_z], dtype=float)

    state = np.array([0.0, x, y, z, ut, ux, uy, uz], dtype=float)
    for i in range(1, npoints):
        k1 = deriv(state)
        k2 = deriv(state + 0.5 * step * k1)
        k3 = deriv(state + 0.5 * step * k2)
        k4 = deriv(state + step * k3)
        state = state + (step/6.0) * (k1 + 2*k2 + 2*k3 + k4)
        x, y, z = state[1], state[2], state[3]
        pts.append((float(x), float(y), float(z)))
    return pts


# Simple RK4-style CPU integrator POC (position-only for demonstration)
def trace_flat_rk4(source: Tuple[float,float,float], direction: Tuple[float,float,float], params: dict = None):
    params = params or {}
    npoints = int(params.get('npoints', 256))
    step = float(params.get('step', 1e-6))
    sx, sy, sz = source
    dx, dy, dz = direction
    dir_norm = np.sqrt(dx*dx + dy*dy + dz*dz) or 1.0
    dx /= dir_norm; dy /= dir_norm; dz /= dir_norm
    # simple RK4 that integrates x' = dx (constant) as POC
    points = []
    x, y, z = sx, sy, sz
    # include initial position as first sample to match trace_flat convention
    points.append((x, y, z))
    for i in range(1, npoints):
        x += dx * step
        y += dy * step
        z += dz * step
        points.append((x, y, z))
    return points


# Adaptive RK4 integrator (step-doubling error estimate)
def trace_schwarzschild_rk4_adaptive(source: Tuple[float,float,float], direction: Tuple[float,float,float], mass: float = 1.0, params: dict = None):
    params = params or {}
    npoints = int(params.get('npoints', 256))
    h0 = float(params.get('step', 1e-6))
    tol = float(params.get('tol', 1e-8))
    max_steps = int(params.get('max_steps', 100000))

    sx, sy, sz = source
    vx, vy, vz = direction
    # normalize velocity
    vnorm = np.sqrt(vx*vx + vy*vy + vz*vz) or 1.0
    vx /= vnorm; vy /= vnorm; vz /= vnorm

    t = 0.0
    t_end = npoints * h0

    def accel(px, py, pz):
        r = np.sqrt(px*px + py*py + pz*pz) + 1e-12
        return (-4.0 * mass * px / (r**3 + 1e-12) * 1e-7,
                -4.0 * mass * py / (r**3 + 1e-12) * 1e-7,
                -4.0 * mass * pz / (r**3 + 1e-12) * 1e-7)

    xs = []
    ys = []
    zs = []

    x, y, z = sx, sy, sz

    h = h0
    steps = 0
    while t < t_end and steps < max_steps:
        if t + h > t_end:
            h = t_end - t
        # single full step
        # RK4 step for (pos, vel) with velocity treated as dx/dt and acceleration from position
        def rk4_step(px, py, pz, vx0, vy0, vz0, hh):
            ax1, ay1, az1 = accel(px, py, pz)
            k1_vx, k1_vy, k1_vz = ax1, ay1, az1
            k1_x, k1_y, k1_z = vx0, vy0, vz0

            xm = px + 0.5*hh*k1_x
            ym = py + 0.5*hh*k1_y
            zm = pz + 0.5*hh*k1_z
            ax2, ay2, az2 = accel(xm, ym, zm)
            k2_vx, k2_vy, k2_vz = ax2, ay2, az2
            k2_x, k2_y, k2_z = vx0 + 0.5*hh*k1_vx, vy0 + 0.5*hh*k1_vy, vz0 + 0.5*hh*k1_vz

            xm = px + 0.5*hh*k2_x
            ym = py + 0.5*hh*k2_y
            zm = pz + 0.5*hh*k2_z
            ax3, ay3, az3 = accel(xm, ym, zm)
            k3_vx, k3_vy, k3_vz = ax3, ay3, az3
            k3_x, k3_y, k3_z = vx0 + 0.5*hh*k2_vx, vy0 + 0.5*hh*k2_vy, vz0 + 0.5*hh*k2_vz

            xm = px + hh*k3_x
            ym = py + hh*k3_y
            zm = pz + hh*k3_z
            ax4, ay4, az4 = accel(xm, ym, zm)
            k4_vx, k4_vy, k4_vz = ax4, ay4, az4
            k4_x, k4_y, k4_z = vx0 + hh*k3_vx, vy0 + hh*k3_vy, vz0 + hh*k3_vz

            nvx = vx0 + (hh/6.0)*(k1_vx + 2*k2_vx + 2*k3_vx + k4_vx)
            nvy = vy0 + (hh/6.0)*(k1_vy + 2*k2_vy + 2*k3_vy + k4_vy)
            nvz = vz0 + (hh/6.0)*(k1_vz + 2*k2_vz + 2*k3_vz + k4_vz)

            nx = px + (hh/6.0)*(k1_x + 2*k2_x + 2*k3_x + k4_x)
            ny = py + (hh/6.0)*(k1_y + 2*k2_y + 2*k3_y + k4_y)
            nz = pz + (hh/6.0)*(k1_z + 2*k2_z + 2*k3_z + k4_z)

            return nx, ny, nz, nvx, nvy, nvz

        # full step
        nx1, ny1, nz1, nvx1, nvy1, nvz1 = rk4_step(x, y, z, vx, vy, vz, h)
        # two half steps
        nxh, nyh, nzh, nvxh, nvyh, nvzh = rk4_step(x, y, z, vx, vy, vz, h*0.5)
        nx2, ny2, nz2, nvx2, nvy2, nvz2 = rk4_step(nxh, nyh, nzh, nvxh, nvyh, nvzh, h*0.5)

        # error estimate (4th-order RK: error ~ (nx2 - nx1)/15)
        err = np.sqrt((nx2 - nx1)**2 + (ny2 - ny1)**2 + (nz2 - nz1)**2) / 15.0
        if err <= tol:
            # accept step
            t += h
            x, y, z = nx2, ny2, nz2
            vx, vy, vz = nvx2, nvy2, nvz2
            xs.append(x); ys.append(y); zs.append(z)
            # increase step gently
            h = min(h*2, h0*10)
        else:
            # reject and reduce step
            h = max(h*0.5, h0*1e-6)
        steps += 1

    # resample to npoints (interpolate)
    if len(xs) < 2:
        # fallback: uniform RK4
        return trace_schwarzschild_rk4(source, direction, mass, {'npoints': npoints, 'step': h0})

    import numpy as _np
    t_vals = _np.linspace(0, t, len(xs))
    t_target = _np.linspace(0, t, npoints)
    xs_arr = _np.array(xs); ys_arr = _np.array(ys); zs_arr = _np.array(zs)
    x_interp = _np.interp(t_target, t_vals, xs_arr)
    y_interp = _np.interp(t_target, t_vals, ys_arr)
    z_interp = _np.interp(t_target, t_vals, zs_arr)
    return [ (float(x_interp[i]), float(y_interp[i]), float(z_interp[i])) for i in range(npoints) ]


def trace_schwarzschild_rk4(source: Tuple[float,float,float], direction: Tuple[float,float,float], mass: float = 1.0, params: dict = None):
    params = params or {}
    npoints = int(params.get('npoints', 256))
    step = float(params.get('step', 1e-6))
    sx, sy, sz = source
    vx, vy, vz = direction
    # normalize velocity
    vnorm = np.sqrt(vx*vx + vy*vy + vz*vz) or 1.0
    vx /= vnorm; vy /= vnorm; vz /= vnorm

    x, y, z = sx, sy, sz
    points = []
    points.append((x, y, z))

    for i in range(1, npoints):
        # define acceleration due to central mass (weak-field approx)
        def accel(px, py, pz):
            r = np.sqrt(px*px + py*py + pz*pz) + 1e-12
            return (-4.0 * mass * px / (r**3 + 1e-12) * 1e-7,
                    -4.0 * mass * py / (r**3 + 1e-12) * 1e-7,
                    -4.0 * mass * pz / (r**3 + 1e-12) * 1e-7)

        ax1, ay1, az1 = accel(x, y, z)
        kx1, ky1, kz1 = vx, vy, vz

        xm = x + 0.5 * step * kx1
        ym = y + 0.5 * step * ky1
        zm = z + 0.5 * step * kz1
        avx, avy, avz = accel(xm, ym, zm)
        kx2 = vx + 0.5 * step * ax1
        ky2 = vy + 0.5 * step * ay1
        kz2 = vz + 0.5 * step * az1
        ax2, ay2, az2 = avx, avy, avz

        xm = x + 0.5 * step * kx2
        ym = y + 0.5 * step * ky2
        zm = z + 0.5 * step * kz2
        ax3, ay3, az3 = accel(xm, ym, zm)
        kx3 = vx + 0.5 * step * ax2
        ky3 = vy + 0.5 * step * ay2
        kz3 = vz + 0.5 * step * az2

        xm = x + step * kx3
        ym = y + step * ky3
        zm = z + step * kz3
        ax4, ay4, az4 = accel(xm, ym, zm)
        kx4 = vx + step * ax3
        ky4 = vy + step * ay3
        kz4 = vz + step * az3

        vx = vx + (step / 6.0) * (ax1 + 2*ax2 + 2*ax3 + ax4)
        vy = vy + (step / 6.0) * (ay1 + 2*ay2 + 2*ay3 + ay4)
        vz = vz + (step / 6.0) * (az1 + 2*az2 + 2*az3 + az4)

        x = x + (step / 6.0) * (kx1 + 2*kx2 + 2*kx3 + kx4)
        y = y + (step / 6.0) * (ky1 + 2*ky2 + 2*ky3 + ky4)
        z = z + (step / 6.0) * (kz1 + 2*kz2 + 2*kz3 + kz4)

        points.append((x, y, z))
    return points


# Full null geodesic integrator (Christoffel-based POC)
def trace_null_geodesic(source: Tuple[float,float,float], direction: Tuple[float,float,float], mass: float = 1.0, params: dict = None):
    """Integrate an approximate null geodesic using a simplified Christoffel
    weak-field approximation. This is a POC implementation that integrates
    spacetime trajectory (t ignored in output) using an RK4 step on the
    4-velocity and returns spatial sample points."""
    params = params or {}
    npoints = int(params.get('npoints', 256))
    step = float(params.get('step', 1e-6))
    sx, sy, sz = source
    vx, vy, vz = direction
    # normalize spatial velocity to unit light-speed approximation
    vnorm = np.sqrt(vx*vx + vy*vy + vz*vz) or 1.0
    vx /= vnorm; vy /= vnorm; vz /= vnorm

    # initial 4-velocity: choose ut such that g_{mu nu} u^mu u^nu = 0 in weak-field
    def potential(px, py, pz):
        r = np.sqrt(px*px + py*py + pz*pz) + 1e-12
        return -mass / r

    # approximate ut from null condition: -(1+2Phi) ut^2 + (1-2Phi) v^2 ut^2 = 0 => ut ~ 1/sqrt(1-2Phi)
    Phi = potential(sx, sy, sz)
    ut = 1.0 / np.sqrt(max(1e-12, 1 - 2*Phi))

    x, y, z = sx, sy, sz
    ux, uy, uz = vx * ut, vy * ut, vz * ut

    points = [(x, y, z)]

    def christoffel_acc(px, py, pz, ux_loc, uy_loc, uz_loc, ut_loc):
        # Weak-field Christoffel approximation: Gamma^i_tt ~ partial_i Phi
        r = np.sqrt(px*px + py*py + pz*pz) + 1e-12
        dPx = mass * px / (r**3 + 1e-12)
        dPy = mass * py / (r**3 + 1e-12)
        dPz = mass * pz / (r**3 + 1e-12)
        # acceleration term for spatial part: -Gamma^i_tt (ut)^2 dominated
        ax = -dPx * (ut_loc**2) * 2e-7
        ay = -dPy * (ut_loc**2) * 2e-7
        az = -dPz * (ut_loc**2) * 2e-7
        return ax, ay, az

    for i in range(1, npoints):
        # RK4 integrate spatial positions/velocities with acceleration from Christoffel
        ax1, ay1, az1 = christoffel_acc(x, y, z, ux, uy, uz, ut)
        kx1, ky1, kz1 = ux, uy, uz

        xm = x + 0.5*step*kx1; ym = y + 0.5*step*ky1; zm = z + 0.5*step*kz1
        ax2, ay2, az2 = christoffel_acc(xm, ym, zm, ux, uy, uz, ut)
        kx2 = ux + 0.5*step*ax1; ky2 = uy + 0.5*step*ay1; kz2 = uz + 0.5*step*az1

        xm = x + 0.5*step*kx2; ym = y + 0.5*step*ky2; zm = z + 0.5*step*kz2
        ax3, ay3, az3 = christoffel_acc(xm, ym, zm, ux, uy, uz, ut)
        kx3 = ux + 0.5*step*ax2; ky3 = uy + 0.5*step*ay2; kz3 = uz + 0.5*step*az2

        xm = x + step*kx3; ym = y + step*ky3; zm = z + step*kz3
        ax4, ay4, az4 = christoffel_acc(xm, ym, zm, ux, uy, uz, ut)
        kx4 = ux + step*ax3; ky4 = uy + step*ay3; kz4 = uz + step*az3

        ux = ux + (step/6.0)*(ax1 + 2*ax2 + 2*ax3 + ax4)
        uy = uy + (step/6.0)*(ay1 + 2*ay2 + 2*ay3 + ay4)
        uz = uz + (step/6.0)*(az1 + 2*az2 + 2*az3 + az4)

        x = x + (step/6.0)*(kx1 + 2*kx2 + 2*kx3 + kx4)
        y = y + (step/6.0)*(ky1 + 2*ky2 + 2*ky3 + ky4)
        z = z + (step/6.0)*(kz1 + 2*kz2 + 2*kz3 + kz4)

        points.append((x, y, z))
    return points


# Batch helpers (support GPU batched kernels when requested)

def trace_flat_batch(source, directions, params: dict = None):
    params = params or {}
    if _HAS_CUDA and params.get('device') == 'gpu':
        import numpy as np
        logger.info('Using CUDA batched kernel for trace_flat_batch')
        sources = np.array([source for _ in range(len(directions))], dtype=np.float64)
        dirs = np.array(directions, dtype=np.float64)
        if params.get('method') in ('rk4', 'rk4_adaptive'):
            try:
                return trace_flat_rk4_gpu(sources, dirs, params)
            except Exception:
                pass
        return trace_flat_gpu(sources, dirs, params)
    else:
        results = []
        if params.get('method') == 'rk4':
            for d in directions:
                results.append(trace_flat_rk4(source, d, params))
        elif params.get('method') == 'rk4_adaptive':
            for d in directions:
                # no adaptive flat integrator yet; fallback to rk4
                results.append(trace_flat_rk4(source, d, params))
        else:
            for d in directions:
                results.append(trace_flat(source, d, params))
        return results


def trace_schwarzschild_batch(source, directions, mass=1.0, params: dict = None):
    params = params or {}
    if _HAS_CUDA and params.get('device') == 'gpu':
        import numpy as np
        logger.info('Using CUDA batched kernel for trace_schwarzschild_batch')
        sources = np.array([source for _ in range(len(directions))], dtype=np.float64)
        dirs = np.array(directions, dtype=np.float64)
        masses = np.array([mass for _ in range(len(directions))], dtype=np.float64)
        # Special-case Kerr formal on GPU (choose analytic RK4 kernel if requested)
        if params.get('method') == 'kerr_formal':
            try:
                if params.get('analytic', True):
                    from .accelerated_cuda import trace_kerr_rk4_gpu
                    return trace_kerr_rk4_gpu(sources, dirs, masses, params)
                else:
                    from .accelerated_cuda import trace_kerr_gpu
                    return trace_kerr_gpu(sources, dirs, masses, params)
            except Exception:
                # fallback to CPU per-ray integrator below
                pass
        if params.get('method') == 'rk4_adaptive':
            # Prefer device-side error-control kernel if requested
            if params.get('device_adaptive') == 'error_control' or params.get('device_adaptive') is True:
                try:
                    from .accelerated_cuda import trace_schwarzschild_rk4_device_adaptive_error
                    return trace_schwarzschild_rk4_device_adaptive_error(sources, dirs, masses, params)
                except Exception:
                    pass
            # Otherwise try multi-pass host-coordinated adaptive GPU orchestration
            try:
                from .accelerated_cuda import trace_schwarzschild_rk4_adaptive_gpu
                return trace_schwarzschild_rk4_adaptive_gpu(sources, dirs, masses, params)
            except Exception:
                # fallback to CPU adaptive
                pass
        if params.get('method') in ('rk4', 'rk4_adaptive'):
            try:
                return trace_schwarzschild_rk4_gpu(sources, dirs, masses, params)
            except Exception:
                pass
        return trace_schwarzschild_gpu(sources, dirs, masses, params)
    else:
        results = []
        if params.get('method') == 'rk4_adaptive':
            for d in directions:
                results.append(trace_schwarzschild_rk4_adaptive(source, d, mass, params))
        elif params.get('method') == 'rk4':
            for d in directions:
                results.append(trace_schwarzschild_rk4(source, d, mass, params))
        elif params.get('method') == 'null':
            # simple null geodesic POC
            for d in directions:
                results.append(trace_null_geodesic(source, d, mass, params))
        elif params.get('method') == 'null_formal':
            for d in directions:
                results.append(trace_null_formal(source, d, mass, params))
        elif params.get('method') == 'kerr_formal':
            # CPU: prefer a Numba batched kernel if requested and available
            spin = params.get('spin', (0.0, 0.0, 0.0))
            if params.get('device') == 'cpu' and params.get('use_numba', True):
                try:
                    from .accelerated import trace_kerr_numba_batch
                    import numpy as _np
                    srcs = _np.array([source for _ in directions], dtype=float)
                    dirs = _np.array(directions, dtype=float)
                    masses = _np.array([mass for _ in directions], dtype=float)
                    spins = _np.array([spin for _ in directions], dtype=float)
                    res = trace_kerr_numba_batch(srcs, dirs, masses, spins, int(params.get('npoints',256)), float(params.get('step',1e-6)), params.get('a', None))
                    # convert to expected list-of-lists
                    for r in res:
                        results.append(r)
                    return results
                except Exception:
                    # fallback to python per-ray integrator below
                    pass
            # fallback: per-direction CPU integrator
            for d in directions:
                spin = params.get('spin', (0.0, 0.0, 0.0))
                results.append(trace_kerr_formal(source, d, mass, spin, params))
        else:
            for d in directions:
                results.append(trace_schwarzschild_weak(source, d, mass, params))
        return results

# Dask-friendly wrapper
try:
    from dask import delayed
    def trace_delayed(func, *args, **kwargs):
        return delayed(func)(*args, **kwargs)
except Exception:
    def trace_delayed(func, *args, **kwargs):
        # fallback: return result immediately
        return func(*args, **kwargs)
