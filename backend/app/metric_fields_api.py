from __future__ import annotations

import json
import uuid
from typing import Any, Dict

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .metric_fields import (
    METRIC_FIELD_DIR,
    MetricFieldMeta,
    generate_weakfield_metric_grid,
    delete_metric_field,
    list_metric_fields,
    load_metric_field,
    save_metric_field,
)


router = APIRouter()


@router.get('/metric-fields')
async def metric_fields_list():
    return {'metric_fields': list(list_metric_fields())}


@router.get('/metric-field/{field_id}/meta')
async def metric_field_meta(field_id: str):
    try:
        meta, _ = load_metric_field(field_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail='not found')
    return meta.to_dict()


@router.get('/metric-field/{field_id}/data')
async def metric_field_data(field_id: str):
    p = METRIC_FIELD_DIR / field_id / 'data.npz'
    if not p.exists():
        raise HTTPException(status_code=404, detail='not found')
    return FileResponse(str(p), media_type='application/octet-stream', filename=f'{field_id}.npz')


@router.post('/metric-field/{field_id}/curvature/ricci-scalar')
async def metric_field_curvature_ricci_scalar(field_id: str, h: float = 1e-3, force: bool = False):
    """Compute (or load cached) Ricci scalar volume for a metric field."""
    try:
        from .curvature_fields import compute_ricci_scalar_volume_for_field

        meta = compute_ricci_scalar_volume_for_field(
            field_id,
            h=float(h),
            base_dir=METRIC_FIELD_DIR,
            force=bool(force),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return meta.to_dict()


@router.get('/metric-field/{field_id}/curvature/ricci-scalar/meta')
async def metric_field_curvature_ricci_scalar_meta(field_id: str, h: float = 1e-3):
    try:
        from .curvature_fields import compute_ricci_scalar_volume_for_field

        meta = compute_ricci_scalar_volume_for_field(
            field_id,
            h=float(h),
            base_dir=METRIC_FIELD_DIR,
            force=False,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return meta.to_dict()


@router.get('/metric-field/{field_id}/curvature/ricci-scalar/data')
async def metric_field_curvature_ricci_scalar_data(field_id: str, h: float = 1e-3):
    try:
        from .curvature_fields import curvature_volume_paths

        _, data_path = curvature_volume_paths(field_id, h=float(h), base_dir=METRIC_FIELD_DIR)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not data_path.exists():
        raise HTTPException(status_code=404, detail='not found (compute first)')
    return FileResponse(str(data_path), media_type='application/octet-stream', filename=f'{field_id}_ricci_scalar.npz')


@router.delete('/metric-field/{field_id}')
async def metric_field_delete(field_id: str):
    delete_metric_field(field_id)
    return {'status': 'ok'}


@router.post('/metric-field')
async def metric_field_upload(
    meta: UploadFile = File(...),
    data: UploadFile = File(...),
    field_id: str | None = None,
):
    """Upload a metric field.

    Expects multipart form-data with:
      - meta: JSON file containing the MetricFieldMeta dict
      - data: .npz containing array `g` with shape (nx, ny, nz, 4, 4)
    """
    fid = field_id or str(uuid.uuid4())

    try:
        meta_bytes = await meta.read()
        meta_dict: Dict[str, Any] = json.loads(meta_bytes.decode('utf-8'))
        parsed = MetricFieldMeta.from_dict(meta_dict)
        # override id to match fid (server controls the storage id)
        parsed = MetricFieldMeta(
            field_id=fid,
            origin=parsed.origin,
            spacing=parsed.spacing,
            shape=parsed.shape,
            order=parsed.order,
            components=parsed.components,
            signature=parsed.signature,
            version=parsed.version,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'invalid meta: {e}')

    try:
        data_bytes = await data.read()
        # Load from bytes to validate content before writing.
        import io

        npz = np.load(io.BytesIO(data_bytes))
        if 'g' not in npz:
            raise ValueError('npz missing array "g"')
        g = np.asarray(npz['g'], dtype=float)
        if g.ndim != 5 or g.shape[-2:] != (4, 4):
            raise ValueError('g must have shape (nx, ny, nz, 4, 4)')
        if tuple(g.shape[:3]) != tuple(parsed.shape):
            raise ValueError(f'g grid {tuple(g.shape[:3])} does not match meta.shape {parsed.shape}')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'invalid data: {e}')

    save_metric_field(fid, parsed, g)
    return {'id': fid, 'meta': parsed.to_dict()}


@router.post('/metric-field/generate/weakfield')
async def metric_field_generate_weakfield(body: Dict[str, Any]):
    """Generate an interactive weak-field baseline metric and store it as a metric field.

    Body shape (example):
      {
        "grid": {"origin": [..], "spacing": [..], "shape": [..]},
        "objects": [{"mass": 1.0, "position": [x,y,z]}, ...],
        "softening": 1e-6,
        "field_id": "optional"
      }
    """
    grid = body.get('grid', {}) if isinstance(body, dict) else {}
    origin = tuple(grid.get('origin', (0.0, 0.0, 0.0)))
    spacing = tuple(grid.get('spacing', (1.0, 1.0, 1.0)))
    shape = tuple(grid.get('shape', (32, 32, 32)))
    objects = body.get('objects', []) if isinstance(body, dict) else []
    softening = float(body.get('softening', 1e-6)) if isinstance(body, dict) else 1e-6
    fid = (body.get('field_id') if isinstance(body, dict) else None) or str(uuid.uuid4())

    try:
        g = generate_weakfield_metric_grid(
            origin=(float(origin[0]), float(origin[1]), float(origin[2])),
            spacing=(float(spacing[0]), float(spacing[1]), float(spacing[2])),
            shape=(int(shape[0]), int(shape[1]), int(shape[2])),
            objects=objects,
            softening=softening,
        )
        meta = MetricFieldMeta(
            field_id=fid,
            origin=(float(origin[0]), float(origin[1]), float(origin[2])),
            spacing=(float(spacing[0]), float(spacing[1]), float(spacing[2])),
            shape=(int(shape[0]), int(shape[1]), int(shape[2])),
        )
        save_metric_field(fid, meta, g)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {'id': fid, 'meta': meta.to_dict()}


@router.post('/metric-field/generate/sample')
async def metric_field_generate_by_sampling(body: Dict[str, Any]):
    """Sample an existing metric config over a grid and store as a metric field.

    Body shape (example):
      {
        "grid": {"origin": [..], "spacing": [..], "shape": [..]},
        "metric": {"type": "schwarzschild", "mass": 1.0, ...},
        "field_id": "optional"
      }
    """
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail='body must be an object')

    grid = body.get('grid', {})
    metric_cfg = body.get('metric', {})
    origin = tuple(grid.get('origin', (0.0, 0.0, 0.0)))
    spacing = tuple(grid.get('spacing', (1.0, 1.0, 1.0)))
    shape = tuple(grid.get('shape', (32, 32, 32)))
    fid = body.get('field_id') or str(uuid.uuid4())

    try:
        from .metrics import validate_metric_cfg, metric_at

        metric_norm = validate_metric_cfg(metric_cfg)
        nx, ny, nz = int(shape[0]), int(shape[1]), int(shape[2])
        ox, oy, oz = float(origin[0]), float(origin[1]), float(origin[2])
        dx, dy, dz = float(spacing[0]), float(spacing[1]), float(spacing[2])
        g = np.zeros((nx, ny, nz, 4, 4), dtype=float)
        for ix in range(nx):
            x = ox + dx * ix
            for iy in range(ny):
                y = oy + dy * iy
                for iz in range(nz):
                    z = oz + dz * iz
                    g[ix, iy, iz] = metric_at((x, y, z), metric_norm)

        meta = MetricFieldMeta(
            field_id=fid,
            origin=(ox, oy, oz),
            spacing=(dx, dy, dz),
            shape=(nx, ny, nz),
        )
        save_metric_field(fid, meta, g)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {'id': fid, 'meta': meta.to_dict(), 'metric': metric_norm}
