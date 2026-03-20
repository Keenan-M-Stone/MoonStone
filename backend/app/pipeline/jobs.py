from __future__ import annotations

import os
import signal
import subprocess
import sys
import logging
from pathlib import Path

from .models import JobFile, RunRecord
from .time_util import utc_now_iso

logger = logging.getLogger(__name__)


class LocalJobRunner:
    def submit(
        self,
        run: RunRecord,
        run_dir: Path,
        backend: str,
        python_executable: str | None = None,
    ) -> JobFile:
        logs_dir = run_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = logs_dir / "stdout.log"
        stderr_path = logs_dir / "stderr.log"

        py = (python_executable.strip() if python_executable else sys.executable)

        cmd = [
            py,
            "-m",
            "app.pipeline.worker",
            "--run-dir",
            str(run_dir),
            "--backend",
            backend,
        ]

        with open(stdout_path, "ab", buffering=0) as stdout_f, open(
            stderr_path, "ab", buffering=0
        ) as stderr_f:
            proc = subprocess.Popen(
                cmd,
                stdout=stdout_f,
                stderr=stderr_f,
                cwd=str(run_dir),
                start_new_session=True,
            )

        return JobFile(pid=proc.pid, started_at=utc_now_iso(), backend=backend, mode="local")

    def cancel(self, job: JobFile) -> None:
        try:
            os.killpg(job.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
