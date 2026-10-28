"""Seed helpers for the products read API tests (F14-b)."""
from datetime import date

from sqlalchemy import event

from app import db
from app.models import RbProducts, RbSet, RbcmPrice


def add_sets():
    db.session.add_all([
        RbSet(rbset_id='OGN', rbset_name='Origins', rbset_outdat=date(2025, 10, 31)),
        RbSet(rbset_id='SFD', rbset_name='Spiritforged', rbset_outdat=date(2025, 11, 30)),
        # Alphabetically first, released last: the set facet follows the release order.
        RbSet(rbset_id='ARC', rbset_name='Arcane', rbset_outdat=date(2026, 6, 1)),
    ])


def add_product(product_id, name, *, kind='booster', set_id='OGN', category='Boosters',
                listed=True, hidden=False, type_='nonsingle', description=None):
    db.session.add(RbProducts(
        rbpdt_id_product=product_id, rbpdt_name=name, rbpdt_kind=kind, rbpdt_id_set=set_id,
        rbpdt_category=category, rbpdt_listed=listed, rbpdt_hidden=hidden, rbpdt_type=type_,
        rbpdt_description=description))


def add_price(product_id, day, *, avg7=None, trend=None, low=None, avg30=None, **extra):
    db.session.add(RbcmPrice(rbprc_date=day, rbprc_id_product=product_id, rbprc_avg7=avg7,
                             rbprc_trend=trend, rbprc_low=low, rbprc_avg30=avg30, **extra))


def count_statements(app, fn):
    """`(result of fn(), number of SQL statements it ran)`."""
    statements = []

    def listener(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    with app.app_context():
        event.listen(db.engine, 'before_cursor_execute', listener)
        try:
            result = fn()
        finally:
            event.remove(db.engine, 'before_cursor_execute', listener)
    return result, len(statements)
