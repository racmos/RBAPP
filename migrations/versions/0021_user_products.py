"""user products: rbuserproducts

Spec S1 of F14-c (docs/requirements/F14/F14-c-owned-products-api.md).

`riftbound.rbuserproducts` holds the sealed products each user owns (quantity,
optional purchase price and note). A new table only: no data loss on upgrade. A
product with owners cannot be deleted (`rbuserproducts_product_fk` is ON DELETE
RESTRICT); deleting a user deletes their lines.

Data loss on downgrade: the downgrade drops the table, so it drops every user's
products; they cannot be rebuilt from anything else.

Revision ID: 0021_user_products
Revises: 0020_jobs_products_refresh
Create Date: 2026-10-28

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0021_user_products'
down_revision = '0020_jobs_products_refresh'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'


def upgrade():
    op.create_table(
        'rbuserproducts',
        sa.Column('rbupr_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
                  autoincrement=True, nullable=False, comment='Line id'),
        sa.Column('rbupr_user_id', sa.Integer(), nullable=False, comment='User id'),
        sa.Column('rbupr_id_product', sa.Integer(), nullable=False,
                  comment='Cardmarket product id'),
        sa.Column('rbupr_quantity', sa.Integer(), nullable=False,
                  comment='Copies owned (1..9999)'),
        sa.Column('rbupr_purchase_price', sa.Numeric(10, 2), nullable=True,
                  comment='Unit purchase price (optional)'),
        sa.Column('rbupr_note', sa.String(length=200), nullable=True,
                  comment='Free note (optional)'),
        sa.Column('rbupr_created_at', sa.DateTime(), nullable=False,
                  comment='When the line was created (UTC)'),
        sa.Column('rbupr_updated_at', sa.DateTime(), nullable=False, comment='Last change (UTC)'),
        sa.PrimaryKeyConstraint('rbupr_id', name='rbuserproducts_pkey'),
        sa.ForeignKeyConstraint(['rbupr_user_id'], [f'{SCHEMA}.rbusers.id'],
                                name='rbuserproducts_user_fk', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rbupr_id_product'], [f'{SCHEMA}.rbproducts.rbpdt_id_product'],
                                name='rbuserproducts_product_fk', ondelete='RESTRICT'),
        sa.CheckConstraint('rbupr_quantity BETWEEN 1 AND 9999',
                           name='rbuserproducts_quantity_chk'),
        sa.CheckConstraint('rbupr_purchase_price IS NULL OR rbupr_purchase_price >= 0',
                           name='rbuserproducts_purchase_price_chk'),
        schema=SCHEMA,
        comment='Sealed products each user owns (F14).',
    )
    op.create_index('ix_rbuserproducts_user', 'rbuserproducts', ['rbupr_user_id'],
                    schema=SCHEMA)


def downgrade():
    op.drop_index('ix_rbuserproducts_user', table_name='rbuserproducts', schema=SCHEMA)
    op.drop_table('rbuserproducts', schema=SCHEMA)
