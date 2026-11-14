from app import db
from app.utils import clock


class RbApiKey(db.Model):
    """The personal read-only API key of one user (F9-h): at most one per user.

    Only `sha256(key)` (hex) and the first 14 characters (`rb_live_` + 6 hex, shown to the user
    to recognise the key) are stored; the key itself is shown once and never stored or logged.
    Logic in `app.services.api_keys`. Names match migration 0032.
    """
    __tablename__ = 'rbapikeys'
    __table_args__ = (
        db.PrimaryKeyConstraint('rbapk_id', name='rbapikeys_pkey'),
        db.ForeignKeyConstraint(
            ['rbapk_user_id'], ['riftbound.rbusers.id'],
            name='rbapikeys_user_fk', ondelete='CASCADE'),
        db.UniqueConstraint('rbapk_user_id', name='rbapikeys_user_key'),
        db.UniqueConstraint('rbapk_key_hash', name='rbapikeys_key_hash_key'),
        {"schema": "riftbound", "comment": 'Personal read-only API keys, hashed (F9).'},
    )

    # BIGINT in PostgreSQL; INTEGER in SQLite, where only an INTEGER PRIMARY KEY autoincrements.
    rbapk_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                         autoincrement=True, comment='API key id')
    rbapk_user_id = db.Column(db.Integer, nullable=False, comment='User id')
    rbapk_prefix = db.Column(db.String(16), nullable=False,
                             comment='First 14 characters of the key (rb_live_ + 6 hex)')
    rbapk_key_hash = db.Column(db.CHAR(64), nullable=False,
                               comment='sha256 of the key (64 hex); never the key')
    rbapk_created_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='When the key was created (UTC)')
    rbapk_last_used_at = db.Column(db.DateTime, nullable=True,
                                   comment='Last use (UTC), written at most once a minute')
