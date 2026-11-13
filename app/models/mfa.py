from app import db
from app.utils import clock


class RbUserMfa(db.Model):
    """TOTP two-factor authentication of one user (F9-d): 1:1 with `rbusers`.

    `rbmfa_secret_enc` is the Fernet ciphertext of the base32 secret (key
    `TOTP_ENCRYPTION_KEY`); the clear secret is never stored. `rbmfa_enabled_at` NULL = a
    pending setup (the user has not confirmed a code yet). `rbmfa_last_step` is the last
    accepted TOTP step: a code of that step or an earlier one is refused (replay protection).
    Logic in `app.services.mfa`. Names match migration 0031.
    """
    __tablename__ = 'rbusermfa'
    __table_args__ = (
        db.PrimaryKeyConstraint('rbmfa_user_id', name='rbusermfa_pkey'),
        db.ForeignKeyConstraint(
            ['rbmfa_user_id'], ['riftbound.rbusers.id'],
            name='rbusermfa_user_fk', ondelete='CASCADE'),
        {"schema": "riftbound", "comment": 'TOTP two-factor authentication of a user (F9).'},
    )

    rbmfa_user_id = db.Column(db.Integer, nullable=False, comment='User id')
    rbmfa_secret_enc = db.Column(db.Text, nullable=False,
                                 comment='Fernet ciphertext of the TOTP secret; never the secret')
    rbmfa_enabled_at = db.Column(db.DateTime, nullable=True,
                                 comment='When 2FA was turned on (UTC); NULL = pending setup')
    rbmfa_last_step = db.Column(db.BigInteger, nullable=True,
                                comment='Last accepted TOTP step (unix time // 30); replay guard')
    rbmfa_created_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='When the secret was created (UTC)')


class RbRecoveryCode(db.Model):
    """One recovery code of a user (F9-d): ten per generation, single use.

    Only `sha256` of the normalised code (lower case, no spaces or hyphens) is stored.
    Names match migration 0031.
    """
    __tablename__ = 'rbrecoverycodes'
    __table_args__ = (
        db.PrimaryKeyConstraint('rbrco_id', name='rbrecoverycodes_pkey'),
        db.ForeignKeyConstraint(
            ['rbrco_user_id'], ['riftbound.rbusers.id'],
            name='rbrecoverycodes_user_fk', ondelete='CASCADE'),
        db.Index('ix_rbrecoverycodes_user', 'rbrco_user_id'),
        {"schema": "riftbound", "comment": 'Two-factor recovery codes, hashed (F9).'},
    )

    # BIGINT in PostgreSQL; INTEGER in SQLite, where only an INTEGER PRIMARY KEY autoincrements.
    rbrco_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                         autoincrement=True, comment='Recovery code id')
    rbrco_user_id = db.Column(db.Integer, nullable=False, comment='User id')
    rbrco_code_hash = db.Column(db.CHAR(64), nullable=False,
                                comment='sha256 of the normalised code (64 hex); never the code')
    rbrco_used_at = db.Column(db.DateTime, nullable=True,
                              comment='When the code was used (UTC); NULL = unused')
