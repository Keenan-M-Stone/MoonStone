"""Centralized resource limits and concurrency control for MoonStone.

All safety caps and concurrency gates live here so they can be tuned from
one place (or overridden via environment variables) instead of being
scattered across traces.py, metric_fields_api.py, etc.
"""
import asyncio
import os


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# --- Trace limits ---
MAX_DIRECTIONS: int = _env_int("MOONSTONE_MAX_DIRECTIONS", 2048)
MAX_NPOINTS: int = _env_int("MOONSTONE_MAX_NPOINTS", 10000)
MAX_STORED_TRACES: int = _env_int("MOONSTONE_MAX_STORED_TRACES", 200)

# --- Metric field limits ---
MAX_METRIC_GRID_POINTS: int = _env_int("MOONSTONE_MAX_METRIC_GRID_POINTS", 4_000_000)

# --- Concurrency gates ---
#  Limit concurrent expensive computations so we don't starve the event loop
#  or exhaust memory when multiple users hit the API simultaneously.
TRACE_COMPUTE_SEMAPHORE: asyncio.Semaphore = asyncio.Semaphore(
    _env_int("MOONSTONE_TRACE_CONCURRENCY", 4)
)
METRIC_COMPUTE_SEMAPHORE: asyncio.Semaphore = asyncio.Semaphore(
    _env_int("MOONSTONE_METRIC_CONCURRENCY", 2)
)
