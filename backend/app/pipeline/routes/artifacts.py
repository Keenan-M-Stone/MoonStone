from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..models import ArtifactEntry, ArtifactList
from ..settings import Settings, get_settings
from ..store import RunStore

router = APIRouter(tags=["artifacts"])


def _store(settings: Settings) -> RunStore:
    s = RunStore(settings.data_dir)
    s.ensure()
    return s


def _safe_join(root: Path, rel: str) -> Path:
    candidate = (root / rel).resolve()
    root_resolved = root.resolve()
    if root_resolved == candidate or root_resolved in candidate.parents:
        return candidate
    raise ValueError("illegal path")


def _iter_artifacts(run_dir: Path) -> list[ArtifactEntry]:
    artifacts: list[ArtifactEntry] = []
    for rel_root in ["outputs", "logs", "runtime"]:
        base = run_dir / rel_root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                st = path.stat()
                artifacts.append(
                    ArtifactEntry(
                        path=str(path.relative_to(run_dir)),
                        size_bytes=st.st_size,
                        mtime=st.st_mtime,
                    )
                )
    artifacts.sort(key=lambda a: a.path)
    return artifacts


@router.get("/runs/{run_id}/artifacts", response_model=ArtifactList)
def list_artifacts(run_id: str, settings: Settings = Depends(get_settings)) -> ArtifactList:
    store = _store(settings)
    run_dir = store.run_dir(run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run not found")
    return ArtifactList(run_id=run_id, artifacts=_iter_artifacts(run_dir))


@router.get("/runs/{run_id}/artifacts/{path:path}")
def download_artifact(run_id: str, path: str, settings: Settings = Depends(get_settings)):
    store = _store(settings)
    run_dir = store.run_dir(run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run not found")

    try:
        resolved = _safe_join(run_dir, path)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="invalid path") from err

    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")

    return FileResponse(str(resolved), filename=os.path.basename(resolved))
