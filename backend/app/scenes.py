from fastapi import APIRouter
from pathlib import Path
import uuid
import json
from typing import Dict, Any

router = APIRouter()
SCENE_DIR = Path(__file__).resolve().parents[1] / 'scenes'
SCENE_DIR.mkdir(parents=True, exist_ok=True)


def _extract_scene_id(body: Dict[str, Any]) -> str | None:
    # Legacy payloads stored an id at the root.
    root_id = body.get('id')
    if isinstance(root_id, str) and root_id:
        return root_id

    # New convention: stardust.bundle with MoonStone scene under manifest.extra.moonstone.scene
    try:
        scene_id = (
            body.get('manifest', {})
            .get('extra', {})
            .get('moonstone', {})
            .get('scene', {})
            .get('id')
        )
        if isinstance(scene_id, str) and scene_id:
            return scene_id
    except Exception:
        pass

    return None

@router.post('/scene')
async def save_scene(body: Dict[str, Any]):
    sid = _extract_scene_id(body) or str(uuid.uuid4())
    p = SCENE_DIR / f"{sid}.json"
    with p.open('w') as fh:
        json.dump(body, fh)
    return {'id': sid}

@router.get('/scene/{scene_id}')
async def load_scene(scene_id: str):
    p = SCENE_DIR / f"{scene_id}.json"
    if not p.exists():
        return {'error': 'not found'}
    with p.open('r') as fh:
        return json.load(fh)

@router.get('/scenes')
async def list_scenes():
    out = []
    for p in SCENE_DIR.glob('*.json'):
        out.append(p.stem)
    return {'scenes': out}
