"""Seed helpers for the products API tests (F14-b, F14-c, F14-d)."""
from datetime import date, datetime

from sqlalchemy import event

from app import db
from app.models import RbProducts, RbSet, RbUserProduct, RbcmPrice, User


def add_sets():
    db.session.add_all([
        RbSet(rbset_id='OGN', rbset_name='Origins', rbset_outdat=date(2025, 10, 31)),
        RbSet(rbset_id='SFD', rbset_name='Spiritforged', rbset_outdat=date(2025, 11, 30)),
        # Alphabetically first, released last: the set facet follows the release order.
        RbSet(rbset_id='ARC', rbset_name='Arcane', rbset_outdat=date(2026, 6, 1)),
    ])


def add_product(product_id, name, *, kind='booster', set_id='OGN', category='Boosters',
                listed=True, hidden=False, type_='nonsingle', description=None, image=None,
                kind_locked=False, set_locked=False, updated_at=None):
    db.session.add(RbProducts(
        rbpdt_id_product=product_id, rbpdt_name=name, rbpdt_kind=kind, rbpdt_id_set=set_id,
        rbpdt_category=category, rbpdt_listed=listed, rbpdt_hidden=hidden, rbpdt_type=type_,
        rbpdt_description=description, rbpdt_image=image, rbpdt_kind_locked=kind_locked,
        rbpdt_set_locked=set_locked, rbpdt_updated_at=updated_at))


def add_price(product_id, day, *, avg7=None, trend=None, low=None, avg30=None, **extra):
    db.session.add(RbcmPrice(rbprc_date=day, rbprc_id_product=product_id, rbprc_avg7=avg7,
                             rbprc_trend=trend, rbprc_low=low, rbprc_avg30=avg30, **extra))


def user_id(username='testuser'):
    return User.query.filter_by(username=username).one().id


def add_owned(product_id, quantity, *, user='testuser', purchase=None, note=None,
              at=datetime(2026, 10, 1, 9, 30)):
    """One `rbuserproducts` line of `user` (committed); returns it."""
    row = RbUserProduct(rbupr_user_id=user_id(user), rbupr_id_product=product_id,
                        rbupr_quantity=quantity, rbupr_purchase_price=purchase,
                        rbupr_note=note, rbupr_created_at=at, rbupr_updated_at=at)
    db.session.add(row)
    db.session.commit()
    return row


def owned_rows(user='testuser'):
    db.session.expire_all()
    return RbUserProduct.query.filter_by(rbupr_user_id=user_id(user)).order_by(
        RbUserProduct.rbupr_id).all()


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
