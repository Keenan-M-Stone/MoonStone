from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException


router = APIRouter()


def _registry() -> Dict[str, Any]:
    """Describe metric/mapping options for generic GUI editors."""
    return {
        'mappings': {
            'sunstone': {
                'description': 'Default Plebanski mapping convention used by SunStone utilities',
            },
            'boston': {
                'description': 'SR Boston / paper-specific convention mapping (Eq. 11)',
            },
        },
        'metric_types': {
            'flat': {
                'description': 'Minkowski flat spacetime (baseline)',
                'params': {},
                'supports_trace': True,
                'supports_run': True,
            },
            'schwarzschild': {
                'description': 'Simple static Schwarzschild POC metric centered at origin',
                'params': {
                    'mass': {'type': 'number', 'default': 1.0},
                },
                'supports_trace': True,
                'supports_run': True,
                'gravity_model': 'gr',
            },
            'galadriel': {
                'description': 'SR Boston "Galadriel\'s Mirror" metric (Eq. 37 transcription)',
                'params': {
                    'f': {'type': 'number', 'default': 1.0},
                    'b': {'type': 'number', 'default': 0.0},
                    'r2_floor': {'type': 'number', 'default': 1e-12, 'optional': True},
                },
                'supports_trace': False,
                'supports_run': False,
                'gravity_model': 'gr',
            },
            'matrix': {
                'description': 'User-provided constant 4x4 metric matrix g_{μν}',
                'params': {
                    'g': {'type': 'matrix4', 'required': True},
                },
                'supports_trace': False,
                'supports_run': False,
                'gravity_model': 'user_supplied',
            },
            'field': {
                'description': 'Imported metric field on a regular 3D grid (see /moon/metric-field APIs)',
                'params': {
                    'field_id': {'type': 'string', 'required': True},
                },
                'supports_trace': False,
                'supports_run': False,
                'gravity_model': 'user_supplied',
            },
        },
        'gravity_models': {
            'gr': {
                'description': 'General relativity (metadata; analytic metrics are GR-based)',
            },
            'gr_weakfield_static': {
                'description': 'Interactive weak-field static approximation used by weakfield generator',
            },
            'user_supplied': {
                'description': 'User supplies a metric directly (matrix/field); MoonStone does not enforce field equations',
            },
        },
    }


@router.get('/metric-registry')
async def metric_registry():
    return _registry()


@router.post('/metric/validate')
async def metric_validate(body: Dict[str, Any]):
    """Validate a metric config and return warnings.

    Request body:
      { "metric": { ... } }
    """
    metric = body.get('metric', {}) if isinstance(body, dict) else {}
    try:
        from .metrics import validate_metric_cfg, metric_cfg_warnings

        norm = validate_metric_cfg(metric)
        warnings = metric_cfg_warnings(norm)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    mtype = norm.get('type', 'flat')
    reg = _registry()['metric_types']
    supports = reg.get(mtype, {}) if isinstance(reg, dict) else {}
    return {
        'metric': norm,
        'warnings': warnings,
        'supports_trace': bool(supports.get('supports_trace', False)),
        'supports_run': bool(supports.get('supports_run', False)),
    }
