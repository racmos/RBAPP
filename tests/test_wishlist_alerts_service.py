"""F4-g-2: `app/services/wishlist_alerts.py::raise_alerts`, the daily wishlist price alerts.

Catalog and prices from `tests/wishlist_helpers.py` (price date 2026-10-20): OGN/1 non-foil 10,
foil 30; OGN/1a 50; SFD/5 4 (the cheapest "Alpha Fury"); OGN/2 unpriced; OGN/79 20.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy import event

from app import db
from app.models import RbcmPrice, RbWishlist, RbWishlistAlert, RbWishlistLine
from app.services import wishlist_alerts
from app.services.bans import name_key
from tests.wishlist_helpers import seed_catalog, seed_fillers, user_id

DAY = date(2026, 10, 20)


@pytest.fixture
def seeded(app, make_user, frozen_clock):
    make_user('testuser')
    make_user('otheruser')
    seed_catalog()
    return frozen_clock


def make_list(user='testuser', name='Wishlist', position=1, default=None):
    row = RbWishlist(rbwls_user_id=user_id(user), rbwls_name=name, rbwls_position=position,
                     rbwls_is_default=position == 1 if default is None else default)
    db.session.add(row)
    db.session.commit()
    return row.rbwls_id


CARD_NAMES = {'1': 'Alpha Fury', '1a': 'Alpha Fury', '5': 'Alpha Fury', '2': 'Beta Calm',
              '79': 'Jinx, Loose Cannon'}


def make_line(list_id, card_id=None, *, set_id='OGN', name=None, foil='any', max_price=None):
    """A printing line (`card_id`) or, with `name`, a by-name line."""
    shown = name or CARD_NAMES.get(card_id, f'Filler {card_id}')
    row = RbWishlistLine(rbwsl_list_id=list_id, rbwsl_name_key=name_key(shown),
                         rbwsl_name=shown, rbwsl_rbset_id=None if name else set_id,
                         rbwsl_rbcar_id=None if name else card_id, rbwsl_foil=foil,
                         rbwsl_qty=1,
                         rbwsl_max_price=None if max_price is None else Decimal(str(max_price)))
    db.session.add(row)
    db.session.commit()
    return row


def alerts():
    db.session.expire_all()
    rows = [(row.rbwal_user_id, row.rbwal_name, row.rbwal_rbset_id, row.rbwal_rbcar_id,
             float(row.rbwal_price), float(row.rbwal_max_price), row.rbwal_price_date)
            for row in db.session.execute(sa.select(RbWishlistAlert)).scalars()]
    return sorted(rows, key=lambda r: (r[0], r[1], r[2] or '', r[3] or '', r[6]))


def me():
    return user_id('testuser')


class TestThreshold:
    @pytest.mark.parametrize('max_price, raised', [(9.99, False), (10, True), (12, True)])
    def test_at_or_below_the_max_price_alerts(self, seeded, max_price, raised):
        make_line(make_list(), '1', foil='N', max_price=max_price)
        result = wishlist_alerts.raise_alerts()
        expected = [(me(), 'Alpha Fury', 'OGN', '1', 10.0, float(max_price), DAY)] if raised \
            else []
        assert alerts() == expected
        assert result == {'price_date': '2026-10-20', 'lines_checked': 1, 'cards_checked': 1,
                          'alerts_created': len(expected), 'skipped_no_price': 0}

    def test_a_line_without_a_max_price_never_alerts(self, seeded):
        make_line(make_list(), '1', foil='N')
        result = wishlist_alerts.raise_alerts()
        assert alerts() == []
        assert result['lines_checked'] == 0 and result['cards_checked'] == 0

    def test_the_foil_wish_picks_the_price(self, seeded):
        wishlist = make_list()
        make_line(wishlist, '1', foil='S', max_price=25)        # foil 30: not reached
        make_line(make_list(name='Other', position=2), '1', foil='any', max_price=10)
        wishlist_alerts.raise_alerts()
        assert alerts() == [(me(), 'Alpha Fury', 'OGN', '1', 10.0, 10.0, DAY)]

    def test_the_foil_price_reached(self, seeded):
        make_line(make_list(), '1', foil='S', max_price=30)
        wishlist_alerts.raise_alerts()
        assert alerts() == [(me(), 'Alpha Fury', 'OGN', '1', 30.0, 30.0, DAY)]

    def test_a_card_without_a_price_is_skipped(self, seeded):
        make_line(make_list(), '2', max_price=100)
        result = wishlist_alerts.raise_alerts()
        assert alerts() == []
        assert result == {'price_date': '2026-10-20', 'lines_checked': 1, 'cards_checked': 1,
                          'alerts_created': 0, 'skipped_no_price': 1}

    def test_a_printing_that_left_the_catalog_is_skipped(self, seeded):
        make_line(make_list(), '999', max_price=100)
        result = wishlist_alerts.raise_alerts()
        assert alerts() == [] and result['skipped_no_price'] == 1


class TestOnePerUserCardAndDay:
    def test_the_same_card_in_two_lists_raises_one_alert(self, seeded):
        make_line(make_list(), '1', foil='N', max_price=12)
        make_line(make_list(name='Trades', position=2), '1', foil='N', max_price=11)
        result = wishlist_alerts.raise_alerts()
        # The lowest max price that was met is the threshold stored.
        assert alerts() == [(me(), 'Alpha Fury', 'OGN', '1', 10.0, 11.0, DAY)]
        assert (result['lines_checked'], result['cards_checked'],
                result['alerts_created']) == (2, 1, 1)

    def test_any_line_reached_alerts_with_the_lowest_max_that_was_met(self, seeded):
        make_line(make_list(), '1', foil='N', max_price=12)
        make_line(make_list(name='Trades', position=2), '1', foil='N', max_price=9)
        wishlist_alerts.raise_alerts()
        assert alerts() == [(me(), 'Alpha Fury', 'OGN', '1', 10.0, 12.0, DAY)]

    def test_two_users_are_independent(self, seeded):
        make_line(make_list(), '1', foil='N', max_price=10)
        make_line(make_list('otheruser'), '1', foil='N', max_price=5)
        make_line(make_list('otheruser', 'Second', 2), '79', max_price=20)
        wishlist_alerts.raise_alerts()
        other = user_id('otheruser')
        assert alerts() == [(me(), 'Alpha Fury', 'OGN', '1', 10.0, 10.0, DAY),
                            (other, 'Jinx, Loose Cannon', 'OGN', '79', 20.0, 20.0, DAY)]

    def test_a_by_name_line_takes_the_cheapest_printing_and_alerts_apart(self, seeded):
        wishlist = make_list()
        make_line(wishlist, name='Alpha Fury', max_price=4)          # SFD/5 at 4
        make_line(wishlist, '1', foil='N', max_price=10)              # its own alert
        result = wishlist_alerts.raise_alerts()
        assert alerts() == [(me(), 'Alpha Fury', None, None, 4.0, 4.0, DAY),
                            (me(), 'Alpha Fury', 'OGN', '1', 10.0, 10.0, DAY)]
        assert result['cards_checked'] == 2

    def test_a_by_name_line_above_the_cheapest_printing_does_not_alert(self, seeded):
        make_line(make_list(), name='Alpha Fury', max_price=3.99)
        wishlist_alerts.raise_alerts()
        assert alerts() == []


class TestDays:
    def test_a_rerun_for_the_same_price_date_creates_nothing(self, seeded):
        make_line(make_list(), '1', foil='N', max_price=10)
        first = wishlist_alerts.raise_alerts()
        seeded.advance(minutes=60)
        second = wishlist_alerts.raise_alerts()
        assert first['alerts_created'] == 1 and second['alerts_created'] == 0
        assert len(alerts()) == 1

    def test_a_rerun_after_a_new_alert_line_only_adds_the_new_card(self, seeded):
        wishlist = make_list()
        make_line(wishlist, '1', foil='N', max_price=10)
        wishlist_alerts.raise_alerts()
        make_line(wishlist, '79', max_price=20)
        assert wishlist_alerts.raise_alerts()['alerts_created'] == 1
        assert [row[3] for row in alerts()] == ['1', '79']

    def test_the_next_price_date_alerts_again_while_still_below(self, seeded):
        make_line(make_list(), '1', foil='N', max_price=10)
        wishlist_alerts.raise_alerts()
        db.session.add(RbcmPrice(rbprc_date='20261021', rbprc_id_product=1, rbprc_avg7=9.5))
        db.session.commit()
        result = wishlist_alerts.raise_alerts()
        assert result['price_date'] == '2026-10-21' and result['alerts_created'] == 1
        assert alerts() == [(me(), 'Alpha Fury', 'OGN', '1', 10.0, 10.0, DAY),
                            (me(), 'Alpha Fury', 'OGN', '1', 9.5, 10.0, date(2026, 10, 21))]

    def test_an_explicit_price_date_is_used(self, seeded):
        make_line(make_list(), '1', foil='N', max_price=10)
        assert wishlist_alerts.raise_alerts(date(2026, 10, 22))['price_date'] == '2026-10-22'
        assert alerts()[0][6] == date(2026, 10, 22)

    def test_a_deleted_line_or_a_cleared_max_price_stops_the_alerts(self, seeded):
        wishlist = make_list()
        line = make_line(wishlist, '1', foil='N', max_price=10)
        other = make_line(wishlist, '79', max_price=20)
        wishlist_alerts.raise_alerts()
        db.session.delete(line)
        other.rbwsl_max_price = None
        db.session.add(RbcmPrice(rbprc_date='20261021', rbprc_id_product=1, rbprc_avg7=9))
        db.session.commit()
        result = wishlist_alerts.raise_alerts()
        assert result['alerts_created'] == 0 and result['lines_checked'] == 0
        assert len(alerts()) == 2

    def test_alerts_survive_a_deleted_list(self, seeded):
        second = make_list(name='Trades', position=2)
        make_line(second, '1', foil='N', max_price=10)
        wishlist_alerts.raise_alerts()
        db.session.execute(sa.delete(RbWishlistLine))
        db.session.execute(sa.delete(RbWishlist).where(RbWishlist.rbwls_id == second))
        db.session.commit()
        assert len(alerts()) == 1

    def test_an_alert_stores_when_it_was_raised_and_starts_unread(self, seeded):
        make_line(make_list(), '1', foil='N', max_price=10)
        wishlist_alerts.raise_alerts()
        row = db.session.execute(sa.select(RbWishlistAlert)).scalar_one()
        assert row.rbwal_created_at == datetime(2030, 1, 1, 12, 0)
        assert row.rbwal_read_at is None
        assert row.rbwal_name_key == name_key('Alpha Fury')

    def test_no_price_load_at_all_raises(self, app, make_user):
        make_user('testuser')
        with pytest.raises(wishlist_alerts.NoPrices):
            wishlist_alerts.raise_alerts()


def _statements(call):
    counted = []

    def before(conn, cursor, statement, parameters, context, executemany):
        counted.append(statement)

    event.listen(db.engine, 'before_cursor_execute', before)
    try:
        call()
    finally:
        event.remove(db.engine, 'before_cursor_execute', before)
    return len(counted)


def test_the_number_of_statements_does_not_grow_with_the_lines(seeded):
    wishlist = make_list()
    make_line(wishlist, '1', foil='N', max_price=10)
    few = _statements(wishlist_alerts.raise_alerts)
    db.session.execute(sa.delete(RbWishlistAlert))
    db.session.commit()
    other = make_list('otheruser')
    for card_id in seed_fillers(8):
        make_line(other, card_id, max_price=1)
    make_line(other, name='Alpha Fury', max_price=50)
    make_line(other, '79', max_price=20)
    make_line(make_list(name='Trades', position=2), '1', foil='S', max_price=40)
    many = _statements(wishlist_alerts.raise_alerts)
    assert few == many
    # price date, lines, cards, price mapping, prices, the day's alerts, insert
    assert many == 7


def test_many_alerts_are_inserted_in_chunks(seeded, monkeypatch):
    monkeypatch.setattr(wishlist_alerts, 'INSERT_CHUNK', 2)
    wishlist = make_list()
    make_line(wishlist, '1', foil='N', max_price=10)
    make_line(wishlist, '79', max_price=20)
    make_line(wishlist, name='Alpha Fury', max_price=5)
    make_line(make_list('otheruser'), '1', foil='N', max_price=11)
    inserts = []

    def before(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith('INSERT'):
            inserts.append(statement)

    event.listen(db.engine, 'before_cursor_execute', before)
    try:
        assert wishlist_alerts.raise_alerts()['alerts_created'] == 4
    finally:
        event.remove(db.engine, 'before_cursor_execute', before)
    assert len(inserts) == 2
    assert len(alerts()) == 4
