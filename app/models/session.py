from app import db
from app.utils import clock

AUTH_METHODS = ('password', 'discord', 'google')


class RbSession(db.Model):
    """One sign-in (F9-a): the server side of a Flask session or remember cookie.

    The cookie holds `s:<token>`; only `sha256(token)` is stored. A row is active while it is
    not revoked and, when remembered, before `expires_at` (absolute, 30 days) or, when not
    remembered, within 12 hours of `last_seen_at` (`app.services.sessions`). Names match
    migration 0029.
    """
    __tablename__ = 'rbsessions'
    __table_args__ = (
        db.PrimaryKeyConstraint('rbses_id', name='rbsessions_pkey'),
        db.ForeignKeyConstraint(
            ['rbses_user_id'], ['riftbound.rbusers.id'],
            name='rbsessions_user_fk', ondelete='CASCADE'),
        db.UniqueConstraint('rbses_token_hash', name='rbsessions_token_hash_key'),
        db.CheckConstraint("rbses_auth_method IN ('password', 'discord', 'google')",
                           name='ck_rbsessions_auth_method'),
        db.Index('ix_rbsessions_user_revoked', 'rbses_user_id', 'rbses_revoked_at'),
        db.Index('ix_rbsessions_expires_at', 'rbses_expires_at'),
        {"schema": "riftbound", "comment": 'Server-side sessions: one row per sign-in (F9).'},
    )

    # BIGINT in PostgreSQL; INTEGER in SQLite, where only an INTEGER PRIMARY KEY autoincrements.
    rbses_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                         autoincrement=True, comment='Session id')
    rbses_user_id = db.Column(db.Integer, nullable=False, comment='User id')
    rbses_token_hash = db.Column(db.CHAR(64), nullable=False,
                                 comment='sha256 of the session token (64 hex); never the token')
    rbses_created_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='Sign-in time (UTC)')
    rbses_last_seen_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                   comment='Last use (UTC), written at most every 5 minutes')
    rbses_expires_at = db.Column(db.DateTime, nullable=True,
                                 comment='Absolute end of a remembered session (UTC); NULL otherwise')
    rbses_remember = db.Column(db.Boolean, nullable=False, default=False,
                               server_default=db.false(), comment='Signed in with "remember me"')
    rbses_auth_method = db.Column(db.String(16), nullable=False, default='password',
                                  server_default='password',
                                  comment='How the user signed in: password, discord or google')
    rbses_mfa = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false(),
                          comment='Second factor passed at sign-in')
    rbses_reauth_at = db.Column(db.DateTime, nullable=True,
                                comment='Last re-authentication (UTC)')
    rbses_user_agent = db.Column(db.String(255), nullable=True,
                                 comment='User-Agent at sign-in, cut to 255 characters')
    rbses_ip_prefix = db.Column(db.String(48), nullable=True,
                                comment='IP prefix at sign-in (IPv4 /24, IPv6 /48); never the address')
    rbses_revoked_at = db.Column(db.DateTime, nullable=True,
                                 comment='When the session was ended (UTC); NULL = not revoked')
