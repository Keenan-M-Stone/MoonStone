from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .traces import router as traces_router

app = FastAPI(title="MoonStone Trace Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(traces_router, prefix="/moon")

@app.get("/")
def root():
    return {"status": "ok", "service": "MoonStone trace service"}
