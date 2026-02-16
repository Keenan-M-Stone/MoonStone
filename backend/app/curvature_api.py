from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from .models import TracePoint


router = APIRouter()


@router.post('/curvature')
async def curvature_at_point(point: TracePoint, metric: str | None = None, h: float = 1e-3):
    """Return an approximate static Ricci scalar R at a 3D point.

    Notes:
    - Uses numerical finite differences.
    - Assumes ∂_t g = 0.
    """
    from .metrics import validate_metric_cfg, metric_cfg_warnings, metric_at
    from .curvature import ricci_scalar_static

    metric_obj: Dict[str, Any]
    if metric is None or metric == '':
        metric_obj = {}
    else:
        try:
            metric_obj = json.loads(metric)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f'invalid metric JSON: {e}')

    try:
        metric_norm = validate_metric_cfg(metric_obj)
        warnings = metric_cfg_warnings(metric_norm)
        h = float(h)

        def mfn(p):
            return metric_at(p, metric_norm)

        out = ricci_scalar_static(mfn, (point.x, point.y, point.z), h=h)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        'point': {'x': point.x, 'y': point.y, 'z': point.z},
        'metric': metric_norm,
        'warnings': warnings + ['curvature is approximate (finite differences, static assumption ∂_t g=0)'],
        'ricci_scalar': out.ricci_scalar,
        'metric_det': out.metric_det,
        'params': {'h': h},
    }
