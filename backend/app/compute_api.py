from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter


router = APIRouter(tags=["compute"])


def _storage_status() -> Dict[str, Any]:
    out: Dict[str, Any] = {'status': 'ok'}
    try:
        from .cache import cache_status, cache_last_prune

        out['trace_cache'] = cache_status()
        out['trace_cache_last_prune'] = cache_last_prune()
    except Exception as e:
        out['trace_cache'] = {'status': 'error', 'detail': str(e)}

    try:
        from .metric_fields import metric_fields_status, metric_fields_last_prune

        out['metric_fields'] = metric_fields_status()
        out['metric_fields_last_prune'] = metric_fields_last_prune()
    except Exception as e:
        out['metric_fields'] = {'status': 'error', 'detail': str(e)}

    return out


def _compute_stats() -> Dict[str, Any]:
    out: Dict[str, Any] = {'status': 'ok'}
    try:
        from .metric_fields_api import metric_compute_stats

        out['metric_fields'] = metric_compute_stats()
    except Exception as e:
        out['metric_fields'] = {'status': 'error', 'detail': str(e)}
    return out


@router.get('/compute/stats')
async def compute_stats():
    """User-facing compute + storage snapshot used by UI panels."""
    out: Dict[str, Any] = {'status': 'ok'}
    out['compute'] = _compute_stats()
    out['storage'] = _storage_status()
    # GPU snapshot
    try:
        from .traces import gpu_status

        out['gpu'] = await gpu_status()  # type: ignore
    except Exception as e:
        out['gpu'] = {'cuda': False, 'detail': str(e)}
    return out


@router.get('/compute/storage-status')
def compute_storage_status():
    return _storage_status()


@router.post('/compute/prune-cache')
def compute_prune_cache(body: Dict[str, Any] | None = None):
    body = body or {}
    max_files = body.get('max_files', None)
    max_bytes = body.get('max_bytes', None)
    try:
        from .cache import cache_prune

        return cache_prune(
            max_files=(int(max_files) if max_files is not None else None),
            max_bytes=(int(max_bytes) if max_bytes is not None else None),
        )
    except Exception as e:
        return {'status': 'error', 'detail': str(e)}


@router.post('/compute/prune-metric-fields')
def compute_prune_metric_fields(body: Dict[str, Any] | None = None):
    body = body or {}
    max_fields = body.get('max_fields', None)
    max_bytes = body.get('max_bytes', None)
    try:
        from .metric_fields import prune_metric_fields

        return prune_metric_fields(
            max_fields=(int(max_fields) if max_fields is not None else None),
            max_bytes=(int(max_bytes) if max_bytes is not None else None),
        )
    except Exception as e:
        return {'status': 'error', 'detail': str(e)}


@router.get('/compute/gpu')
async def compute_gpu_status():
    try:
        from .traces import gpu_status

        return await gpu_status()  # type: ignore
    except Exception:
        return {'cuda': False}


@router.get('/compute/gpu/smoke')
async def compute_gpu_smoke():
    try:
        from .traces import gpu_smoke

        return await gpu_smoke()  # type: ignore
    except Exception as e:
        return {'cuda': False, 'ok': False, 'detail': str(e)}


# Back-compat deprecated aliases (user requested rename now; keep these temporarily).
@router.get('/admin/storage-status')
def admin_storage_status_deprecated():
    out = _storage_status()
    out['deprecated'] = True
    return out


@router.post('/admin/prune-cache')
def admin_prune_cache_deprecated(body: Dict[str, Any] | None = None):
    out = compute_prune_cache(body)
    if isinstance(out, dict):
        out['deprecated'] = True
    return out


@router.post('/admin/prune-metric-fields')
def admin_prune_metric_fields_deprecated(body: Dict[str, Any] | None = None):
    out = compute_prune_metric_fields(body)
    if isinstance(out, dict):
        out['deprecated'] = True
    return out
