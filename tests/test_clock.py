"""Injectable clock (task 4.3, D17).

Services read time through the module (`clock.utcnow()`), so a test can freeze
or advance it with `monkeypatch.setattr(clock, 'utcnow', ...)`.
"""
from datetime import datetime, timedelta, timezone

from app.utils import clock


def consumer():
    """Stands in for a service module: calls the clock through the module."""
    return clock.utcnow() + timedelta(minutes=15)


class TestUtcNow:
    def test_is_naive_utc(self):
        now = clock.utcnow()
        assert now.tzinfo is None
        wall = datetime.now(timezone.utc).replace(tzinfo=None)
        assert abs((wall - now).total_seconds()) < 5

    def test_patching_the_module_attribute_is_honored(self, monkeypatch):
        t0 = datetime(2030, 1, 1, 12, 0, 0)
        monkeypatch.setattr(clock, 'utcnow', lambda: t0)
        assert consumer() == t0 + timedelta(minutes=15)

    def test_a_later_patch_moves_time_forward(self, monkeypatch):
        t0 = datetime(2030, 1, 1, 12, 0, 0)
        monkeypatch.setattr(clock, 'utcnow', lambda: t0)
        first = consumer()
        monkeypatch.setattr(clock, 'utcnow', lambda: t0 + timedelta(hours=2))
        assert consumer() - first == timedelta(hours=2)
