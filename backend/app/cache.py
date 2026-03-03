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
import os
import time

CACHE_DIR = Path(__file__).resolve().parents[1] / 'cache'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Simple index in memory for this process
_index = {}

# Throttle prune scans (which can be O(n) in number of cache files).
_LAST_PRUNE_TS = 0.0
_PRUNE_MIN_INTERVAL_SEC = float(os.environ.get('MOONSTONE_TRACE_CACHE_PRUNE_INTERVAL_SEC', '10'))


def _env_int(name: str, default: int) -> int:
    try:
        v = int(os.environ.get(name, str(default)))
        return v
    except Exception:
        return int(default)


def _cache_limits():
    # Automatic pruning defaults (can be overridden by env vars).
    # Keep fairly conservative defaults to avoid surprise disk growth.
    max_files = _env_int('MOONSTONE_TRACE_CACHE_MAX_FILES', 4000)
    max_bytes = _env_int('MOONSTONE_TRACE_CACHE_MAX_BYTES', 750_000_000)
    return max_files, max_bytes


def _cache_stats():
    files = []
    total = 0
    for p in CACHE_DIR.glob('*.pkl'):
        try:
            st = p.stat()
            files.append((p, st.st_mtime, st.st_size))
            total += int(st.st_size)
        except Exception:
            continue
    files.sort(key=lambda x: x[1])
    return files, total


def cache_status() -> dict:
    max_files, max_bytes = _cache_limits()
    files, total = _cache_stats()
    return {
        'status': 'ok',
        'cache_dir': str(CACHE_DIR),
        'files': len(files),
        'bytes': int(total),
        'max_files': int(max_files),
        'max_bytes': int(max_bytes),
    }


def cache_prune(*, max_files: int | None = None, max_bytes: int | None = None) -> dict:
    mf, mb = _cache_limits()
    max_files = int(mf if max_files is None else max_files)
    max_bytes = int(mb if max_bytes is None else max_bytes)

    files, total = _cache_stats()
    removed = 0
    removed_bytes = 0

    def needs_prune() -> bool:
        return (max_files > 0 and len(files) > max_files) or (max_bytes > 0 and total > max_bytes)

    while files and needs_prune():
        p, _, sz = files.pop(0)
        try:
            p.unlink(missing_ok=True)
            removed += 1
            removed_bytes += int(sz)
            total -= int(sz)
        except Exception:
            continue

    summary = {
        'status': 'ok',
        'removed': removed,
        'removed_bytes': removed_bytes,
        'remaining_files': len(files),
        'remaining_bytes': total,
        'max_files': max_files,
        'max_bytes': max_bytes,
    }

    try:
        global _LAST_PRUNE_TS
        _LAST_PRUNE_TS = time.time()
    except Exception:
        pass

    global _LAST_PRUNE_SUMMARY
    _LAST_PRUNE_SUMMARY = summary
    return summary


_LAST_PRUNE_SUMMARY: dict | None = None


def cache_last_prune() -> dict | None:
    return _LAST_PRUNE_SUMMARY


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
                # Touch to approximate LRU (mtime-based) pruning.
                try:
                    now = time.time()
                    os.utime(p, (now, now))
                except Exception:
                    pass
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
    # Automatic pruning (best-effort).
    try:
        global _LAST_PRUNE_TS
        now = time.time()
        if (now - _LAST_PRUNE_TS) >= _PRUNE_MIN_INTERVAL_SEC:
            cache_prune()
            _LAST_PRUNE_TS = now
    except Exception:
        pass
    return key


def cache_key(req: dict) -> str:
    return _serialize_key(req)
