from __future__ import annotations

from typing import Any

from .dummy import DummyBackend
from .einstein_toolkit import (
    EinsteinToolkitBackend,
    DendroGRBackend,
    GRTresnaBackend,
    GR1DBackend,
)

_AVAILABLE: dict[str, Any] = {
    "dummy": DummyBackend,
    "einstein_toolkit": EinsteinToolkitBackend,
    "dendro_gr": DendroGRBackend,
    "grtresna": GRTresnaBackend,
    "gr1d": GR1DBackend,
}


def get_backend(name: str):
    key = name.strip().lower()
    if key not in _AVAILABLE:
        raise KeyError(f"Unknown backend: {name}")
    be = _AVAILABLE[key]()
    try:
        be.name = key
    except Exception:
        pass
    return be


def list_backends() -> list[str]:
    return list(_AVAILABLE.keys())
