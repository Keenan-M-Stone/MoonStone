from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class Backend(ABC):
    name: str

    @abstractmethod
    def run(self, run_dir: Path) -> None:
        raise NotImplementedError
