"""Metric-field import/export and sampling.

This module provides a lightweight way to store and sample a spacetime metric
that is defined on a regular 3D grid. It is intended as a baseline structure
for import/export and later composition with analytic perturbations.

File format (directory per field id):
  - meta.json : grid metadata
  - data.npz  : numpy array `g` with shape (nx, ny, nz, 4, 4)

Coordinates:
  - Cartesian (x, y, z) for now.
  - Metric components are assumed to be covariant g_{mu nu}.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Any, Dict, Iterable, Tuple

import time

import numpy as np


def _default_metric_field_dir() -> Path:
    # Allow tests and deployments to override location.
    override = os.environ.get('MOONSTONE_METRIC_FIELD_DIR')
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / 'metric_fields'


METRIC_FIELD_DIR = _default_metric_field_dir()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return int(default)


def _metric_field_limits() -> tuple[int, int]:
    # Defaults are intentionally conservative; override via env vars.
    max_fields = _env_int('MOONSTONE_METRIC_FIELD_MAX_FIELDS', 25)
    max_bytes = _env_int('MOONSTONE_METRIC_FIELD_MAX_BYTES', 2_500_000_000)
    return max_fields, max_bytes


def _dir_size_bytes(p: Path) -> int:
    total = 0
    try:
        for f in p.rglob('*'):
            if f.is_file():
                try:
                    total += int(f.stat().st_size)
                except Exception:
                    continue
    except Exception:
        return 0
    return total


def prune_metric_fields(
    *,
    base_dir: Path | None = None,
    max_fields: int | None = None,
    max_bytes: int | None = None,
) -> Dict[str, Any]:
    """Prune metric-field directories to enforce disk budget.

    Strategy: approximate LRU using directory mtime, deleting oldest first.
    """
    bd = base_dir or METRIC_FIELD_DIR
    bd.mkdir(parents=True, exist_ok=True)
    def_max_fields, def_max_bytes = _metric_field_limits()
    max_fields = int(def_max_fields if max_fields is None else max_fields)
    max_bytes = int(def_max_bytes if max_bytes is None else max_bytes)

    entries: list[tuple[Path, float, int]] = []
    total_bytes = 0
    for p in bd.iterdir():
        if not p.is_dir():
            continue
        if not (p / 'meta.json').exists() or not (p / 'data.npz').exists():
            continue
        try:
            # Use directory mtime; callers may touch meta/data to keep active.
            mtime = float(p.stat().st_mtime)
        except Exception:
            mtime = time.time()
        size = _dir_size_bytes(p)
        entries.append((p, mtime, size))
        total_bytes += int(size)

    entries.sort(key=lambda x: x[1])
    removed = 0
    removed_bytes = 0

    def needs_prune() -> bool:
        return (max_fields > 0 and len(entries) > max_fields) or (max_bytes > 0 and total_bytes > max_bytes)

    while entries and needs_prune():
        p, _, sz = entries.pop(0)
        try:
            shutil.rmtree(p, ignore_errors=True)
            removed += 1
            removed_bytes += int(sz)
            total_bytes -= int(sz)
        except Exception:
            continue

    summary = {
        'status': 'ok',
        'removed': removed,
        'removed_bytes': removed_bytes,
        'remaining_fields': len(entries),
        'remaining_bytes': total_bytes,
        'max_fields': max_fields,
        'max_bytes': max_bytes,
    }

    global _LAST_PRUNE_SUMMARY
    _LAST_PRUNE_SUMMARY = summary
    return summary


_LAST_PRUNE_SUMMARY: Dict[str, Any] | None = None


def metric_fields_last_prune() -> Dict[str, Any] | None:
    return _LAST_PRUNE_SUMMARY


def metric_fields_status(*, base_dir: Path | None = None) -> Dict[str, Any]:
    bd = base_dir or METRIC_FIELD_DIR
    bd.mkdir(parents=True, exist_ok=True)
    max_fields, max_bytes = _metric_field_limits()

    entries: list[tuple[Path, float, int]] = []
    total_bytes = 0
    for p in bd.iterdir():
        if not p.is_dir():
            continue
        if not (p / 'meta.json').exists() or not (p / 'data.npz').exists():
            continue
        try:
            mtime = float(p.stat().st_mtime)
        except Exception:
            mtime = time.time()
        size = _dir_size_bytes(p)
        entries.append((p, mtime, size))
        total_bytes += int(size)

    return {
        'status': 'ok',
        'base_dir': str(bd),
        'fields': int(len(entries)),
        'bytes': int(total_bytes),
        'max_fields': int(max_fields),
        'max_bytes': int(max_bytes),
    }


@dataclass(frozen=True)
class MetricFieldMeta:
    field_id: str
    origin: Tuple[float, float, float]
    spacing: Tuple[float, float, float]
    shape: Tuple[int, int, int]
    order: str = 'xyz'
    components: str = 'g_cov'
    signature: str = '-+++'
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            'version': int(self.version),
            'kind': 'metric_field',
            'id': self.field_id,
            'coord_system': 'cartesian',
            'grid': {
                'origin': list(map(float, self.origin)),
                'spacing': list(map(float, self.spacing)),
                'shape': list(map(int, self.shape)),
                'order': str(self.order),
            },
            'components': str(self.components),
            'signature': str(self.signature),
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> 'MetricFieldMeta':
        grid = d.get('grid', {}) if isinstance(d, dict) else {}
        return MetricFieldMeta(
            field_id=str(d.get('id', '')),
            origin=tuple(float(x) for x in grid.get('origin', (0.0, 0.0, 0.0))),
            spacing=tuple(float(x) for x in grid.get('spacing', (1.0, 1.0, 1.0))),
            shape=tuple(int(x) for x in grid.get('shape', (0, 0, 0))),
            order=str(grid.get('order', 'xyz')),
            components=str(d.get('components', 'g_cov')),
            signature=str(d.get('signature', '-+++')),
            version=int(d.get('version', 1)),
        )


def _field_dir(field_id: str, *, base_dir: Path | None = None) -> Path:
    bd = base_dir or METRIC_FIELD_DIR
    return bd / field_id


def save_metric_field(
    field_id: str,
    meta: MetricFieldMeta,
    g: np.ndarray,
    *,
    base_dir: Path | None = None,
) -> Path:
    """Persist a metric field to disk."""
    g = np.asarray(g, dtype=float)
    if g.ndim != 5 or g.shape[-2:] != (4, 4):
        raise ValueError('g must have shape (nx, ny, nz, 4, 4)')

    nx, ny, nz = g.shape[0], g.shape[1], g.shape[2]
    if (nx, ny, nz) != tuple(meta.shape):
        raise ValueError(f'meta.shape {meta.shape} does not match g grid {(nx, ny, nz)}')

    p = _field_dir(field_id, base_dir=base_dir)
    p.mkdir(parents=True, exist_ok=True)
    meta_path = p / 'meta.json'
    data_path = p / 'data.npz'
    with meta_path.open('w') as fh:
        json.dump(meta.to_dict(), fh, indent=2)
    np.savez_compressed(data_path, g=g)
    # Automatic pruning (best-effort) to keep disk bounded.
    try:
        prune_metric_fields(base_dir=base_dir)
    except Exception:
        pass
    return p


def load_metric_field(
    field_id: str,
    *,
    base_dir: Path | None = None,
    mmap_mode: str | None = 'r',
) -> Tuple[MetricFieldMeta, np.ndarray]:
    """Load a metric field from disk."""
    p = _field_dir(field_id, base_dir=base_dir)
    meta_path = p / 'meta.json'
    data_path = p / 'data.npz'
    if not meta_path.exists() or not data_path.exists():
        raise FileNotFoundError(f'metric field not found: {field_id}')

    with meta_path.open('r') as fh:
        meta_dict = json.load(fh)
    meta = MetricFieldMeta.from_dict(meta_dict)
    # np.load can memory-map .npz members in some NumPy versions; if not, it still avoids full copies.
    npz = np.load(data_path, mmap_mode=mmap_mode)
    g = np.asarray(npz['g'], dtype=float)
    return meta, g


def list_metric_fields(*, base_dir: Path | None = None) -> Iterable[str]:
    bd = base_dir or METRIC_FIELD_DIR
    bd.mkdir(parents=True, exist_ok=True)
    for p in bd.iterdir():
        if p.is_dir() and (p / 'meta.json').exists() and (p / 'data.npz').exists():
            yield p.name


def delete_metric_field(field_id: str, *, base_dir: Path | None = None) -> None:
    p = _field_dir(field_id, base_dir=base_dir)
    if not p.exists():
        return
    shutil.rmtree(p, ignore_errors=True)


def sample_metric_field(
    point: Tuple[float, float, float],
    meta: MetricFieldMeta,
    g: np.ndarray,
    *,
    clamp: bool = True,
) -> np.ndarray:
    """Sample g_{mu nu}(x,y,z) using trilinear interpolation."""
    x, y, z = (float(point[0]), float(point[1]), float(point[2]))
    x0, y0, z0 = meta.origin
    dx, dy, dz = meta.spacing
    nx, ny, nz = meta.shape

    if dx == 0 or dy == 0 or dz == 0:
        raise ValueError('grid spacing must be non-zero')

    fx = (x - x0) / dx
    fy = (y - y0) / dy
    fz = (z - z0) / dz

    # For interpolation we need i0 within [0, n-2]
    def _idx(frac: float, n: int) -> Tuple[int, float]:
        if n < 2:
            return 0, 0.0
        if clamp:
            # Clamp to the grid domain [0, n-1]. Keep the interpolant well-defined
            # for exact-boundary samples by snapping (i0,t) to (n-2,1) at the top.
            if frac <= 0.0:
                return 0, 0.0
            if frac >= float(n - 1):
                return n - 2, 1.0
        i0 = int(np.floor(frac))
        t = float(frac - i0)
        if clamp:
            i0 = max(0, min(i0, n - 2))
            t = max(0.0, min(t, 1.0))
        return i0, t

    ix, tx = _idx(fx, nx)
    iy, ty = _idx(fy, ny)
    iz, tz = _idx(fz, nz)

    g000 = g[ix, iy, iz]
    g100 = g[ix + 1, iy, iz] if nx > 1 else g000
    g010 = g[ix, iy + 1, iz] if ny > 1 else g000
    g110 = g[ix + 1, iy + 1, iz] if (nx > 1 and ny > 1) else g000
    g001 = g[ix, iy, iz + 1] if nz > 1 else g000
    g101 = g[ix + 1, iy, iz + 1] if (nx > 1 and nz > 1) else g000
    g011 = g[ix, iy + 1, iz + 1] if (ny > 1 and nz > 1) else g000
    g111 = g[ix + 1, iy + 1, iz + 1] if (nx > 1 and ny > 1 and nz > 1) else g000

    # trilinear blend
    c00 = g000 * (1.0 - tx) + g100 * tx
    c10 = g010 * (1.0 - tx) + g110 * tx
    c01 = g001 * (1.0 - tx) + g101 * tx
    c11 = g011 * (1.0 - tx) + g111 * tx
    c0 = c00 * (1.0 - ty) + c10 * ty
    c1 = c01 * (1.0 - ty) + c11 * ty
    out = c0 * (1.0 - tz) + c1 * tz
    return np.asarray(out, dtype=float)


def generate_weakfield_metric_grid(
    *,
    origin: Tuple[float, float, float],
    spacing: Tuple[float, float, float],
    shape: Tuple[int, int, int],
    objects: Iterable[Dict[str, Any]],
    softening: float = 1e-6,
    max_points: int = 256 * 256 * 256,
) -> np.ndarray:
    """Generate a weak-field static metric grid from point-mass objects.

    This is an interactive, low-cost approximation meant for GUI responsiveness.
    It uses a post-Newtonian style metric (geometric units, c=G=1):

    Phi(x) = -\\sum_i M_i / sqrt(|x-x_i|^2 + softening^2)
      g_tt = -(1 + 2 Phi)
      g_ij = (1 - 2 Phi) delta_ij

    No frame-dragging or time dependence is included.
    """
    nx, ny, nz = (int(shape[0]), int(shape[1]), int(shape[2]))
    if nx <= 0 or ny <= 0 or nz <= 0:
        raise ValueError('shape must be positive')
    npts = nx * ny * nz
    if npts > int(max_points):
        raise ValueError(f'grid too large for interactive generator: {npts} > {max_points}')

    x0, y0, z0 = (float(origin[0]), float(origin[1]), float(origin[2]))
    dx, dy, dz = (float(spacing[0]), float(spacing[1]), float(spacing[2]))
    if dx == 0 or dy == 0 or dz == 0:
        raise ValueError('spacing must be non-zero')

    xs = x0 + dx * np.arange(nx, dtype=float)
    ys = y0 + dy * np.arange(ny, dtype=float)
    zs = z0 + dz * np.arange(nz, dtype=float)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')

    phi = np.zeros((nx, ny, nz), dtype=float)
    soft2 = float(softening) * float(softening)
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        m = float(obj.get('mass', 0.0))
        pos = obj.get('position', obj.get('pos', obj.get('center', (0.0, 0.0, 0.0))))
        try:
            ox, oy, oz = (float(pos[0]), float(pos[1]), float(pos[2]))
        except Exception:
            p = pos if isinstance(pos, dict) else {}
            ox, oy, oz = (float(p.get('x', 0.0)), float(p.get('y', 0.0)), float(p.get('z', 0.0)))

        if m == 0.0:
            continue
        r2 = (X - ox) ** 2 + (Y - oy) ** 2 + (Z - oz) ** 2 + soft2
        r = np.sqrt(r2)
        phi += -m / r

    g = np.zeros((nx, ny, nz, 4, 4), dtype=float)
    g00 = -(1.0 + 2.0 * phi)
    g11 = (1.0 - 2.0 * phi)
    g[:, :, :, 0, 0] = g00
    g[:, :, :, 1, 1] = g11
    g[:, :, :, 2, 2] = g11
    g[:, :, :, 3, 3] = g11
    return g
