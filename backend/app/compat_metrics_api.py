from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse


router = APIRouter(tags=["compat", "metrics"])


@router.get("/runs/{run_id}/resource")
def get_run_resource(run_id: str):
    # StarDust UI expects a list of samples (same shape as /runs/{id}/metrics)
    try:
        from .resource_monitor import get_run_samples

        return JSONResponse(content=get_run_samples(run_id))
    except Exception:
        return JSONResponse(content=[])


@router.get("/runs/{run_id}/metrics")
def get_run_metrics(run_id: str):
    # StarDust UI expects a list of samples (rolling window)
    try:
        from .resource_monitor import get_run_samples

        return JSONResponse(content=get_run_samples(run_id))
    except Exception:
        return JSONResponse(content=[])


@router.get("/metrics/hosts")
def get_hosts_metrics():
    # Match StarDust backend schema closely enough for the UI.
    try:
        import psutil  # type: ignore

        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        data = {
            "cpu_percent": cpu,
            "memory_total": getattr(mem, "total", None),
            "memory_available": getattr(mem, "available", None),
        }
        try:
            import GPUtil  # type: ignore

            gpus = GPUtil.getGPUs()
            data["gpus"] = [
                {
                    "id": g.id,
                    "name": getattr(g, "name", None),
                    "load": getattr(g, "load", None),
                    "memory_total": getattr(g, "memoryTotal", None),
                    "memory_used": getattr(g, "memoryUsed", None),
                }
                for g in gpus
            ]
        except Exception:
            data["gpus"] = None
        return JSONResponse(content=data)
    except Exception:
        return JSONResponse(content={})
