from app import db
from app.utils import clock


class RbValueSnapshot(db.Model):
    """The value of one user's collection on one day (F4-c): written by the
    `value_snapshot` job after the daily price load. One row per user and day; a
    second run the same day replaces it. The history cannot be rebuilt later, so rows
    are never deleted except with the user. Names match migration 0016."""
    __tablename__ = 'rbvaluesnaps'
    __table_args__ = (
        db.PrimaryKeyConstraint('rbvsn_user_id', 'rbvsn_date', name='rbvaluesnaps_pkey'),
        db.ForeignKeyConstraint(
            ['rbvsn_user_id'], ['riftbound.rbusers.id'],
            name='rbvaluesnaps_user_fk', ondelete='CASCADE'),
        {"schema": "riftbound", "comment": 'Daily value of each user collection (F4).'},
    )

    rbvsn_user_id = db.Column(db.Integer, nullable=False, comment='User id')
    rbvsn_date = db.Column(db.Date, nullable=False, comment='Day of the snapshot (UTC)')
    rbvsn_value = db.Column(db.Numeric(12, 2), nullable=False,
                            comment='Sum of market x quantity over the priced lines')
    rbvsn_cost = db.Column(db.Numeric(12, 2), nullable=True,
                           comment='Sum of purchase price x quantity; NULL when no line has one')
    rbvsn_qty = db.Column(db.Integer, nullable=False, comment='Copies in the collection')
    rbvsn_unique = db.Column(db.Integer, nullable=False, comment='Distinct printings')
    rbvsn_unpriced = db.Column(db.Integer, nullable=False, comment='Lines without a market price')
    rbvsn_created_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 server_default=db.func.now(),
                                 comment='When the row was created (UTC)')
