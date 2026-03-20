from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RunStatus = Literal["created", "submitted", "running", "succeeded", "failed", "canceled"]


class RunRecord(BaseModel):
    id: str
    project_id: str
    created_at: str
    status: RunStatus
    backend: str


class StatusFile(BaseModel):
    status: RunStatus
    updated_at: str
    detail: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class JobFile(BaseModel):
    pid: int
    started_at: str
    backend: str
    mode: str


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ProjectRecord(BaseModel):
    id: str
    name: str
    created_at: str


class CreateRunRequest(BaseModel):
    spec: dict


class SubmitRunRequest(BaseModel):
    mode: Literal["local"] = "local"
    backend: str | None = None
    python_executable: str | None = None
    backend_options: dict | None = None


class SubmitRunResponse(BaseModel):
    run_id: str
    status: str


class ArtifactEntry(BaseModel):
    path: str
    size_bytes: int
    mtime: float


class ArtifactList(BaseModel):
    run_id: str
    artifacts: list[ArtifactEntry]
