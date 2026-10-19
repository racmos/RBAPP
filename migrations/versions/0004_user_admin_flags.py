"""rbusers.is_admin and rbusers.is_blocked

Specs ACL-1, ACL-2, decision D10 (+ reconciliation R1).

Two BOOLEAN NOT NULL columns with a false server default, so every existing
row is valid straight away (nobody becomes admin, nobody is blocked). The
first admin is made by the operator with `flask users promote <username>`;
no migration, env var or registration input ever does it.

`is_blocked` is stored negated on purpose: the model exposes
`User.is_active = not is_blocked`, the attribute Flask-Login reads, without a
column that shadows it.

Revision ID: 0004_user_admin_flags
Revises: 0003_collection_quantity_integer
Create Date: 2026-10-19

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004_user_admin_flags'
down_revision = '0003_collection_quantity_integer'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'


def upgrade():
    with op.batch_alter_table('rbusers', schema=SCHEMA) as batch:
        batch.add_column(sa.Column('is_admin', sa.Boolean(), nullable=False,
                                   server_default=sa.false()))
        batch.add_column(sa.Column('is_blocked', sa.Boolean(), nullable=False,
                                   server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('rbusers', schema=SCHEMA) as batch:
        batch.drop_column('is_blocked')
        batch.drop_column('is_admin')
