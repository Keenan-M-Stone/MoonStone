from __future__ import annotations

import json
import time
from pathlib import Path

from .base import Backend


class DummyBackend(Backend):
    name = "dummy"

    def run(self, run_dir: Path) -> None:
        spec_path = run_dir / "spec.json"
        spec = json.loads(spec_path.read_text()) if spec_path.exists() else {}
        time.sleep(0.5)
        out = run_dir / "outputs" / "result.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"ok": True, "backend": "dummy", "spec_keys": list(spec.keys())}))
