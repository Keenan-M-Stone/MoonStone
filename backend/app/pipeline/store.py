from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from .models import RunRecord, StatusFile
from .time_util import utc_now_iso


def _get_logger(data_dir: Path):
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "backend.log"
    logger = logging.getLogger("moonstone_backend")
    if not logger.hasHandlers():
        handler = logging.FileHandler(log_path, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


class RunStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.projects_dir = self.data_dir / "projects"
        self.runs_dir = self.data_dir / "runs"
        self.logger = _get_logger(self.data_dir)

    def ensure(self) -> None:
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    # Projects
    def create_project(self, name: str) -> dict:
        self.ensure()
        project_id = uuid.uuid4().hex
        rec = {"id": project_id, "name": name, "created_at": utc_now_iso()}
        project_path = self.projects_dir / project_id
        project_path.mkdir(parents=True, exist_ok=False)
        (project_path / "project.json").write_text(json.dumps(rec, indent=2))
        return rec

    def get_project(self, project_id: str) -> dict:
        path = self.projects_dir / project_id / "project.json"
        if not path.exists():
            raise FileNotFoundError(project_id)
        return json.loads(path.read_text())

    # Runs
    def create_run(self, project_id: str, spec: dict, backend: str) -> RunRecord:
        self.ensure()
        _ = self.get_project(project_id)

        run_id = uuid.uuid4().hex
        run_dir = self.run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=False)

        (run_dir / "runtime").mkdir(parents=True)
        (run_dir / "logs").mkdir(parents=True)
        (run_dir / "outputs").mkdir(parents=True)

        (run_dir / "spec.json").write_text(json.dumps(spec, indent=2))
        (run_dir / "runtime" / "backend.json").write_text(
            json.dumps({"backend": backend}, indent=2)
        )

        rec = RunRecord(
            id=run_id,
            project_id=project_id,
            created_at=utc_now_iso(),
            status="created",
            backend=backend,
        )
        (run_dir / "runtime" / "run.json").write_text(rec.model_dump_json(indent=2))

        status = StatusFile(status="created", updated_at=utc_now_iso())
        (run_dir / "runtime" / "status.json").write_text(status.model_dump_json(indent=2))

        self.logger.info("Created run %s for project %s", run_id, project_id)
        return rec

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / f"run_{run_id}"

    def load_run(self, run_id: str) -> RunRecord:
        path = self.run_dir(run_id) / "runtime" / "run.json"
        if not path.exists():
            raise FileNotFoundError(run_id)
        run = RunRecord.model_validate_json(path.read_text())
        status_path = self.run_dir(run_id) / "runtime" / "status.json"
        if status_path.exists():
            status = StatusFile.model_validate_json(status_path.read_text())
            run.status = status.status
        return run

    def save_run(self, run: RunRecord) -> None:
        (self.run_dir(run.id) / "runtime" / "run.json").write_text(run.model_dump_json(indent=2))

    def load_status(self, run_id: str) -> StatusFile:
        path = self.run_dir(run_id) / "runtime" / "status.json"
        if not path.exists():
            raise FileNotFoundError(run_id)
        return StatusFile.model_validate_json(path.read_text())

    def save_status(self, run_id: str, status: StatusFile) -> None:
        (self.run_dir(run_id) / "runtime" / "status.json").write_text(
            status.model_dump_json(indent=2)
        )
