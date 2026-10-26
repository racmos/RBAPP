"""Index prices by product and date (F2-b S8).

The catalog reads the newest rows of a product first
(`price_summaries`); without the index that scan walks the whole table.

Revision ID: 0013_price_product_date_idx
Revises: 0012_jobs_riot_sync

No data change on upgrade; the downgrade drops the index.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '0013_price_product_date_idx'
down_revision = '0012_jobs_riot_sync'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
INDEX = 'idx_rbcm_price_product_date'


def upgrade():
    op.create_index(INDEX, 'rbcm_price', ['rbprc_id_product', 'rbprc_date'],
                    schema=SCHEMA)


def downgrade():
    op.drop_index(INDEX, table_name='rbcm_price', schema=SCHEMA)
