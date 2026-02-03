from fastapi import APIRouter, BackgroundTasks
from .models import TracePoint
import uuid
import time
from typing import Dict, Any
from .metrics import constitutive_at
from .geodesics import trace_schwarzschild_weak, trace_flat, trace_schwarzschild_rk4_adaptive, trace_schwarzschild_rk4, trace_kerr_formal

# detect CUDA availability in a non-fatal way
try:
    from .accelerated_cuda import NUMBA_CUDA_OK as _NUMBA_CUDA_OK, trace_kerr_gpu
except Exception:
    _NUMBA_CUDA_OK = False
    trace_kerr_gpu = None

router = APIRouter()

_RUNS: Dict[str, Dict[str, Any]] = {}

@router.post('/run')
def submit_run(body: Dict[str, Any], background_tasks: BackgroundTasks):
    """Submit a run job. body contains: scene, solver, params, metric, observers
    For POC we run a long-lived computation in background and store results.
    """
    rid = str(uuid.uuid4())
    run = {
        'id': rid,
        'status': 'queued',
        'body': body,
        'log': [],
        'result': None,
    }
    _RUNS[rid] = run

    def worker(rid: str):
        r = _RUNS[rid]
        r['status'] = 'running'
        r['log'].append('Started run')
        # choose a solver
        solver = body.get('solver', 'reference')
        # simulate work: either run many trace directions or sleep
        try:
            if solver == 'interactive':
                # short run
                time.sleep(0.5)
                r['log'].append('Interactive quick run complete')
                r['status'] = 'finished'
                r['result'] = {'note': 'quick result (interactive)'}
            else:
                # heavy run: sample many rays and compute tensors
                source = body.get('source', {'x':0,'y':0,'z':0})
                metric = body.get('metric', {'type':'schwarzschild','mass':1.0})
                n_dirs = body.get('n_dirs', 128)
                # generate directions on a grid (POC)
                points = []
                solver_method = body.get('solver_method', None)
                t0_run = time.time()
                for i in range(n_dirs):
                    d = (1.0, 0.0, 0.0)
                    params = {'npoints':512, 'step':1e-7}
                    if solver_method == 'rk4_adaptive':
                        pts = trace_schwarzschild_rk4_adaptive((source['x'], source['y'], source['z']), d, metric.get('mass',1.0), params=params)
                    elif solver_method == 'rk4':
                        pts = trace_schwarzschild_rk4((source['x'], source['y'], source['z']), d, metric.get('mass',1.0), params=params)
                    elif solver_method == 'kerr_formal':
                        # choose GPU if requested and available
                        if body.get('device') == 'gpu' and _NUMBA_CUDA_OK and trace_kerr_gpu is not None:
                            try:
                                import numpy as _np
                                s_arr = _np.array([[source['x'], source['y'], source['z']]], dtype=float)
                                d_arr = _np.array([[d[0], d[1], d[2]]], dtype=float)
                                m_arr = _np.array([metric.get('mass',1.0)], dtype=float)
                                pts = trace_kerr_gpu(s_arr, d_arr, m_arr, {'npoints':512, 'step':1e-7, 'spin': body.get('spin', (0,0,0))})[0]
                            except Exception:
                                pts = trace_kerr_formal((source['x'], source['y'], source['z']), d, metric.get('mass',1.0), body.get('spin', (0,0,0)), params=params)
                        else:
                            pts = trace_kerr_formal((source['x'], source['y'], source['z']), d, metric.get('mass',1.0), body.get('spin', (0,0,0)), params=params)
                    else:
                        pts = trace_schwarzschild_weak((source['x'], source['y'], source['z']), d, metric.get('mass',1.0), params=params)
                    points.append(pts)
                    if i % 8 == 0:
                        r['log'].append(f'Processed {i} dirs')
                t1_run = time.time()
                total_time = t1_run - t0_run
                mean_per_ray = total_time / float(max(1, n_dirs))
                # compute tensors at first few points
                samples = []
                for p in pts[:16]:
                    t = constitutive_at((p[0], p[1], p[2]), metric)
                    samples.append({'point': p, 'eps': t['eps'].tolist()})
                r['status'] = 'finished'
                r['log'].append('Heavy run complete')
                r['result'] = {'samples': samples, 'n_dirs': n_dirs, 'timing': {'total_sec': total_time, 'mean_per_ray': mean_per_ray}}
                # persist benchmark sample for later aggregation
                try:
                    from .bench_store import add_entry
                    add_entry({'solver': solver_method or 'weak', 'mean_sec': mean_per_ray, 'per_1000_rays': mean_per_ray * 1000, 'npoints': 512, 'n_dirs': n_dirs, 'ts': time.time()})
                except Exception:
                    pass
        except Exception as e:
            r['status'] = 'failed'
            r['log'].append(f'Error: {e}')

    background_tasks.add_task(worker, rid)
    return {'run_id': rid}

@router.get('/run/{run_id}')
def get_run(run_id: str):
    return _RUNS.get(run_id, {'error': 'not found'})

@router.get('/run/{run_id}/log')
def get_run_log(run_id: str):
    run = _RUNS.get(run_id)
    if not run:
        return {'error': 'not found'}
    return {'log': run['log'], 'status': run['status']}
