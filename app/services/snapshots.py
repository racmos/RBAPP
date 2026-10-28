"""Daily collection value snapshots (F4-c).

`take_snapshots` runs after the daily price load: one `rbvaluesnaps` row per user
with at least one collection line (D-F4-4), priced by the same code as `GET /collection`
(D-F4-5). A second run the same day replaces the day's values.

F14-c: `rbvsn_products_value` keeps the value of the user's sealed products apart (never
added to `rbvsn_value`), priced like `GET /me/products`; NULL when the user has no product
lines. A user with product lines but no collection lines gets a row with the cards at 0.
"""
from datetime import date
from decimal import Decimal

import sqlalchemy as sa

from app import db
from app.models import RbValueSnapshot, User
from app.services.collection_read import user_value_summaries
from app.services.user_products import products_values

_NO_CARDS = {'value': Decimal(0), 'cost': None, 'qty': 0, 'unique': 0, 'unpriced': 0}


def take_snapshots(today: date) -> dict:
    summaries = user_value_summaries()
    ids = dict(db.session.execute(
        sa.select(User.username, User.id).where(User.username.in_(list(summaries)))).all()
    ) if summaries else {}
    by_user = {ids[username]: summary for username, summary in summaries.items()
               if username in ids}
    products = products_values()
    existing = {row.rbvsn_user_id: row for row in db.session.execute(
        sa.select(RbValueSnapshot).where(RbValueSnapshot.rbvsn_date == today)).scalars()}

    total = 0
    products_total = 0
    rows = 0
    for user_id in [*by_user, *(u for u in products if u not in by_user)]:
        summary = by_user.get(user_id, _NO_CARDS)
        row = existing.get(user_id)
        if row is None:
            row = RbValueSnapshot(rbvsn_user_id=user_id, rbvsn_date=today)
            db.session.add(row)
        row.rbvsn_value = summary['value']
        row.rbvsn_cost = summary['cost']
        row.rbvsn_qty = summary['qty']
        row.rbvsn_unique = summary['unique']
        row.rbvsn_unpriced = summary['unpriced']
        row.rbvsn_products_value = products.get(user_id)
        total += summary['value']
        products_total += products.get(user_id) or 0
        rows += 1
    db.session.commit()
    return {'date': today.isoformat(), 'users': rows, 'rows': rows,
            'total_value': float(total), 'products_value': float(products_total)}
