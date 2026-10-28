"""Daily collection value snapshots (F4-c).

`take_snapshots` runs after the daily price load: one `rbvaluesnaps` row per user
with at least one collection line (D-F4-4), priced by the same code as `GET /collection`
(D-F4-5). A second run the same day replaces the day's values.
"""
from datetime import date

import sqlalchemy as sa

from app import db
from app.models import RbValueSnapshot, User
from app.services.collection_read import user_value_summaries


def take_snapshots(today: date) -> dict:
    summaries = user_value_summaries()
    ids = dict(db.session.execute(
        sa.select(User.username, User.id).where(User.username.in_(list(summaries)))).all()
    ) if summaries else {}
    existing = {row.rbvsn_user_id: row for row in db.session.execute(
        sa.select(RbValueSnapshot).where(RbValueSnapshot.rbvsn_date == today)).scalars()}

    total = 0
    rows = 0
    for username, summary in summaries.items():
        user_id = ids.get(username)
        if user_id is None:
            continue
        row = existing.get(user_id)
        if row is None:
            row = RbValueSnapshot(rbvsn_user_id=user_id, rbvsn_date=today)
            db.session.add(row)
        row.rbvsn_value = summary['value']
        row.rbvsn_cost = summary['cost']
        row.rbvsn_qty = summary['qty']
        row.rbvsn_unique = summary['unique']
        row.rbvsn_unpriced = summary['unpriced']
        total += summary['value']
        rows += 1
    db.session.commit()
    return {'date': today.isoformat(), 'users': rows, 'rows': rows,
            'total_value': float(total)}
