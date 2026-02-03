from fastapi import APIRouter
from pathlib import Path
import uuid
import json
from typing import Dict, Any

router = APIRouter()
SCENE_DIR = Path(__file__).resolve().parents[1] / 'scenes'
SCENE_DIR.mkdir(parents=True, exist_ok=True)

@router.post('/scene')
async def save_scene(body: Dict[str, Any]):
    sid = body.get('id') or str(uuid.uuid4())
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
