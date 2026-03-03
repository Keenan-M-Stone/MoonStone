from fastapi import APIRouter, BackgroundTasks, HTTPException
from .models import TraceRequest, TraceResult, TracePoint
from .geodesics import trace_flat, trace_schwarzschild_weak, trace_delayed, trace_flat_batch, trace_schwarzschild_batch, trace_static_metric_batch
import uuid
import json
from typing import Dict

router = APIRouter()

# in-memory store for demo
_TRACES: Dict[str, TraceResult] = {}

# Safety caps to avoid unbounded resource usage from client requests
MAX_DIRECTIONS = 2048
MAX_NPOINTS = 10000
MAX_STORED_TRACES = 200

@router.post('/trace', response_model=TraceResult)
async def submit_trace(req: TraceRequest, background_tasks: BackgroundTasks):
    tid = str(uuid.uuid4())
    metric_in = req.metric or {}
    # validate metric early so config errors show as 4xx (not 5xx)
    from .metrics import validate_metric_cfg, metric_cfg_warnings
    try:
        metric = validate_metric_cfg(metric_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    mtype = metric.get('type', 'flat')
    warnings = metric_cfg_warnings(metric)

    # Validate & enforce client-side caps to prevent abuse or accidental overloads.
    n_dirs = len(req.directions) if isinstance(req.directions, list) else 0
    if n_dirs > MAX_DIRECTIONS:
        raise HTTPException(status_code=400, detail=f"too many directions: {n_dirs} (max {MAX_DIRECTIONS})")

    # Respect an explicit npoints param if present, but clamp to a sane maximum.
    params = req.params or {}
    try:
        npoints_req = int(params.get('npoints')) if params.get('npoints') is not None else None
    except Exception:
        npoints_req = None
    if npoints_req is not None and (npoints_req <= 0 or npoints_req > MAX_NPOINTS):
        raise HTTPException(status_code=400, detail=f"invalid npoints: {npoints_req} (1..{MAX_NPOINTS})")

    # Check disk cache first (fast interactive hits)
    from .cache import cache_get, cache_set, cache_key
    trace_req_repr = {
        'source': {'x': req.source.x, 'y': req.source.y, 'z': req.source.z},
        'directions': [ {'x': d.x, 'y': d.y, 'z': d.z} for d in req.directions ],
        'metric': metric,
        'params': params
    }
    cached = cache_get(trace_req_repr)
    if cached is not None:
        # return cached trace result quickly
        trace_points = [TracePoint(x=p[0], y=p[1], z=p[2]) for p in cached['points']]
        res = TraceResult(id=cached.get('id', tid), points=trace_points, meta={'cached': True, 'metric': metric, 'warnings': warnings})
        _TRACES[res.id] = res
        # prune oldest traces if store grows too large
        if len(_TRACES) > MAX_STORED_TRACES:
            # pop oldest (insertion-ordered dict)
            oldest_key = next(iter(_TRACES))
            _TRACES.pop(oldest_key, None)
        return res

    # Not cached: compute
    directions = [ (d.x, d.y, d.z) for d in req.directions ]
    # matrix/field tracing uses the generic static-metric integrator; keep local for now
    if mtype in ('matrix', 'field'):
        try:
            results = trace_static_metric_batch((req.source.x, req.source.y, req.source.z), directions, metric, req.params or {})
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        try:
            # If Dask available, submit a single batched job (better for GPU-enabled workers)
            from dask.distributed import Client
            client = Client() if Client.scheduler_info()['address'] is None else Client()
            # prefer GPU workers when requested
            submit_options = {}
            if (req.params or {}).get('device') == 'gpu':
                submit_options['resources'] = {'GPU': 1}

            if mtype == 'schwarzschild':
                mass = metric.get('mass', 1.0)
                fut = client.submit('app.geodesics.trace_schwarzschild_batch', (req.source.x, req.source.y, req.source.z), directions, mass, req.params or {}, **submit_options)
            else:
                fut = client.submit('app.geodesics.trace_flat_batch', (req.source.x, req.source.y, req.source.z), directions, req.params or {}, **submit_options)
            results = client.gather(fut)
            # client.gather may return the batched result directly or a list with one element depending on serialization
            # normalize the possible wrapped result
            if isinstance(results, list) and len(results) == 1 and isinstance(results[0], list):
                results = results[0]
        except Exception:
            # fallback: local batched call
            if mtype == 'schwarzschild':
                mass = metric.get('mass', 1.0)
                results = trace_schwarzschild_batch((req.source.x, req.source.y, req.source.z), directions, mass, req.params or {})
            else:
                results = trace_flat_batch((req.source.x, req.source.y, req.source.z), directions, req.params or {})

    # record and cache
    pts_list = results[0] if results else []
    cache_set(trace_req_repr, {'id': tid, 'points': pts_list})
    trace_points = [TracePoint(x=p[0], y=p[1], z=p[2]) for p in pts_list]

    # Infer if a GPU analytic Kerr kernel was requested/used
    params_in = req.params or {}
    device_analytic_requested = False
    device_analytic_executed = False
    if params_in.get('method') == 'kerr_formal' and params_in.get('device') == 'gpu':
        device_analytic_requested = bool(params_in.get('analytic', True))
        # try to read the last kernel provenance information
        try:
            from . import accelerated_cuda
            prov = getattr(accelerated_cuda, '_LAST_KERNEL_INFO', {})
            device_analytic_executed = bool(prov.get('executed_analytic', False))
        except Exception:
            device_analytic_executed = False

    res_meta = {'cached': False, 'num_dirs': len(req.directions), 'metric': metric, 'warnings': warnings, 'device_analytic_requested': device_analytic_requested, 'device_analytic_executed': device_analytic_executed}
    res = TraceResult(id=tid, points=trace_points, meta=res_meta)
    _TRACES[tid] = res
    # prune oldest traces to keep memory bounded
    if len(_TRACES) > MAX_STORED_TRACES:
        oldest_key = next(iter(_TRACES))
        _TRACES.pop(oldest_key, None)
    return res

@router.get('/trace/{trace_id}', response_model=TraceResult)
async def get_trace(trace_id: str):
    return _TRACES[trace_id]

@router.post('/trace/clear')
async def clear_traces():
    """Administrative: clear in-memory trace store."""
    _TRACES.clear()
    return {'status': 'ok', 'cleared': True}


@router.get('/gpu')
async def gpu_status():
    """Report whether a CUDA-capable GPU is available on this server."""
    try:
        from stardust.gpu import is_cuda_available
        return {'cuda': bool(is_cuda_available())}
    except Exception:
        return {'cuda': False}


@router.get('/gpu/smoke')
async def gpu_smoke():
    """Run a tiny CUDA smoke test (best-effort).

    Returns quickly and never raises, so UIs can poll safely.
    """
    import time
    try:
        from . import accelerated_cuda
        if not getattr(accelerated_cuda, 'NUMBA_CUDA_OK', False):
            return {'cuda': False, 'ok': False, 'detail': 'numba cuda not available'}

        import numpy as np

        sources = np.array([[0.0, 0.0, 0.0]], dtype=float)
        dirs = np.array([[1.0, 0.0, 0.0]], dtype=float)
        params = {'npoints': 16, 'step': 1e-3}

        t0 = time.time()
        pts = accelerated_cuda.trace_flat_gpu(sources, dirs, params)[0]
        t1 = time.time()

        ok = bool(len(pts) == int(params['npoints']))
        if ok:
            # basic sanity: x should increase linearly and y,z ~ 0
            for j, p in enumerate(pts[:5]):
                if abs(float(p[1])) > 1e-8 or abs(float(p[2])) > 1e-8:
                    ok = False
                    break
                exp_x = float(j) * float(params['step'])
                if abs(float(p[0]) - exp_x) > 1e-6:
                    ok = False
                    break

        device_name = None
        try:
            from numba import cuda  # type: ignore

            device_name = str(cuda.get_current_device().name)
        except Exception:
            device_name = None

        return {
            'cuda': True,
            'ok': ok,
            'device': device_name,
            'elapsed_ms': (t1 - t0) * 1000.0,
        }
    except Exception as e:
        return {'cuda': False, 'ok': False, 'detail': str(e)}


@router.post('/metric')
async def get_metric_sample(point: TracePoint, metric: str | None = None):
    """Return Plebanski-style constitutive tensors at a 3D point for the requested metric."""
    # lazy import to avoid startup cost if not needed
    from .metrics import constitutive_at, validate_metric_cfg, metric_cfg_warnings
    metric_obj = {}
    if metric is None or metric == '':
        metric_obj = {}
    else:
        try:
            metric_obj = json.loads(metric)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f'invalid metric JSON: {e}')
    pt = (point.x, point.y, point.z)
    try:
        metric_norm = validate_metric_cfg(metric_obj)
        tensors = constitutive_at(pt, metric_norm)
        warnings = metric_cfg_warnings(metric_norm)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Avoid leaking internal stack traces as 500s for user config errors.
        raise HTTPException(status_code=400, detail=str(e))
    # serialize numpy arrays to lists
    return {
        'point': {'x': point.x, 'y': point.y, 'z': point.z},
        'metric': metric_norm,
        'warnings': warnings,
        'eps': tensors['eps'].tolist(),
        'mu': tensors['mu'].tolist(),
        'xi': tensors['xi'].tolist(),
        'zeta': tensors['zeta'].tolist(),
    }


from fastapi import Request

@router.post('/bench')
async def bench_solver(request: Request):
    """Run small benchmarks for requested solvers and return timing info.

    Accepts either:
    - JSON body { "solver": "weak" }
    - or { "solvers": ["weak","rk4"] }

    Returns per-solver mean times and estimates. If a single solver is requested
    the response keeps the historical single-solver shape for compatibility.
    """
    import time
    payload = await request.json() if request else {}
    metric = payload.get('metric', {}) if isinstance(payload, dict) else {}
    params = payload.get('params', {}) if isinstance(payload, dict) else {}
    ntest = int(params.get('ntest', 4))
    npoints = int(params.get('npoints', 256))
    mass = metric.get('mass', 1.0)

    from .geodesics import trace_flat, trace_schwarzschild_weak, trace_schwarzschild_rk4, trace_schwarzschild_rk4_adaptive, trace_null_geodesic, trace_null_formal, trace_kerr_formal

    # normalize solvers list
    if isinstance(payload, dict) and 'solvers' in payload:
        sol_list = payload['solvers']
    elif isinstance(payload, dict) and 'solver' in payload:
        sol_list = [payload['solver']]
    else:
        # if not provided, benchmark the defaults
        sol_list = ['weak', 'rk4', 'rk4_adaptive', 'null', 'null_formal', 'kerr_formal']

    def run_one(solver_name):
        src = (0.0, 1.0, 0.0)
        dir = (1.0, 0.0, 0.0)
        if solver_name == 'weak':
            _ = trace_schwarzschild_weak(src, dir, mass, {'npoints': npoints, 'step': params.get('step',1e-6)})
        elif solver_name == 'rk4':
            _ = trace_schwarzschild_rk4(src, dir, mass, {'npoints': npoints, 'step': params.get('step',1e-6)})
        elif solver_name == 'rk4_adaptive':
            _ = trace_schwarzschild_rk4_adaptive(src, dir, mass, {'npoints': npoints, 'step': params.get('step',1e-6), 'tol': params.get('tol',1e-7)})
        elif solver_name == 'null':
            _ = trace_null_geodesic(src, dir, mass, {'npoints': npoints, 'step': params.get('step',1e-6)})
        elif solver_name == 'null_formal':
            _ = trace_null_formal(src, dir, mass, {'npoints': npoints, 'step': params.get('step',1e-6)})
        elif solver_name == 'kerr_formal':
            _ = trace_kerr_formal(src, dir, mass, params={'npoints': npoints, 'step': params.get('step',1e-6), 'formal': True})
        else:
            _ = trace_schwarzschild_weak(src, dir, mass, {'npoints': npoints, 'step': params.get('step',1e-6)})

    results = {}
    for sname in sol_list:
        times = []
        for i in range(ntest):
            t0 = time.time()
            run_one(sname)
            t1 = time.time()
            times.append(t1 - t0)
        mean = sum(times)/len(times)
        results[sname] = {'mean_sec': mean, 'per_1000_rays': mean * 1000}

    # If a single solver was requested, return the historical single-solver shape
    if isinstance(payload, dict) and ('solver' in payload or ('solvers' in payload and len(payload['solvers']) == 1)):
        sname = sol_list[0]
        return {'solver': sname, 'npoints': npoints, 'ntest': ntest, 'mean_sec': results[sname]['mean_sec'], 'estimate': {'per_ray': results[sname]['mean_sec'], 'per_1000_rays': results[sname]['per_1000_rays']}}

    # store bench summary for each solver in persistent store
    try:
        from .bench_store import add_entry
        import time as _time
        ts = _time.time()
        for sname, info in results.items():
            add_entry({'solver': sname, 'mean_sec': info['mean_sec'], 'per_1000_rays': info['per_1000_rays'], 'npoints': npoints, 'ntest': ntest, 'ts': ts})
    except Exception:
        pass

    # store bench summary for each solver in persistent store
    try:
        from .bench_store import add_entry
        import time as _time
        ts = _time.time()
        for sname, info in results.items():
            add_entry({'solver': sname, 'mean_sec': info['mean_sec'], 'per_1000_rays': info['per_1000_rays'], 'npoints': npoints, 'ntest': ntest, 'ts': ts})
    except Exception:
        pass

    return {'npoints': npoints, 'ntest': ntest, 'results': results}


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
        samples.append({'point': {'x': p.x, 'y': p.y, 'z': p.z}, 'eps': t['eps'].tolist(), 'mu': t['mu'].tolist(), 'xi': t['xi'].tolist(), 'zeta': t['zeta'].tolist()})
    return {'trace_id': trace_id, 'metric': metric, 'samples': samples}


@router.post('/bench/save')
async def bench_save(body: dict):
    """Persist a benchmark entry. Body should include solver, mean_sec, npoints, etc."""
    try:
        from .bench_store import add_entry
        add_entry(body)
        return {'status': 'ok'}
    except Exception as e:
        return {'error': str(e)}


@router.get('/bench/history')
async def bench_history():
    try:
        from .bench_store import aggregate_by_solver
        return {'by_solver': aggregate_by_solver()}
    except Exception as e:
        return {'error': str(e)}


# WebSocket streaming endpoint for progressive trace updates
from fastapi import WebSocket, WebSocketDisconnect

@router.websocket('/trace/ws')
async def trace_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        req = await websocket.receive_json()
        # expect payload like: { source, directions, metric, params }
        source = req.get('source', {'x':0,'y':0,'z':0})
        metric = req.get('metric', {}) or {}
        directions = req.get('directions', [])
        params = req.get('params', {}) or {}
        mtype = metric.get('type', 'flat')
        # Stream per-direction partial results
        for i, d in enumerate(directions):
            dir_tuple = (d.get('x',0.0), d.get('y',0.0), d.get('z',0.0))
            if mtype == 'schwarzschild':
                mass = metric.get('mass', 1.0)
                pts = trace_schwarzschild_batch((source['x'], source['y'], source['z']), [dir_tuple], mass, params)[0]
            else:
                pts = trace_flat_batch((source['x'], source['y'], source['z']), [dir_tuple], params)[0]
            # prepare provenance/meta flags for streaming
            device_analytic_requested = False
            device_analytic_executed = False
            if params.get('method') == 'kerr_formal' and params.get('device') == 'gpu':
                device_analytic_requested = bool(params.get('analytic', True))
                try:
                    from . import accelerated_cuda
                    prov = getattr(accelerated_cuda, '_LAST_KERNEL_INFO', {})
                    device_analytic_executed = bool(prov.get('executed_analytic', False))
                except Exception:
                    device_analytic_executed = False
            # send progressive chunk
            await websocket.send_json({'type': 'partial', 'dir_index': i, 'points': [[float(p[0]), float(p[1]), float(p[2])] for p in pts], 'meta': {'dir': i, 'device_analytic_requested': device_analytic_requested, 'device_analytic_executed': device_analytic_executed}})
        await websocket.send_json({'type': 'done', 'meta': {'device_analytic_requested': device_analytic_requested, 'device_analytic_executed': device_analytic_executed}})
    except WebSocketDisconnect:
        # client disconnected
        return
