from app import db
from app.utils import clock

# The code CHECK needs a regular expression on PostgreSQL and GLOB on SQLite (the tests);
# each version is emitted only on its dialect. Same text as migration 0024.
CODE_CHECK_PG = "rbloc_code ~ '^[A-Za-z0-9-]{1,32}$'"
CODE_CHECK_SQLITE = ("rbloc_code NOT GLOB '*[^A-Za-z0-9-]*' "
                     "AND length(rbloc_code) BETWEEN 1 AND 32")


class RbLocation(db.Model):
    """A place where a user keeps cards (F16-a): binder, box, deck pool or, from F16-e, a
    mounted deck. The code is unique per user ignoring case (expression index on
    `lower(rbloc_code)`); `rbloc_position` is the user's order (1..n). Names match
    migration 0024."""
    __tablename__ = 'rblocations'
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['rbloc_user'], ['riftbound.rbusers.username'],
            name='rblocations_user_fk', onupdate='CASCADE', ondelete='CASCADE'),
        db.CheckConstraint(CODE_CHECK_PG, name='rblocations_code_chk').ddl_if(
            dialect='postgresql'),
        db.CheckConstraint(CODE_CHECK_SQLITE, name='rblocations_code_chk').ddl_if(
            dialect='sqlite'),
        db.CheckConstraint('rbloc_position >= 1', name='rblocations_position_chk'),
        db.UniqueConstraint('rbloc_user', 'rbloc_position', name='rblocations_user_position_uq'),
        db.UniqueConstraint('rbloc_deck_id', name='rblocations_deck_uq'),
        db.Index('rblocations_user_code_uq', 'rbloc_user', db.text('lower(rbloc_code)'),
                 unique=True),
        {"schema": "riftbound", "comment": 'Storage locations of each user (F16).'},
    )

    # BIGINT in PostgreSQL; INTEGER in SQLite, where only an INTEGER PRIMARY KEY autoincrements.
    rbloc_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                         primary_key=True, autoincrement=True, comment='Location id')
    rbloc_user = db.Column(db.String(64), nullable=False, comment='Owner (rbusers.username)')
    rbloc_code = db.Column(db.String(32), nullable=False,
                           comment='Code: 1-32 letters, digits or -; unique per user ignoring case')
    rbloc_description = db.Column(db.String(200), nullable=True, comment='Description (optional)')
    rbloc_position = db.Column(db.Integer, nullable=False,
                               comment="Place in the user's order (1..n, unique per user)")
    rbloc_locked = db.Column(db.Boolean, nullable=False, default=False,
                             server_default=db.false(),
                             comment='Locked: skipped by automatic takes, quantities read-only')
    rbloc_deck_id = db.Column(db.BigInteger, nullable=True,
                              comment='Mounted deck (F16-e); NULL for an ordinary location')
    rbloc_updated_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='Last change (UTC)')


class RbCollectionLocation(db.Model):
    """Copies of one collection line kept in one location (F16-a). The sum over a line is
    at most its `rbcol_quantity`; the rest is unassigned (derived, never stored)."""
    __tablename__ = 'rbcollection_locations'
    __table_args__ = (
        db.PrimaryKeyConstraint('rbcll_line_id', 'rbcll_location_id',
                                name='rbcollection_locations_pkey'),
        db.ForeignKeyConstraint(
            ['rbcll_line_id'], ['riftbound.rbcollection.rbcol_id'],
            name='rbcollection_locations_line_fk', ondelete='CASCADE'),
        db.ForeignKeyConstraint(
            ['rbcll_location_id'], ['riftbound.rblocations.rbloc_id'],
            name='rbcollection_locations_location_fk', ondelete='CASCADE'),
        db.CheckConstraint('rbcll_qty >= 1', name='rbcollection_locations_qty_chk'),
        db.Index('ix_rbcollection_locations_location', 'rbcll_location_id'),
        {"schema": "riftbound", "comment": 'Copies of each collection line per location (F16).'},
    )

    rbcll_line_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'), nullable=False,
                              comment='Collection line (rbcollection.rbcol_id)')
    rbcll_location_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                                  nullable=False, comment='Location (rblocations.rbloc_id)')
    rbcll_qty = db.Column(db.Integer, nullable=False, comment='Copies of the line in the location')
