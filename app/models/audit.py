"""Audit trail of admin actions (F13-R2).

Every admin write records one row here, in the same transaction as the change
(`app.services.audit.record` adds the row without committing). The actor is
denormalised (`rbaud_actor_username`) so the row survives the user's deletion;
`rbaud_actor_id` is SET NULL then.
"""
from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.utils import clock


def _json():
    # none_as_null: a Python None is SQL NULL, not the JSON literal 'null'.
    return db.JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), 'postgresql')


class RbAdminAudit(db.Model):
    """One admin action. The names match migration 0010."""
    __tablename__ = 'rbadminaudit'
    __table_args__ = (
        db.PrimaryKeyConstraint('rbaud_id', name='rbadminaudit_pkey'),
        db.ForeignKeyConstraint(
            ['rbaud_actor_id'], ['riftbound.rbusers.id'],
            name='rbadminaudit_actor_fk', ondelete='SET NULL'),
        db.Index('idx_rbadminaudit_created', 'rbaud_created_at'),
        db.Index('idx_rbadminaudit_target', 'rbaud_target_type', 'rbaud_target_id'),
        {"schema": "riftbound", "comment": 'Audit trail of admin actions (F13)'},
    )

    rbaud_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                         primary_key=True, autoincrement=True, comment='Audit row id')
    rbaud_actor_id = db.Column(db.Integer, nullable=True,
                               comment='User who acted; NULL for system jobs')
    rbaud_actor_username = db.Column(db.String(64), nullable=False,
                                     comment='Username at the time of the action ("system" for jobs)')
    rbaud_action = db.Column(db.String(48), nullable=False,
                             comment='Dotted lowercase action, e.g. set.create')
    rbaud_target_type = db.Column(db.String(24), nullable=False,
                                  comment='Kind of target: set, card, user, ...')
    rbaud_target_id = db.Column(db.String(64), nullable=True,
                                comment='Identifier of the target, when it has one')
    rbaud_details = db.Column(_json(), nullable=True,
                              comment='Small JSON summary of the change (old/new values)')
    rbaud_created_at = db.Column(db.DateTime, nullable=False,
                                 default=lambda: clock.utcnow(), server_default=db.func.now(),
                                 comment='When the action happened (UTC)')

    def __repr__(self):
        return f'<RbAdminAudit {self.rbaud_action} {self.rbaud_target_type}:{self.rbaud_target_id}>'
