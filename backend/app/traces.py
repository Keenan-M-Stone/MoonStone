from fastapi import APIRouter, BackgroundTasks
from .models import TraceRequest, TraceResult, TracePoint
from .geodesics import trace_flat, trace_schwarzschild_weak, trace_delayed
import uuid
from typing import Dict

router = APIRouter()

# in-memory store for demo
_TRACES: Dict[str, TraceResult] = {}

@router.post('/trace', response_model=TraceResult)
async def submit_trace(req: TraceRequest, background_tasks: BackgroundTasks):
    tid = str(uuid.uuid4())
    metric = req.metric or {}
    mtype = metric.get('type', 'flat')

    # Choose a worker strategy: use Dask distributed if available, otherwise run locally
    try:
        from dask.distributed import Client, as_completed
        # connect to scheduler if environment variable provided, else create local
        client = Client() if Client.scheduler_info()['address'] is None else Client()
        futures = []
        for d in req.directions:
            dir_tuple = (d.x, d.y, d.z)
            if mtype == 'schwarzschild':
                mass = metric.get('mass', 1.0)
                fut = client.submit(trace_schwarzschild_weak, (req.source.x, req.source.y, req.source.z), dir_tuple, mass)
            else:
                fut = client.submit(trace_flat, (req.source.x, req.source.y, req.source.z), dir_tuple)
            futures.append(fut)
        results = client.gather(futures)
    except Exception:
        # fallback: simple local map
        results = []
        for d in req.directions:
            dir_tuple = (d.x, d.y, d.z)
            if mtype == 'schwarzschild':
                mass = metric.get('mass', 1.0)
                points = trace_schwarzschild_weak((req.source.x, req.source.y, req.source.z), dir_tuple, mass=mass)
            else:
                points = trace_flat((req.source.x, req.source.y, req.source.z), dir_tuple)
            results.append(points)

    # For now, record the first direction's trace and include meta for number of directions
    trace_points = [TracePoint(x=p[0], y=p[1], z=p[2]) for p in (results[0] if results else [])]
    res = TraceResult(id=tid, points=trace_points, meta={'num_dirs': len(req.directions), 'metric': metric})
    _TRACES[tid] = res
    return res

@router.get('/trace/{trace_id}', response_model=TraceResult)
async def get_trace(trace_id: str):
    return _TRACES[trace_id]


@router.post('/metric')
async def get_metric_sample(point: TracePoint, metric: dict = None):
    """Return Plebanski-style constitutive tensors at a 3D point for the requested metric."""
    # lazy import to avoid startup cost if not needed
    from .metrics import constitutive_at
    metric = metric or {}
    pt = (point.x, point.y, point.z)
    tensors = constitutive_at(pt, metric)
    # serialize numpy arrays to lists
    return {
        'point': {'x': point.x, 'y': point.y, 'z': point.z},
        'metric': metric,
        'eps': tensors['eps'].tolist(),
        'mu': tensors['mu'].tolist(),
        'xi': tensors['xi'].tolist(),
    }


@router.post('/export')
async def export_trace_tensor(trace_id: str):
    """Export constitutive tensors sampled along a stored trace (JSON)."""
    from .metrics import constitutive_at
    if trace_id not in _TRACES:
        return {'error': 'trace not found'}
    trace = _TRACES[trace_id]
    samples = []
    metric = trace.meta.get('metric', {}) if trace.meta else {}
    for p in trace.points:
        t = constitutive_at((p.x, p.y, p.z), metric)
        samples.append({'point': {'x': p.x, 'y': p.y, 'z': p.z}, 'eps': t['eps'].tolist(), 'mu': t['mu'].tolist(), 'xi': t['xi'].tolist()})
    return {'trace_id': trace_id, 'metric': metric, 'samples': samples}
