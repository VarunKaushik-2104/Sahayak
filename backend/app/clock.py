"""One place for 'now' and 'today' so tests can pin time."""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from .config import settings

_override: datetime | None = None


def set_now(dt: datetime | None) -> None:
    global _override
    _override = dt


def now() -> datetime:
    """Timezone-aware UTC now."""
    return _override or datetime.now(timezone.utc)


def _tz():
    try:
        return ZoneInfo(settings.timezone)
    except Exception:  # pragma: no cover - tzdata missing
        return timezone.utc


def local_date(dt: datetime) -> date:
    return dt.astimezone(_tz()).date()


def today() -> date:
    return local_date(now())
