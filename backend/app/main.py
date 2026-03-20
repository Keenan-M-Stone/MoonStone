from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .traces import router as traces_router
from .runs import router as runs_router
from .metric_fields_api import router as metric_fields_router
from .metric_registry_api import router as metric_registry_router
from .curvature_api import router as curvature_router
from .compat_metrics_api import router as compat_metrics_router
from .compute_api import router as compute_router

# Pipeline routes (StarDust-compatible project/run infrastructure)
from .pipeline.routes.projects import router as pipeline_projects_router
from .pipeline.routes.runs import router as pipeline_runs_router
from .pipeline.routes.artifacts import router as pipeline_artifacts_router
from .pipeline.routes.backends import router as pipeline_backends_router

app = FastAPI(title="MoonStone Trace Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(traces_router, prefix="/moon")
app.include_router(runs_router, prefix="/moon")
app.include_router(metric_fields_router, prefix="/moon")
app.include_router(metric_registry_router, prefix="/moon")
app.include_router(curvature_router, prefix="/moon")
from .scenes import router as scenes_router
app.include_router(scenes_router, prefix="/moon")
app.include_router(compute_router, prefix="/moon")

# StarDust-compatible pipeline routes (project/run/artifact/backend management)
app.include_router(pipeline_projects_router)
app.include_router(pipeline_runs_router)
app.include_router(pipeline_artifacts_router)
app.include_router(pipeline_backends_router)

# Root-level compatibility endpoints for StarDust UI components (ResourceMonitor).
app.include_router(compat_metrics_router)

@app.get("/")
def root():
    return {"status": "ok", "service": "MoonStone trace service"}

