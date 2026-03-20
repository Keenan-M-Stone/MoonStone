from __future__ import annotations

try:
    from datetime import UTC
except Exception:
    from datetime import timezone as _timezone
    UTC = _timezone.utc
from datetime import datetime


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()
