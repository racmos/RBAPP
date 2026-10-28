"""value snapshots: rbvaluesnaps

Spec S1 of F4-c (docs/requirements/F4/F4-c-value-snapshots.md).

`riftbound.rbvaluesnaps` holds one row per user and day with the value of the
collection (written by the `value_snapshot` job). A new table only: no data loss
on upgrade. The downgrade drops the table, so every snapshot taken so far is
lost; the history cannot be rebuilt from the prices later.

Revision ID: 0016_value_snapshots
Revises: 0015_playset
Create Date: 2026-10-28

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0016_value_snapshots'
down_revision = '0015_playset'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'


def upgrade():
    op.create_table(
        'rbvaluesnaps',
        sa.Column('rbvsn_user_id', sa.Integer(), nullable=False, comment='User id'),
        sa.Column('rbvsn_date', sa.Date(), nullable=False, comment='Day of the snapshot (UTC)'),
        sa.Column('rbvsn_value', sa.Numeric(12, 2), nullable=False,
                  comment='Sum of market x quantity over the priced lines'),
        sa.Column('rbvsn_cost', sa.Numeric(12, 2), nullable=True,
                  comment='Sum of purchase price x quantity; NULL when no line has one'),
        sa.Column('rbvsn_qty', sa.Integer(), nullable=False, comment='Copies in the collection'),
        sa.Column('rbvsn_unique', sa.Integer(), nullable=False, comment='Distinct printings'),
        sa.Column('rbvsn_unpriced', sa.Integer(), nullable=False,
                  comment='Lines without a market price'),
        sa.Column('rbvsn_created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now(), comment='When the row was created (UTC)'),
        sa.PrimaryKeyConstraint('rbvsn_user_id', 'rbvsn_date', name='rbvaluesnaps_pkey'),
        sa.ForeignKeyConstraint(['rbvsn_user_id'], [f'{SCHEMA}.rbusers.id'],
                                name='rbvaluesnaps_user_fk', ondelete='CASCADE'),
        schema=SCHEMA,
        comment='Daily value of each user collection (F4).',
    )


def downgrade():
    op.drop_table('rbvaluesnaps', schema=SCHEMA)
