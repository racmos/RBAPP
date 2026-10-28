from app import db
from app.utils import clock


class RbUserProduct(db.Model):
    """Copies of one sealed product a user owns (F14-c): quantity, optional unit purchase
    price and note. Several lines of one product may exist (different purchase prices).
    The products total is never part of the collection value. Names match migration 0021."""
    __tablename__ = 'rbuserproducts'
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['rbupr_user_id'], ['riftbound.rbusers.id'],
            name='rbuserproducts_user_fk', ondelete='CASCADE'),
        db.ForeignKeyConstraint(
            ['rbupr_id_product'], ['riftbound.rbproducts.rbpdt_id_product'],
            name='rbuserproducts_product_fk', ondelete='RESTRICT'),
        db.CheckConstraint('rbupr_quantity BETWEEN 1 AND 9999',
                           name='rbuserproducts_quantity_chk'),
        db.CheckConstraint('rbupr_purchase_price IS NULL OR rbupr_purchase_price >= 0',
                           name='rbuserproducts_purchase_price_chk'),
        db.Index('ix_rbuserproducts_user', 'rbupr_user_id'),
        {"schema": "riftbound", "comment": 'Sealed products each user owns (F14).'},
    )

    # BIGINT in PostgreSQL; INTEGER in SQLite, where only an INTEGER PRIMARY KEY autoincrements.
    rbupr_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                         primary_key=True, autoincrement=True, comment='Line id')
    rbupr_user_id = db.Column(db.Integer, nullable=False, comment='User id')
    rbupr_id_product = db.Column(db.Integer, nullable=False, comment='Cardmarket product id')
    rbupr_quantity = db.Column(db.Integer, nullable=False, comment='Copies owned (1..9999)')
    rbupr_purchase_price = db.Column(db.Numeric(10, 2), nullable=True,
                                     comment='Unit purchase price (optional)')
    rbupr_note = db.Column(db.String(200), nullable=True, comment='Free note (optional)')
    rbupr_created_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='When the line was created (UTC)')
    rbupr_updated_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='Last change (UTC)')
