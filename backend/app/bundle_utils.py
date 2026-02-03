"""Utility helpers for MoonStone bundle import/export (.moonstone.bundles)

Simple JSON loader/saver for simulation bundles.
"""
import json
from pathlib import Path
from typing import Any, Dict

# place bundles at repository root `.moonstone.bundles`
BUNDLE_DIR = Path(__file__).resolve().parents[2] / '.moonstone.bundles'


def save_bundle(name: str, data: Dict[str, Any]):
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    path = BUNDLE_DIR / f"{name}.json"
    with open(path, 'w') as fh:
        json.dump(data, fh, indent=2)
    return str(path)


def load_bundle(name: str) -> Dict[str, Any]:
    path = BUNDLE_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Bundle not found: {path}")
    with open(path, 'r') as fh:
        return json.load(fh)


def list_bundles():
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    return [p.name for p in BUNDLE_DIR.glob('*.json')]
