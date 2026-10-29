"""snapshot products value: rbvaluesnaps.rbvsn_products_value

Spec S2 of F14-c (docs/requirements/F14/F14-c-owned-products-api.md).

Adds `rbvaluesnaps.rbvsn_products_value NUMERIC(12,2) NULL`: the value of the
user's sealed products that day, kept apart from `rbvsn_value` (cards). Rows taken
before this revision keep NULL; no data loss on upgrade.

Data loss on downgrade: the downgrade drops the column and its values (every
products value stored by the snapshots so far); the history cannot be rebuilt later.

Revision ID: 0022_snapshot_products_value
Revises: 0021_user_products
Create Date: 2026-10-28

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0022_snapshot_products_value'
down_revision = '0021_user_products'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'


def upgrade():
    with op.batch_alter_table('rbvaluesnaps', schema=SCHEMA) as batch:
        batch.add_column(sa.Column('rbvsn_products_value', sa.Numeric(12, 2), nullable=True,
                                   comment='Sum of price x quantity over the priced product '
                                           'lines; NULL when the user has no products'))


def downgrade():
    with op.batch_alter_table('rbvaluesnaps', schema=SCHEMA) as batch:
        batch.drop_column('rbvsn_products_value')
