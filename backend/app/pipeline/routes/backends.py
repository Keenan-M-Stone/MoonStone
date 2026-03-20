from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["backends"])

# GR backend capabilities registry
CAPABILITIES: dict[str, dict[str, Any]] = {
    "dummy": {
        "name": "dummy",
        "label": "Dummy (no-op)",
        "supports_translation": False,
        "capabilities": {},
    },
    "einstein_toolkit": {
        "name": "einstein_toolkit",
        "label": "Einstein Toolkit (Cactus/Carpet)",
        "supports_translation": False,
        "capabilities": {},
        "metric_types": ["schwarzschild", "kerr", "brill-lindquist", "custom"],
        "initial_data": ["puncture", "tov", "brill-wave"],
        "evolution_thorns": ["McLachlan", "LeanBSSN"],
    },
    "dendro_gr": {
        "name": "dendro_gr",
        "label": "Dendro-GR (AMR)",
        "supports_translation": False,
        "capabilities": {},
    },
    "grtresna": {
        "name": "grtresna",
        "label": "GRTresna (initial data)",
        "supports_translation": False,
        "capabilities": {},
    },
    "gr1d": {
        "name": "gr1d",
        "label": "GR1D (spherical collapse)",
        "supports_translation": False,
        "capabilities": {},
    },
}


@router.get("/backends")
def list_backends() -> list[dict[str, Any]]:
    return [
        {"name": v["name"], "label": v.get("label", v["name"])}
        for v in CAPABILITIES.values()
    ]


@router.get("/backends/{name}")
def get_backend_capabilities(name: str) -> dict[str, Any]:
    key = name.strip().lower()
    if key not in CAPABILITIES:
        raise HTTPException(status_code=404, detail="Unknown backend")
    return CAPABILITIES[key]


@router.post("/backends/{name}/translate")
def translate_backend(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    key = name.strip().lower()
    if key not in CAPABILITIES:
        raise HTTPException(status_code=404, detail="Unknown backend")
    return {
        "backend": key,
        "translated": None,
        "warnings": ["No server-side translator available for this backend"],
    }
