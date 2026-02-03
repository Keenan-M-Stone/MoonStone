import numpy as np
from typing import List, Tuple

# Simple POC geodesic traces
# - Flat spacetime: straight-line propagation
# - Schwarzschild weak-field: approximate deflection using small-angle formula

def trace_flat(source: Tuple[float,float,float], direction: Tuple[float,float,float], npoints: int = 256, step: float = 1e-6):
    sx, sy, sz = source
    dx, dy, dz = direction
    dir_norm = np.sqrt(dx*dx + dy*dy + dz*dz) or 1.0
    dx /= dir_norm; dy /= dir_norm; dz /= dir_norm
    points = []
    for i in range(npoints):
        t = i * step
        points.append((sx + dx * t, sy + dy * t, sz + dz * t))
    return points

def trace_schwarzschild_weak(source: Tuple[float,float,float], direction: Tuple[float,float,float], mass: float = 1.0, npoints: int = 256, step: float = 1e-6):
    """Approximate small-angle deflection for light passing near point mass at origin.
    This is a POC: deflection angle ~ 4GM/b in geometric units; we simulate a small lateral displacement proportional to mass/b.
    """
    sx, sy, sz = source
    dx, dy, dz = direction
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

# Dask-friendly wrapper
try:
    from dask import delayed
    def trace_delayed(func, *args, **kwargs):
        return delayed(func)(*args, **kwargs)
except Exception:
    def trace_delayed(func, *args, **kwargs):
        # fallback: return result immediately
        return func(*args, **kwargs)
