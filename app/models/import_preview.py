from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.utils import clock


class RbImportPreview(db.Model):
    """A parsed import file waiting for the user's decision (F3-e): the rows the commit needs,
    for 30 minutes. Expired previews are deleted by the next preview request; a user keeps
    only their latest one. Names match migration 0018."""
    __tablename__ = 'rbimportpreviews'
    __table_args__ = (
        db.PrimaryKeyConstraint('rbimp_id', name='rbimportpreviews_pkey'),
        db.ForeignKeyConstraint(
            ['rbimp_user_id'], ['riftbound.rbusers.id'],
            name='rbimportpreviews_user_fk', ondelete='CASCADE'),
        db.Index('ix_rbimportpreviews_expires', 'rbimp_expires_at'),
        {"schema": "riftbound", "comment": 'Import previews waiting for a commit (F3).'},
    )

    rbimp_id = db.Column(db.String(36), nullable=False, comment='Preview id (UUID4)')
    rbimp_user_id = db.Column(db.Integer, nullable=False, comment='User id')
    rbimp_format = db.Column(db.String(16), nullable=False, comment='File format (rbapp)')
    rbimp_rows = db.Column(db.JSON().with_variant(JSONB(), 'postgresql'), nullable=False,
                           comment='Parsed rows, as the commit needs them')
    rbimp_created_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='When the preview was made (UTC)')
    rbimp_expires_at = db.Column(db.DateTime, nullable=False,
                                 comment='When the preview stops being valid (UTC)')
