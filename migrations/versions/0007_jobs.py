"""job runner: rbjobs

Spec S1 of F4-a (docs/requirements/F4/F4-a-job-runner.md).

`riftbound.rbjobs` is the queue and the result log of the job runner
(`flask jobs run-pending`). `ck_rbjobs_kind` lists the registered job kinds;
every later unit that registers a kind extends it with its own revision. The
partial unique index `ux_rbjobs_active_kind` allows one queued or running job
per kind, so two concurrent enqueues of the same kind cannot both succeed.

Portable as written: partial indexes (`WHERE`) and `IN (...)` CHECKs run on
SQLite and PostgreSQL; the comments exist on PostgreSQL only. The downgrade
drops the table and its job history.

Revision ID: 0007_jobs
Revises: 0006_user_prefs
Create Date: 2026-10-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0007_jobs'
down_revision = '0006_user_prefs'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
ACTIVE = "rbjob_status IN ('queued', 'running')"


def _json():
    return sa.JSON(none_as_null=True).with_variant(
        postgresql.JSONB(none_as_null=True), 'postgresql')


def upgrade():
    op.create_table(
        'rbjobs',
        sa.Column('rbjob_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
                  autoincrement=True, nullable=False, comment='Job id'),
        sa.Column('rbjob_kind', sa.String(length=32), nullable=False,
                  comment='Registered job kind (app/jobs/registry.py)'),
        sa.Column('rbjob_params', _json(), nullable=False, server_default=sa.text("'{}'"),
                  comment='Parameters passed to the handler'),
        sa.Column('rbjob_status', sa.String(length=10), nullable=False,
                  server_default='queued', comment='queued, running, success or error'),
        sa.Column('rbjob_requested_by', sa.Integer(), nullable=True,
                  comment='User who queued the job; NULL for timers and the CLI'),
        sa.Column('rbjob_requested_at', sa.DateTime(), nullable=False,
                  comment='When the job was queued (UTC)'),
        sa.Column('rbjob_started_at', sa.DateTime(), nullable=True,
                  comment='When a runner claimed the job (UTC)'),
        sa.Column('rbjob_finished_at', sa.DateTime(), nullable=True,
                  comment='When the job ended or timed out (UTC)'),
        sa.Column('rbjob_result', _json(), nullable=True,
                  comment='Value returned by the handler'),
        sa.Column('rbjob_message', sa.String(length=300), nullable=True,
                  comment='Error message, or a short note'),
        sa.PrimaryKeyConstraint('rbjob_id', name='rbjobs_pkey'),
        sa.ForeignKeyConstraint(['rbjob_requested_by'], [f'{SCHEMA}.rbusers.id'],
                                name='rbjobs_requested_by_fk', ondelete='SET NULL'),
        sa.CheckConstraint("rbjob_kind IN ('heartbeat')", name='ck_rbjobs_kind'),
        sa.CheckConstraint("rbjob_status IN ('queued', 'running', 'success', 'error')",
                           name='ck_rbjobs_status'),
        schema=SCHEMA,
        comment='Background jobs: queue and results of the job runner',
    )
    op.create_index('ux_rbjobs_active_kind', 'rbjobs', ['rbjob_kind'], unique=True,
                    schema=SCHEMA, postgresql_where=sa.text(ACTIVE),
                    sqlite_where=sa.text(ACTIVE))
    op.create_index('ix_rbjobs_status_requested', 'rbjobs',
                    ['rbjob_status', 'rbjob_requested_at'], schema=SCHEMA)


def downgrade():
    op.drop_index('ix_rbjobs_status_requested', table_name='rbjobs', schema=SCHEMA)
    op.drop_index('ux_rbjobs_active_kind', table_name='rbjobs', schema=SCHEMA)
    op.drop_table('rbjobs', schema=SCHEMA)
