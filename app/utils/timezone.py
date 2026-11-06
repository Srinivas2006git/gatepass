"""Timezone policy for MRIT.

Database DATETIME values are stored as UTC.  MySQL does not preserve an offset
for DATETIME, so UTCDateTime adds UTC awareness when values are read and removes
only the offset at the database boundary.  Application code always receives
timezone-aware values.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.types import DateTime, TypeDecorator

UTC = timezone.utc
INDIA_TZ = ZoneInfo("Asia/Kolkata")


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        # Legacy values in the existing database follow the established UTC convention.
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def to_india(value: datetime | None) -> datetime | None:
    value = ensure_utc(value)
    return value.astimezone(INDIA_TZ) if value else None


def parse_india_datetime(value: str) -> datetime:
    """Convert an HTML datetime-local value entered in IST to aware UTC."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=INDIA_TZ)
    return parsed.astimezone(UTC)


def format_india(value: datetime | None, pattern: str = "%d/%m/%Y %I:%M %p") -> str:
    local = to_india(value)
    return local.strftime(pattern) if local else "—"


class UTCDateTime(TypeDecorator):
    """A timezone-aware Python datetime backed by a UTC MySQL DATETIME value."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        value = ensure_utc(value)
        return value.replace(tzinfo=None) if value else None

    def process_result_value(self, value, dialect):
        return ensure_utc(value)
