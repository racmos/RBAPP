"""F13-d S1-S2 (AC1): due sets and next run."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.services import riot_sync

MADRID = ZoneInfo('Europe/Madrid')
R = date(2026, 11, 2)
SETS = [('PRE', date(2026, 11, 10)),      # pre_release on 2026-10-25 and 2026-11-02
        ('POST', date(2026, 10, 20)),     # post_release on both days
        ('OLD', date(2025, 1, 1)),        # monthly
        ('NODATE', None),                 # monthly (D-F13-3)
        ('FUTURE', date(2027, 6, 1))]     # none on 2026-10-25


def _due(slot, today):
    return riot_sync.due_sets(SETS, slot, today)


class TestDueSets:
    def test_am_takes_active_windows(self):
        assert _due('am', date(2026, 10, 25)) == [('PRE', 'pre_release'),
                                                 ('POST', 'post_release')]
        assert _due('am', date(2026, 11, 2)) == [('PRE', 'pre_release'),
                                                 ('POST', 'post_release')]

    def test_pm_takes_only_pre_release(self):
        assert _due('pm', date(2026, 10, 25)) == [('PRE', 'pre_release')]
        assert _due('pm', date(2026, 11, 2)) == [('PRE', 'pre_release')]

    def test_monthly_sets_are_due_only_on_the_1st(self):
        first = _due('am', date(2026, 11, 1))
        assert ('OLD', 'monthly') in first and ('NODATE', 'monthly') in first
        mid = _due('am', date(2026, 11, 15))
        assert ('OLD', 'monthly') not in mid and ('NODATE', 'monthly') not in mid
        assert _due('pm', date(2026, 11, 1)) == [('PRE', 'pre_release')]

    def test_none_window_is_never_due(self):
        day = _due('am', date(2026, 10, 25))
        assert ('FUTURE', 'none') not in day
        assert _due('pm', date(2026, 10, 25)) == [('PRE', 'pre_release')]


def _at(day, hour):
    return datetime(day.year, day.month, day.day, hour, 0, tzinfo=MADRID)


class TestNextRun:
    def test_active_window_next_slot_today(self):
        # PRE is pre_release on 2026-10-25: due at both slots.
        assert riot_sync.next_run(date(2026, 11, 10), _at(date(2026, 10, 25), 7)) == \
            _at(date(2026, 10, 25), 8)
        assert riot_sync.next_run(date(2026, 11, 10), _at(date(2026, 10, 25), 9)) == \
            _at(date(2026, 10, 25), 14)
        # POST is post_release: due at am only, so 09:00 waits for tomorrow 08:00.
        assert riot_sync.next_run(date(2026, 10, 20), _at(date(2026, 10, 25), 9)) == \
            _at(date(2026, 10, 26), 8)

    def test_active_window_evening_goes_to_tomorrow(self):
        assert riot_sync.next_run(date(2026, 10, 20), _at(date(2026, 10, 25), 15)) == \
            _at(date(2026, 10, 26), 8)

    def test_none_window_is_r_minus_21_at_8(self):
        assert riot_sync.next_run(date(2027, 6, 1), _at(date(2026, 10, 25), 12)) == \
            _at(date(2027, 5, 11), 8)

    def test_monthly_is_the_next_1st_at_8(self):
        assert riot_sync.next_run(date(2025, 1, 1), _at(date(2026, 10, 25), 12)) == \
            _at(date(2026, 11, 1), 8)
        assert riot_sync.next_run(None, _at(date(2026, 10, 25), 12)) == \
            _at(date(2026, 11, 1), 8)

    def test_monthly_on_the_1st_before_8_is_today(self):
        assert riot_sync.next_run(date(2025, 1, 1), _at(date(2026, 11, 1), 7)) == \
            _at(date(2026, 11, 1), 8)

    def test_monthly_on_the_1st_after_8_is_next_month(self):
        assert riot_sync.next_run(date(2025, 1, 1), _at(date(2026, 11, 1), 9)) == \
            _at(date(2026, 12, 1), 8)

    def test_month_and_year_end(self):
        assert riot_sync.next_run(date(2025, 1, 1), _at(date(2026, 1, 31), 12)) == \
            _at(date(2026, 2, 1), 8)
        assert riot_sync.next_run(date(2025, 1, 1), _at(date(2026, 12, 15), 12)) == \
            _at(date(2027, 1, 1), 8)

    def test_dst_spring_forward_keeps_madrid_offset(self):
        # 2026-03-29 01:30 UTC is 02:30 CEST; the next slot is 08:00 CEST.
        run = riot_sync.next_run(date(2026, 4, 10),
                                 datetime(2026, 3, 29, 1, 30,
                                          tzinfo=ZoneInfo('UTC')).astimezone(MADRID))
        assert run == _at(date(2026, 3, 29), 8)
        assert run.utcoffset().total_seconds() == 7200

    def test_dst_fall_back_keeps_madrid_offset(self):
        # 2026-10-25 00:30 UTC is 02:30 CEST; the set is post_release,
        # so the next slot is 08:00 CET.
        run = riot_sync.next_run(date(2026, 10, 15),
                                 datetime(2026, 10, 25, 0, 30,
                                          tzinfo=ZoneInfo('UTC')).astimezone(MADRID))
        assert run == datetime(2026, 10, 25, 8, 0, tzinfo=MADRID)
        assert run.utcoffset().total_seconds() == 3600
