"""Curvature volume artifacts for metric fields.

Provides compute-on-demand and caching for derived scalar fields (e.g. Ricci
scalar) from an imported metric field.

This is intentionally conservative:
- only operates on metric.type='field' baselines (regular grids)
- uses static finite-difference curvature diagnostic
- enforces max grid point limits for interactive responsiveness
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np

from .curvature import ricci_scalar_static
from .metric_fields import MetricFieldMeta, load_metric_field, sample_metric_field


@dataclass(frozen=True)
class CurvatureVolumeMeta:
    field_id: str
    h: float
    shape: Tuple[int, int, int]
    origin: Tuple[float, float, float]
    spacing: Tuple[float, float, float]
    ricci_min: float
    ricci_max: float
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            'version': int(self.version),
            'kind': 'curvature_volume',
            'field_id': self.field_id,
            'h': float(self.h),
            'grid': {
                'shape': list(map(int, self.shape)),
                'origin': list(map(float, self.origin)),
                'spacing': list(map(float, self.spacing)),
                'order': 'xyz',
            },
            'ricci_scalar': {
                'min': float(self.ricci_min),
                'max': float(self.ricci_max),
            },
        }


def _curv_dir(field_id: str, base_dir: Path) -> Path:
    return base_dir / field_id / 'derived'


def _curv_paths(field_id: str, base_dir: Path, h: float) -> Tuple[Path, Path]:
    d = _curv_dir(field_id, base_dir)
    # Use a stable filename key for h without introducing path separators.
    h_key = f"{float(h):.6g}".replace('-', 'm')
    meta_path = d / f"ricci_scalar_h{h_key}.json"
    data_path = d / f"ricci_scalar_h{h_key}.npz"
    return meta_path, data_path


def compute_ricci_scalar_volume_for_field(
    field_id: str,
    *,
    h: float,
    base_dir: Path,
    force: bool = False,
    max_points: int = 64 * 64 * 64,
) -> CurvatureVolumeMeta:
    """Compute and cache Ricci scalar volume for a stored metric field."""
    if h <= 0:
        raise ValueError('h must be positive')

    meta_path, data_path = _curv_paths(field_id, base_dir, h)
    meta_path.parent.mkdir(parents=True, exist_ok=True)

    if (not force) and meta_path.exists() and data_path.exists():
        # Load cached meta.
        with meta_path.open('r') as fh:
            d = json.load(fh)
        grid = d.get('grid', {})
        rinfo = d.get('ricci_scalar', {})
        return CurvatureVolumeMeta(
            field_id=str(d.get('field_id', field_id)),
            h=float(d.get('h', h)),
            shape=tuple(int(x) for x in grid.get('shape', (0, 0, 0))),
            origin=tuple(float(x) for x in grid.get('origin', (0.0, 0.0, 0.0))),
            spacing=tuple(float(x) for x in grid.get('spacing', (1.0, 1.0, 1.0))),
            ricci_min=float(rinfo.get('min', 0.0)),
            ricci_max=float(rinfo.get('max', 0.0)),
            version=int(d.get('version', 1)),
        )

    field_meta, g_grid = load_metric_field(field_id, base_dir=base_dir)
    if not isinstance(field_meta, MetricFieldMeta):
        raise ValueError('invalid field meta')
    nx, ny, nz = field_meta.shape
    npts = int(nx * ny * nz)
    if npts > int(max_points):
        raise ValueError(f'field grid too large for interactive curvature volume: {npts} > {max_points}')

    # metric_at closure that samples the field with interpolation
    def mfn(p):
        return sample_metric_field(p, field_meta, g_grid, clamp=True)

    R = np.zeros((nx, ny, nz), dtype=float)
    ox, oy, oz = field_meta.origin
    dx, dy, dz = field_meta.spacing
    for ix in range(nx):
        x = ox + dx * ix
        for iy in range(ny):
            y = oy + dy * iy
            for iz in range(nz):
                z = oz + dz * iz
                out = ricci_scalar_static(mfn, (x, y, z), h=h)
                R[ix, iy, iz] = out.ricci_scalar

    ricci_min = float(np.min(R)) if R.size else 0.0
    ricci_max = float(np.max(R)) if R.size else 0.0
    meta_out = CurvatureVolumeMeta(
        field_id=field_id,
        h=float(h),
        shape=(nx, ny, nz),
        origin=field_meta.origin,
        spacing=field_meta.spacing,
        ricci_min=ricci_min,
        ricci_max=ricci_max,
    )

    np.savez_compressed(data_path, R=R)
    with meta_path.open('w') as fh:
        json.dump(meta_out.to_dict(), fh, indent=2)

    return meta_out


def curvature_volume_paths(field_id: str, *, h: float, base_dir: Path) -> Tuple[Path, Path]:
    return _curv_paths(field_id, base_dir, h)
