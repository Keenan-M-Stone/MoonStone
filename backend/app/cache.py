"""Simple disk-backed cache for trace results.

Design goals:
- Deterministic key derived from trace request properties (source, directions, metric, params)
- Fast lookup (in-memory index) with on-disk storage (HDF5 or pickle)
- Small footprint POC for interactive mode
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any, Optional
import pickle

CACHE_DIR = Path(__file__).resolve().parents[1] / 'cache'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Simple index in memory for this process
_index = {}


def _serialize_key(req: dict) -> str:
    # create a stable, sorted JSON representation
    s = json.dumps(req, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(s.encode('utf8')).hexdigest()


def cache_get(req: dict) -> Optional[Any]:
    key = _serialize_key(req)
    if key in _index:
        p = CACHE_DIR / f"{key}.pkl"
        if p.exists():
            try:
                with p.open('rb') as fh:
                    return pickle.load(fh)
            except Exception:
                return None
    return None


def cache_set(req: dict, value: Any) -> str:
    key = _serialize_key(req)
    p = CACHE_DIR / f"{key}.pkl"
    with p.open('wb') as fh:
        pickle.dump(value, fh)
    _index[key] = str(p)
    return key


def cache_key(req: dict) -> str:
    return _serialize_key(req)
