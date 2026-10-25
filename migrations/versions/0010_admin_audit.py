"""admin audit: rbadminaudit

Spec S4 of F13-a (docs/requirements/F13/F13-a-admin-foundation.md).

`riftbound.rbadminaudit` holds one row per admin action (F13-R2): the actor
(id + username, denormalised), a dotted action name, the target and a small
JSON summary. The row is written by `app.services.audit.record` inside the
same transaction as the change. Deleting the user sets `rbaud_actor_id` to
NULL; the username stays.

No data loss on upgrade (a new table only). The downgrade drops the table:
downgrade loses the whole audit history.

Revision ID: 0010_admin_audit
Revises: 0009_card_bans
Create Date: 2026-10-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0010_admin_audit'
down_revision = '0009_card_bans'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'


def _json():
    return sa.JSON(none_as_null=True).with_variant(
        postgresql.JSONB(none_as_null=True), 'postgresql')


def upgrade():
    op.create_table(
        'rbadminaudit',
        sa.Column('rbaud_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
                  autoincrement=True, nullable=False, comment='Audit row id'),
        sa.Column('rbaud_actor_id', sa.Integer(), nullable=True,
                  comment='User who acted; NULL for system jobs'),
        sa.Column('rbaud_actor_username', sa.String(length=64), nullable=False,
                  comment='Username at the time of the action ("system" for jobs)'),
        sa.Column('rbaud_action', sa.String(length=48), nullable=False,
                  comment='Dotted lowercase action, e.g. set.create'),
        sa.Column('rbaud_target_type', sa.String(length=24), nullable=False,
                  comment='Kind of target: set, card, user, ...'),
        sa.Column('rbaud_target_id', sa.String(length=64), nullable=True,
                  comment='Identifier of the target, when it has one'),
        sa.Column('rbaud_details', _json(), nullable=True,
                  comment='Small JSON summary of the change (old/new values)'),
        sa.Column('rbaud_created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now(), comment='When the action happened (UTC)'),
        sa.PrimaryKeyConstraint('rbaud_id', name='rbadminaudit_pkey'),
        sa.ForeignKeyConstraint(['rbaud_actor_id'], [f'{SCHEMA}.rbusers.id'],
                                name='rbadminaudit_actor_fk', ondelete='SET NULL'),
        schema=SCHEMA,
        comment='Audit trail of admin actions (F13)',
    )
    op.create_index('idx_rbadminaudit_created', 'rbadminaudit', ['rbaud_created_at'],
                    schema=SCHEMA)
    op.create_index('idx_rbadminaudit_target', 'rbadminaudit',
                    ['rbaud_target_type', 'rbaud_target_id'], schema=SCHEMA)


def downgrade():
    op.drop_index('idx_rbadminaudit_target', table_name='rbadminaudit', schema=SCHEMA)
    op.drop_index('idx_rbadminaudit_created', table_name='rbadminaudit', schema=SCHEMA)
    op.drop_table('rbadminaudit', schema=SCHEMA)
