"""F4-c S2 (AC1): `take_snapshots` stores one value snapshot per user with a collection,
priced by the same code as `GET /collection` (F3-b)."""
from datetime import date

import pytest
import sqlalchemy as sa

from app import db
from app.models import RbValueSnapshot, User
from app.services.collection_read import list_collection
from app.services.snapshots import take_snapshots
from app.schemas.validators import CollectionListQuery
from tests.collection_read_helpers import line, seed_catalog, seed_lines

DAY = date(2030, 1, 1)


@pytest.fixture
def two_users(app, make_user):
    ana = make_user('testuser')
    bo = make_user('otheruser')
    make_user('lonely')            # no collection lines
    with app.app_context():
        seed_catalog()
        seed_lines()
    return ana, bo


def stored():
    db.session.expire_all()
    return {row.rbvsn_user_id: row for row in db.session.execute(
        sa.select(RbValueSnapshot)).scalars()}


def test_values_for_priced_unpriced_and_foil_lines(app, two_users):
    ana, bo = two_users
    result = take_snapshots(DAY)
    rows = stored()
    mine = rows[ana.id]
    # OGN/1 10 x4 + 10 x2, foil 30 x1, OGN/2 5 x3, OGN/79 20 x1; SFD lines have no price
    assert (float(mine.rbvsn_value), float(mine.rbvsn_cost)) == (125.0, 77.0)
    assert (mine.rbvsn_qty, mine.rbvsn_unique, mine.rbvsn_unpriced) == (14, 5, 2)
    assert mine.rbvsn_date == DAY
    assert result == {'date': '2030-01-01', 'users': 2, 'rows': 2, 'total_value': 215.0,
                      'products_value': 0.0}


def test_same_numbers_as_the_collection_totals(app, two_users):
    ana, bo = two_users
    take_snapshots(DAY)
    row = stored()[ana.id]
    totals = list_collection(CollectionListQuery(), ana)['meta']['totals']
    assert float(row.rbvsn_value) == totals['value']
    assert float(row.rbvsn_cost) == totals['cost']
    assert (row.rbvsn_qty, row.rbvsn_unique) == (totals['qty'], totals['unique'])


def test_cost_is_null_when_no_line_has_a_purchase_price(app, two_users):
    ana, bo = two_users
    take_snapshots(DAY)
    other = stored()[bo.id]
    assert other.rbvsn_cost is None
    assert (float(other.rbvsn_value), other.rbvsn_qty, other.rbvsn_unique,
            other.rbvsn_unpriced) == (90.0, 9, 1, 0)


def test_users_without_lines_get_no_row(app, two_users):
    take_snapshots(DAY)
    assert len(stored()) == 2
    assert User.query.filter_by(username='lonely').one().id not in stored()


def test_a_second_run_the_same_day_replaces_the_values(app, two_users):
    ana, bo = two_users
    take_snapshots(DAY)
    db.session.add(line('2', 1, condition='MT'))
    db.session.commit()
    result = take_snapshots(DAY)
    rows = stored()
    assert len(rows) == 2
    assert (float(rows[ana.id].rbvsn_value), rows[ana.id].rbvsn_qty) == (130.0, 15)
    assert result['rows'] == 2 and result['total_value'] == 220.0


def test_another_day_adds_a_row_and_keeps_the_history(app, two_users):
    ana, bo = two_users
    take_snapshots(DAY)
    take_snapshots(date(2030, 1, 2))
    count = db.session.execute(sa.select(sa.func.count()).select_from(RbValueSnapshot)).scalar()
    assert count == 4


def test_nobody_has_a_collection(app, make_user):
    make_user('lonely')
    assert take_snapshots(DAY) == {'date': '2030-01-01', 'users': 0, 'rows': 0,
                                   'total_value': 0.0, 'products_value': 0.0}


def test_a_bounded_number_of_queries(app, two_users):
    from sqlalchemy import event
    statements = []

    def listener(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db.engine, 'before_cursor_execute', listener)
    try:
        take_snapshots(DAY)
    finally:
        event.remove(db.engine, 'before_cursor_execute', listener)
    selects = [s for s in statements if s.lstrip().upper().startswith('SELECT')]
    assert len(selects) <= 8      # not one per user
