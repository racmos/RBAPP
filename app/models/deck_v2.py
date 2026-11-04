from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.schemas.deck_content import VISIBILITIES
from app.schemas.game_domain import GAME_MODES
from app.schemas.prefs_domain import sql_in
from app.utils import clock

NAME_MAX_LENGTH = 80
LEGACY_NAME_MAX_LENGTH = 200
NOTE_MAX_LENGTH = 200
SHARE_SLUG_MAX_LENGTH = 24


class RbDeckHead(db.Model):
    """One deck of a user (F5-c, D-F5-1): name, game mode, visibility and share link. Its
    contents live in `rbdeckversions`; `rbdkh_current_version_id` is the version the editor
    shows (no foreign key: heads and versions would reference each other; the deck services
    keep it pointing at one of the deck's versions). `rbdkh_legacy_name` is the `rbdecks`
    name the deck was migrated from (NULL for a deck created in v2). Names match
    migration 0025."""
    __tablename__ = 'rbdeckheads'
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['rbdkh_user_id'], ['riftbound.rbusers.id'],
            name='rbdeckheads_user_fk', ondelete='CASCADE'),
        db.UniqueConstraint('rbdkh_user_id', 'rbdkh_name', name='rbdeckheads_user_name_uq'),
        db.UniqueConstraint('rbdkh_share_slug', name='rbdeckheads_share_slug_uq'),
        db.CheckConstraint(sql_in('rbdkh_mode', GAME_MODES), name='rbdeckheads_mode_chk'),
        db.CheckConstraint(sql_in('rbdkh_visibility', VISIBILITIES),
                           name='rbdeckheads_visibility_chk'),
        {"schema": "riftbound", "comment": 'Decks v2: one row per deck (F5).'},
    )

    # BIGINT in PostgreSQL; INTEGER in SQLite, where only an INTEGER PRIMARY KEY autoincrements.
    rbdkh_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                         primary_key=True, autoincrement=True, comment='Deck id')
    rbdkh_user_id = db.Column(db.Integer, nullable=False, comment='Owner (rbusers.id)')
    rbdkh_name = db.Column(db.String(NAME_MAX_LENGTH), nullable=False,
                           comment='Deck name, unique per user')
    rbdkh_mode = db.Column(db.String(3), nullable=False, comment='Game mode: 1v1 or 2v2')
    rbdkh_visibility = db.Column(db.String(8), nullable=False, default='private',
                                 server_default='private', comment='private or public')
    rbdkh_share_slug = db.Column(db.String(SHARE_SLUG_MAX_LENGTH), nullable=True,
                                 comment='Read-only share link slug (NULL = not shared)')
    rbdkh_current_version_id = db.Column(db.BigInteger, nullable=True,
                                         comment='Current version (rbdeckversions.rbdkv_id)')
    rbdkh_legacy_name = db.Column(db.String(LEGACY_NAME_MAX_LENGTH), nullable=True,
                                  comment='rbdecks name it was migrated from (NULL = new)')
    rbdkh_created_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='When the deck was created (UTC)')
    rbdkh_updated_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='Last change (UTC)')


class RbDeckVersion(db.Model):
    """One version of a deck (F5-c): content v2 (`app/schemas/deck_content.py`), its number
    in the deck and an optional note. `rbdkv_legacy_id` is the `rbdecks.id` it was copied
    from (no foreign key: `rbdecks` goes away in F11), which makes `flask decks migrate`
    idempotent. Names match migration 0025."""
    __tablename__ = 'rbdeckversions'
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['rbdkv_deck_id'], ['riftbound.rbdeckheads.rbdkh_id'],
            name='rbdeckversions_deck_fk', ondelete='CASCADE'),
        db.UniqueConstraint('rbdkv_deck_id', 'rbdkv_seq', name='rbdeckversions_deck_seq_uq'),
        db.UniqueConstraint('rbdkv_legacy_id', name='rbdeckversions_legacy_uq'),
        db.CheckConstraint('rbdkv_seq >= 1', name='rbdeckversions_seq_chk'),
        {"schema": "riftbound", "comment": 'Decks v2: versions of each deck (F5).'},
    )

    rbdkv_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                         primary_key=True, autoincrement=True, comment='Version id')
    rbdkv_deck_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                              nullable=False, comment='Deck (rbdeckheads.rbdkh_id)')
    rbdkv_seq = db.Column(db.Integer, nullable=False, comment='Version number in the deck (1..n)')
    rbdkv_content = db.Column(db.JSON().with_variant(JSONB(), 'postgresql'), nullable=False,
                              comment='Content v2 (legend, champion, zones)')
    rbdkv_note = db.Column(db.String(NOTE_MAX_LENGTH), nullable=True,
                           comment='Free note (optional)')
    rbdkv_legacy_id = db.Column(db.Integer, nullable=True,
                                comment='rbdecks.id it was migrated from (NULL = new)')
    rbdkv_created_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='When the version was saved (UTC)')
