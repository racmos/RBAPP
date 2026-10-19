from app import db


class RbCaptchaUsed(db.Model):
    """ALTCHA challenges that were already accepted (D16).

    One row per accepted challenge, keyed by its sha256, kept until the
    challenge itself would have expired. A second insert of the same hash is a
    replay (IntegrityError). Shared by every worker, unlike an in-memory set.
    """
    __tablename__ = 'rbcaptcha_used'
    __table_args__ = (
        db.Index('idx_rbcaptcha_used_expires', 'rbcap_expires_at'),
        {"schema": "riftbound"},
    )

    rbcap_hash = db.Column(db.String(64), primary_key=True)
    rbcap_expires_at = db.Column(db.DateTime, nullable=False)
