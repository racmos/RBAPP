"""collection: purchase price, copies to sell, no legacy 'S' selling value

Spec S2 of F3-a (docs/requirements/F3/F3-a-collection-data.md).

`rbcollection` gains `rbcol_purchase_price` (NUMERIC(10,2), NULL, never
negative) and `rbcol_sell_qty` (INTEGER NOT NULL DEFAULT 0, between 0 and
`rbcol_quantity`). The legacy selling value 'S' becomes 'Y' (D-F3-11) and
`rbcollection_selling_chk` allows only 'Y' and 'N'. `rbcol_sell_qty` is
back-filled from the old rules: `max(0, quantity - playset)` when `rbcol_playset`
is set, else `quantity` when the row is for sale, else 0. The number of rows
changed from 'S' to 'Y' is logged.

Data loss on downgrade: both columns and their CHECKs are dropped, so every
purchase price and copies-to-sell count is lost; rows that were 'S' stay 'Y'.

Revision ID: 0014_collection_selling
Revises: 0013_price_product_date_idx
Create Date: 2026-10-28

"""
import logging

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0014_collection_selling'
down_revision = '0013_price_product_date_idx'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
TABLE = 'rbcollection'
log = logging.getLogger('alembic.runtime.migration')


def upgrade():
    bind = op.get_bind()
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch:
        batch.add_column(sa.Column(
            'rbcol_purchase_price', sa.Numeric(10, 2), nullable=True,
            comment='Precio de compra unitario (opcional)'))
        batch.add_column(sa.Column(
            'rbcol_sell_qty', sa.Integer(), nullable=False, server_default='0',
            comment='Copias a la venta (0..quantity)'))

    changed = bind.execute(sa.text(
        f"UPDATE {SCHEMA}.{TABLE} SET rbcol_selling = 'Y' WHERE rbcol_selling = 'S'")).rowcount
    log.info('rbcollection rows S->Y: %s', changed)
    bind.execute(sa.text(
        f'UPDATE {SCHEMA}.{TABLE} SET rbcol_sell_qty = CASE '
        'WHEN rbcol_playset IS NOT NULL THEN '
        'CASE WHEN rbcol_quantity > rbcol_playset THEN rbcol_quantity - rbcol_playset ELSE 0 END '
        "WHEN rbcol_selling = 'Y' THEN rbcol_quantity ELSE 0 END"))

    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch:
        batch.drop_constraint('rbcollection_selling_chk', type_='check')
        batch.create_check_constraint('rbcollection_selling_chk', "rbcol_selling IN ('Y', 'N')")
        batch.create_check_constraint(
            'rbcollection_purchase_price_chk',
            'rbcol_purchase_price IS NULL OR rbcol_purchase_price >= 0')
        batch.create_check_constraint(
            'rbcollection_sell_qty_chk', 'rbcol_sell_qty BETWEEN 0 AND rbcol_quantity')


def downgrade():
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch:
        batch.drop_constraint('rbcollection_sell_qty_chk', type_='check')
        batch.drop_constraint('rbcollection_purchase_price_chk', type_='check')
        batch.drop_constraint('rbcollection_selling_chk', type_='check')
        batch.create_check_constraint(
            'rbcollection_selling_chk', "rbcol_selling IN ('Y', 'N', 'S')")
        batch.drop_column('rbcol_sell_qty')
        batch.drop_column('rbcol_purchase_price')
