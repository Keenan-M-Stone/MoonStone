from pydantic import BaseModel
from typing import List, Optional, Literal, Any

class TracePoint(BaseModel):
    x: float
    y: float
    z: float

class TraceResult(BaseModel):
    id: str
    points: List[TracePoint]
    meta: Optional[Any]

class TraceRequest(BaseModel):
    source: TracePoint
    directions: List[TracePoint]
    metric: Optional[dict] = None
    params: Optional[dict] = None
