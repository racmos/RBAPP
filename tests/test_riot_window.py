"""F13-c S2 (AC1): the sync window calculator and the Madrid local date."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.services import riot_sync

MADRID = ZoneInfo('Europe/Madrid')
R = date(2026, 11, 2)


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


@pytest.mark.parametrize('today, expected', [
    (date(2026, 10, 11), 'none'),        # R-22
    (date(2026, 10, 12), 'pre_release'),  # R-21, first active day
    (date(2026, 11, 1), 'pre_release'),   # R-1
    (R, 'post_release'),                  # R
    (date(2026, 11, 15), 'post_release'),  # R+13, last active day
    (date(2026, 11, 16), 'monthly'),       # R+14
    (date(2027, 5, 5), 'monthly'),
])
def test_window_boundaries(today, expected):
    assert riot_sync.window_for(R, today) == expected


def test_a_set_without_a_date_is_always_monthly():
    assert riot_sync.window_for(None, date(2026, 10, 20)) == 'monthly'  # D-F13-3


@pytest.mark.parametrize('now, expected', [
    (utc(2026, 1, 15, 22, 59), date(2026, 1, 15)),   # CET (+1)
    (utc(2026, 1, 15, 23, 0), date(2026, 1, 16)),
    (utc(2026, 7, 15, 21, 59), date(2026, 7, 15)),    # CEST (+2)
    (utc(2026, 7, 15, 22, 0), date(2026, 7, 16)),
    (utc(2026, 3, 29, 23, 30), date(2026, 3, 30)),   # spring-forward day
    (utc(2026, 10, 25, 0, 30), date(2026, 10, 25)),  # fall-back day, before transition
    (utc(2026, 10, 25, 1, 30), date(2026, 10, 25)),  # fall-back day, after transition
])
def test_today_is_the_madrid_local_date(now, expected):
    assert riot_sync.today_madrid(now) == expected


def test_naive_datetimes_are_read_as_utc():
    assert riot_sync.today_madrid(datetime(2026, 7, 15, 22, 30)) == date(2026, 7, 16)
