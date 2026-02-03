"""Simple persistent benchmark store (JSON) for the backend.

Stores benchmark entries in a small JSON file and provides aggregation
helpers for runtime predictions.
"""
import json
import os
from typing import Dict, Any, List

STORE_PATH = os.path.join(os.path.dirname(__file__), '..', 'bench_store.json')


def _read_store() -> List[Dict[str, Any]]:
    try:
        with open(STORE_PATH, 'r') as f:
            return json.load(f)
    except Exception:
        return []


def _write_store(data: List[Dict[str, Any]]):
    with open(STORE_PATH, 'w') as f:
        json.dump(data, f)


def add_entry(entry: Dict[str, Any]):
    data = _read_store()
    data.append(entry)
    _write_store(data)


def aggregate_by_solver():
    data = _read_store()
    agg: Dict[str, Dict[str, Any]] = {}
    counts: Dict[str, int] = {}
    for e in data:
        s = e.get('solver')
        if not s:
            continue
        if s not in agg:
            agg[s] = {'mean_per_ray': 0.0}
            counts[s] = 0
        agg[s]['mean_per_ray'] += e.get('mean_sec', 0.0)
        counts[s] += 1
    for s in agg.keys():
        agg[s]['mean_per_ray'] = agg[s]['mean_per_ray'] / max(1, counts[s])
    return agg
