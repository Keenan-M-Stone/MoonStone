from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .traces import router as traces_router
from .runs import router as runs_router
from .metric_fields_api import router as metric_fields_router
from .metric_registry_api import router as metric_registry_router
from .curvature_api import router as curvature_router

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

@app.get("/")
def root():
    return {"status": "ok", "service": "MoonStone trace service"}
