"""Injectable clock (D17).

`utcnow()` returns NAIVE UTC, the same convention as the `timestamp without
time zone` columns. Services must call it through the module
(`from app.utils import clock; clock.utcnow()`), never import the function by
name, so tests can freeze time with
`monkeypatch.setattr(clock, 'utcnow', lambda: ...)`.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current UTC time as a naive datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
