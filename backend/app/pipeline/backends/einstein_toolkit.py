"""Einstein Toolkit backend stub for MoonStone.

This backend will eventually drive the Einstein Toolkit (Cactus/Carpet)
for full numerical relativity simulations. The stub validates the spec
and writes a placeholder result.

Integration plan:
  1. Generate Cactus parameter file (.par) from the run spec
  2. Invoke ``simfactory`` or ``cactus_sim`` via subprocess
  3. Stream HDF5 output into the run's outputs/ directory
  4. Parse log for convergence / constraint violations
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import Backend


class EinsteinToolkitBackend(Backend):
    name = "einstein_toolkit"

    def run(self, run_dir: Path) -> None:
        spec_path = run_dir / "spec.json"
        spec = json.loads(spec_path.read_text()) if spec_path.exists() else {}

        # Validate required spec fields
        metric = spec.get("metric", {})
        domain = spec.get("domain", {})

        out = run_dir / "outputs" / "result.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "ok": False,
            "backend": "einstein_toolkit",
            "detail": "Einstein Toolkit integration is not yet implemented. "
                      "This stub validates spec structure and records the request.",
            "metric_type": metric.get("type", "unknown"),
            "domain_keys": list(domain.keys()),
        }, indent=2))


class DendroGRBackend(Backend):
    """Stub for Dendro-GR adaptive mesh refinement."""
    name = "dendro_gr"

    def run(self, run_dir: Path) -> None:
        out = run_dir / "outputs" / "result.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "ok": False,
            "backend": "dendro_gr",
            "detail": "Dendro-GR backend not yet implemented.",
        }, indent=2))


class GRTresnaBackend(Backend):
    """Stub for GRTresna initial data solver."""
    name = "grtresna"

    def run(self, run_dir: Path) -> None:
        out = run_dir / "outputs" / "result.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "ok": False,
            "backend": "grtresna",
            "detail": "GRTresna backend not yet implemented.",
        }, indent=2))


class GR1DBackend(Backend):
    """Stub for GR1D spherically-symmetric core-collapse."""
    name = "gr1d"

    def run(self, run_dir: Path) -> None:
        out = run_dir / "outputs" / "result.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "ok": False,
            "backend": "gr1d",
            "detail": "GR1D backend not yet implemented.",
        }, indent=2))
