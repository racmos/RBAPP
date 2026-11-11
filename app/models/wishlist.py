from app import db
from app.schemas.prefs_domain import sql_in
from app.utils import clock

# Value domains and sizes (F3-f, docs/requirements/F3/F3-f-wishlists-design.md "Data model").
NAME_MAX_LENGTH = 80
CARD_NAME_MAX_LENGTH = 200
NOTE_MAX_LENGTH = 200
FOILS = ('any', 'N', 'S')
QTY_MIN, QTY_MAX = 1, 99

# Partial-index conditions; the same text runs on PostgreSQL and SQLite (the tests).
_DEFAULT = 'rbwls_is_default'
_UNREAD = 'rbwal_read_at IS NULL'


def _both_or_neither(set_column: str, card_column: str) -> str:
    """CHECK text: a printing is a set and a card number together, or neither (any printing)."""
    return f'({set_column} IS NULL) = ({card_column} IS NULL)'


class RbWishlist(db.Model):
    """One wishlist of a user (F3-f, design D1, A4): a name unique per user ignoring case
    (expression index on `lower(rbwls_name)`), the user's order (`rbwls_position`, 1..n,
    unique per user like `rblocations`) and at most one default list per user (partial
    unique index on the user WHERE `rbwls_is_default`). The 20-list limit lives in the
    service. Names match migration 0026."""
    __tablename__ = 'rbwishlists'
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['rbwls_user_id'], ['riftbound.rbusers.id'],
            name='rbwishlists_user_fk', ondelete='CASCADE'),
        db.CheckConstraint('length(trim(rbwls_name)) >= 1', name='rbwishlists_name_chk'),
        db.CheckConstraint('rbwls_position >= 1', name='rbwishlists_position_chk'),
        db.UniqueConstraint('rbwls_user_id', 'rbwls_position', name='rbwishlists_user_position_uq'),
        db.Index('rbwishlists_user_name_uq', 'rbwls_user_id', db.text('lower(rbwls_name)'),
                 unique=True),
        db.Index('rbwishlists_user_default_uq', 'rbwls_user_id', unique=True,
                 postgresql_where=db.text(_DEFAULT), sqlite_where=db.text(_DEFAULT)),
        {"schema": "riftbound", "comment": 'Wishlists of each user (F3-f).'},
    )

    # BIGINT in PostgreSQL; INTEGER in SQLite, where only an INTEGER PRIMARY KEY autoincrements.
    rbwls_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                         primary_key=True, autoincrement=True, comment='Wishlist id')
    rbwls_user_id = db.Column(db.Integer, nullable=False, comment='Owner (rbusers.id)')
    rbwls_name = db.Column(db.String(NAME_MAX_LENGTH), nullable=False,
                           comment='List name, unique per user ignoring case')
    rbwls_is_default = db.Column(db.Boolean, nullable=False, default=False,
                                 server_default=db.false(),
                                 comment='Default list of the user (at most one per user)')
    rbwls_position = db.Column(db.Integer, nullable=False,
                               comment="Place in the user's order (1..n, unique per user)")
    rbwls_created_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='When the list was created (UTC)')
    rbwls_updated_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='Last change (UTC)')


class RbWishlistLine(db.Model):
    """One wanted card in a wishlist (F3-f, A1, A2, A6). The target is the card name
    (`rbwsl_name_key`, as `app/services/bans.py::name_key`) plus either a printing (set +
    number) or none (NULL = any printing), plus the foil wish (`any`, `N`, `S`). A target is
    unique per list: `rbwishlistlines_target_uq` indexes `COALESCE(set, '*')` and
    `COALESCE(card, '*')` so two by-name lines (NULL printing) also collide. No alert state:
    alerts are a daily evaluation (A3). The 100-line limit lives in the service. Names match
    migration 0026."""
    __tablename__ = 'rbwishlistlines'
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['rbwsl_list_id'], ['riftbound.rbwishlists.rbwls_id'],
            name='rbwishlistlines_list_fk', ondelete='CASCADE'),
        db.CheckConstraint(_both_or_neither('rbwsl_rbset_id', 'rbwsl_rbcar_id'),
                           name='rbwishlistlines_printing_chk'),
        db.CheckConstraint(sql_in('rbwsl_foil', FOILS), name='rbwishlistlines_foil_chk'),
        db.CheckConstraint(f'rbwsl_qty BETWEEN {QTY_MIN} AND {QTY_MAX}',
                           name='rbwishlistlines_qty_chk'),
        db.CheckConstraint('rbwsl_max_price IS NULL OR rbwsl_max_price >= 0',
                           name='rbwishlistlines_max_price_chk'),
        db.Index('rbwishlistlines_target_uq', 'rbwsl_list_id', 'rbwsl_name_key',
                 db.text("coalesce(rbwsl_rbset_id, '*')"),
                 db.text("coalesce(rbwsl_rbcar_id, '*')"), 'rbwsl_foil', unique=True),
        db.Index('ix_rbwishlistlines_name_key', 'rbwsl_name_key'),
        {"schema": "riftbound", "comment": 'Cards wanted in each wishlist (F3-f).'},
    )

    rbwsl_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                         primary_key=True, autoincrement=True, comment='Line id')
    rbwsl_list_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                              nullable=False, comment='Wishlist (rbwishlists.rbwls_id)')
    rbwsl_name_key = db.Column(db.String(CARD_NAME_MAX_LENGTH), nullable=False,
                               comment='Normalised card name (name_key)')
    rbwsl_name = db.Column(db.String(CARD_NAME_MAX_LENGTH), nullable=False,
                           comment='Card name as shown')
    rbwsl_rbset_id = db.Column(db.Text, nullable=True,
                               comment='Set of the wanted printing (NULL = any printing)')
    rbwsl_rbcar_id = db.Column(db.Text, nullable=True,
                               comment='Card number of the wanted printing (NULL = any printing)')
    rbwsl_foil = db.Column(db.String(3), nullable=False, default='any', server_default='any',
                           comment='Foil wish: any, N (non-foil) or S (foil)')
    rbwsl_qty = db.Column(db.SmallInteger, nullable=False, default=1, server_default='1',
                          comment='Copies wanted (1..99)')
    rbwsl_max_price = db.Column(db.Numeric(10, 2), nullable=True,
                                comment='Alert at or below this price (NULL = never alerts)')
    rbwsl_note = db.Column(db.String(NOTE_MAX_LENGTH), nullable=True,
                           comment='Free note (optional)')
    rbwsl_created_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='When the line was added (UTC)')
    rbwsl_updated_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='Last change (UTC)')


class RbWishlistAlert(db.Model):
    """A price alert raised for a user (F3-f, A3, A5): the card (name, optional printing)
    reached `rbwal_price`, at or below `rbwal_max_price`, on the price update of
    `rbwal_price_date`. One per user, card target and day (`rbwishlistalerts_target_uq`, NULL
    printing through `COALESCE` like the lines), so a re-run of the job the same day cannot
    duplicate it. Not linked to a list: alerts survive a deleted list, and the lists that hold
    the card are read live. Names match migration 0026."""
    __tablename__ = 'rbwishlistalerts'
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['rbwal_user_id'], ['riftbound.rbusers.id'],
            name='rbwishlistalerts_user_fk', ondelete='CASCADE'),
        db.CheckConstraint(_both_or_neither('rbwal_rbset_id', 'rbwal_rbcar_id'),
                           name='rbwishlistalerts_printing_chk'),
        db.CheckConstraint('rbwal_price >= 0 AND rbwal_max_price >= 0',
                           name='rbwishlistalerts_price_chk'),
        db.Index('rbwishlistalerts_target_uq', 'rbwal_user_id', 'rbwal_name_key',
                 db.text("coalesce(rbwal_rbset_id, '*')"),
                 db.text("coalesce(rbwal_rbcar_id, '*')"), 'rbwal_price_date', unique=True),
        db.Index('ix_rbwishlistalerts_user_created', 'rbwal_user_id', 'rbwal_created_at'),
        db.Index('ix_rbwishlistalerts_user_unread', 'rbwal_user_id',
                 postgresql_where=db.text(_UNREAD), sqlite_where=db.text(_UNREAD)),
        {"schema": "riftbound", "comment": 'Wishlist price alerts of each user (F3-f).'},
    )

    rbwal_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                         primary_key=True, autoincrement=True, comment='Alert id')
    rbwal_user_id = db.Column(db.Integer, nullable=False, comment='Owner (rbusers.id)')
    rbwal_name_key = db.Column(db.String(CARD_NAME_MAX_LENGTH), nullable=False,
                               comment='Normalised card name (name_key)')
    rbwal_name = db.Column(db.String(CARD_NAME_MAX_LENGTH), nullable=False,
                           comment='Card name as shown')
    rbwal_rbset_id = db.Column(db.Text, nullable=True,
                               comment='Set of the printing (NULL = any printing)')
    rbwal_rbcar_id = db.Column(db.Text, nullable=True,
                               comment='Card number of the printing (NULL = any printing)')
    rbwal_price = db.Column(db.Numeric(10, 2), nullable=False, comment='Price reached')
    rbwal_max_price = db.Column(db.Numeric(10, 2), nullable=False,
                                comment='Max price that raised the alert')
    rbwal_price_date = db.Column(db.Date, nullable=False,
                                 comment='Day of the price update that raised it')
    rbwal_created_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='When the alert was raised (UTC)')
    rbwal_read_at = db.Column(db.DateTime, nullable=True,
                              comment='When the user read it (UTC); NULL = unread')
