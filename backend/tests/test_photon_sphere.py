import numpy as np
from app.geodesics import trace_kerr_formal


def radial_dist(points):
    return [ (p[0]**2 + p[1]**2 + p[2]**2)**0.5 for p in points ]


def test_schwarzschild_photon_sphere():
    src = (3.0, 0.0, 0.0)
    dir = (0.0, 1.0, 0.0)
    pts = trace_kerr_formal(src, dir, mass=1.0, spin=(0.0,0.0,0.0), params={'npoints': 128, 'step': 1e-3, 'formal': True})
    rs = radial_dist(pts)
    mean_r = sum(rs)/len(rs)
    # photon sphere at r=3M for M=1 => mean radius should be close
    assert abs(mean_r - 3.0) < 5e-2


def test_kerr_prograde_shift():
    src = (3.0, 0.0, 0.0)
    dir = (0.0, 1.0, 0.0)
    pts_a0 = trace_kerr_formal(src, dir, mass=1.0, spin=(0.0,0.0,0.0), params={'npoints': 128, 'step': 1e-3, 'formal': True})
    pts_a = trace_kerr_formal(src, dir, mass=1.0, spin=(0.0,0.0,0.2), params={'npoints': 128, 'step': 1e-3, 'formal': True})
    ra0 = sum(radial_dist(pts_a0))/len(pts_a0)
    ra = sum(radial_dist(pts_a))/len(pts_a)
    # prograde spin should decrease effective prograde photon radius slightly
    assert ra <= ra0 + 1e-2
