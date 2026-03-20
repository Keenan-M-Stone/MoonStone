from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..models import CreateProjectRequest, ProjectRecord
from ..settings import Settings, get_settings
from ..store import RunStore

router = APIRouter(prefix="/projects", tags=["projects"])


def _store(settings: Settings) -> RunStore:
    s = RunStore(settings.data_dir)
    s.ensure()
    return s


@router.post("", response_model=ProjectRecord)
def create_project(
    req: CreateProjectRequest,
    settings: Settings = Depends(get_settings),
) -> ProjectRecord:
    store = _store(settings)
    rec = store.create_project(req.name)
    return ProjectRecord(**rec)


@router.get("/{project_id}", response_model=ProjectRecord)
def get_project(project_id: str, settings: Settings = Depends(get_settings)) -> ProjectRecord:
    store = _store(settings)
    try:
        rec = store.get_project(project_id)
        return ProjectRecord(**rec)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail="project not found") from err
