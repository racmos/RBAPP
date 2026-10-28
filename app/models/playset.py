from app import db
from app.utils import clock


class RbKeepPlayset(db.Model):
    """A card name a user keeps a playset of (F3-a, D-F3-12).

    One row per user and `name_key(card name)`: the mark covers every printing
    of the name. Names match migration 0015."""
    __tablename__ = 'rbkeepplayset'
    __table_args__ = (
        db.PrimaryKeyConstraint('rbkps_user_id', 'rbkps_name_key', name='rbkeepplayset_pkey'),
        db.ForeignKeyConstraint(
            ['rbkps_user_id'], ['riftbound.rbusers.id'],
            name='rbkeepplayset_user_fk', ondelete='CASCADE'),
        {"schema": "riftbound", "comment": 'Card names a user keeps a playset of (F3).'},
    )

    rbkps_user_id = db.Column(db.Integer, nullable=False, comment='User id')
    rbkps_name_key = db.Column(db.String(200), nullable=False,
                               comment='Normalized card name (name_key)')
    rbkps_created_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 server_default=db.func.now(),
                                 comment='When the mark was created (UTC)')
