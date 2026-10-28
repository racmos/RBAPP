from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.schemas.prefs_domain import sql_in
from app.utils import clock

# Kinds the database accepts. Every unit that registers a job kind
# (app/jobs/) extends this tuple and `ck_rbjobs_kind` with its own migration.
JOB_KINDS = ('heartbeat', 'daily_prices', 'riot_sync', 'value_snapshot', 'products_refresh')
JOB_STATUSES = ('queued', 'running', 'success', 'error')
ACTIVE_STATUSES = ('queued', 'running')
MESSAGE_MAX_LENGTH = 300

_ACTIVE = sql_in('rbjob_status', ACTIVE_STATUSES)


def _json():
    # none_as_null: a Python None is SQL NULL, not the JSON literal 'null'.
    return db.JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), 'postgresql')


class RbJob(db.Model):
    """One background job (F4-a): queued by a timer, the CLI or an admin,
    claimed and run by `flask jobs run-pending` (`app.services.jobs`).

    The partial unique index allows one active (queued or running) job per
    kind, so two enqueues of the same kind can never both succeed. The names
    match migration 0007.
    """
    __tablename__ = 'rbjobs'
    __table_args__ = (
        db.PrimaryKeyConstraint('rbjob_id', name='rbjobs_pkey'),
        db.ForeignKeyConstraint(
            ['rbjob_requested_by'], ['riftbound.rbusers.id'],
            name='rbjobs_requested_by_fk', ondelete='SET NULL'),
        db.CheckConstraint(sql_in('rbjob_kind', JOB_KINDS), name='ck_rbjobs_kind'),
        db.CheckConstraint(sql_in('rbjob_status', JOB_STATUSES), name='ck_rbjobs_status'),
        db.Index('ux_rbjobs_active_kind', 'rbjob_kind', unique=True,
                 postgresql_where=db.text(_ACTIVE), sqlite_where=db.text(_ACTIVE)),
        db.Index('ix_rbjobs_status_requested', 'rbjob_status', 'rbjob_requested_at'),
        {"schema": "riftbound", "comment": 'Background jobs: queue and results of the job runner'},
    )

    # BIGINT on PostgreSQL; INTEGER on SQLite, where only an INTEGER PRIMARY KEY
    # autoincrements (tests).
    rbjob_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                         autoincrement=True, comment='Job id')
    rbjob_kind = db.Column(db.String(32), nullable=False,
                           comment='Registered job kind (app/jobs/registry.py)')
    rbjob_params = db.Column(_json(), nullable=False, default=dict,
                             server_default=db.text("'{}'"),
                             comment='Parameters passed to the handler')
    rbjob_status = db.Column(db.String(10), nullable=False, default='queued',
                             server_default='queued',
                             comment='queued, running, success or error')
    rbjob_requested_by = db.Column(db.Integer, nullable=True,
                                   comment='User who queued the job; NULL for timers and the CLI')
    rbjob_requested_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                   comment='When the job was queued (UTC)')
    rbjob_started_at = db.Column(db.DateTime, nullable=True,
                                 comment='When a runner claimed the job (UTC)')
    rbjob_finished_at = db.Column(db.DateTime, nullable=True,
                                  comment='When the job ended or timed out (UTC)')
    rbjob_result = db.Column(_json(), nullable=True, comment='Value returned by the handler')
    rbjob_message = db.Column(db.String(MESSAGE_MAX_LENGTH), nullable=True,
                              comment='Error message, or a short note')
