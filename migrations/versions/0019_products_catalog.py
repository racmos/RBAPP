"""products catalog: rbproducts keyed by the Cardmarket product id

Spec S2 of F14-a (docs/requirements/F14/F14-a-product-catalog-data.md).

`rbproducts` becomes the product catalog: the primary key `rbproducts_pkey` moves
from (`rbpdt_id_set`, `rbpdt_id_product`) to (`rbpdt_id_product`), `rbpdt_id_set`
becomes nullable (the set when the expansion is mapped), and the table gains
`rbpdt_category`, `rbpdt_kind` (CHECK `rbproducts_kind_chk`), `rbpdt_kind_locked`,
`rbpdt_set_locked`, `rbpdt_hidden` (false), `rbpdt_listed` (true) and
`rbpdt_updated_at`. Existing rows keep every value and get the defaults.

The upgrade refuses (RuntimeError, nothing changed) while a product id is in more
than one row: the new key would have to drop one of them.

Data loss on downgrade: the seven new columns and their values (category, kind,
locks, hidden, listed, updated at) are dropped. The downgrade refuses
(RuntimeError, nothing changed) while a row has no `rbpdt_id_set`, because the old
key needs one; set it or delete those rows first. Neither check can run in
offline (--sql) mode.

Revision ID: 0019_products_catalog
Revises: 0018_import_previews
Create Date: 2026-10-28

"""
from alembic import context, op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0019_products_catalog'
down_revision = '0018_import_previews'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
TABLE = 'rbproducts'
PK_NAME = 'rbproducts_pkey'
KIND_CHECK = 'rbproducts_kind_chk'
# Frozen copy of PRODUCT_KINDS (app/models/cardmarket.py) at this revision.
KINDS = ('booster', 'box', 'case', 'bundle', 'starter', 'sleeves', 'accessory', 'other')
NEW_COLUMNS = ('rbpdt_category', 'rbpdt_kind', 'rbpdt_kind_locked', 'rbpdt_set_locked',
               'rbpdt_hidden', 'rbpdt_listed', 'rbpdt_updated_at')


def _scalar(sql):
    if context.is_offline_mode():
        raise RuntimeError(
            f'{revision} checks rbproducts before changing its key and cannot run in '
            'offline (--sql) mode. Run `flask db upgrade` / `flask db downgrade` against a '
            'live database.')
    return op.get_bind().execute(sa.text(sql)).scalar_one()


def upgrade():
    duplicated = _scalar(
        f'SELECT COUNT(*) FROM (SELECT rbpdt_id_product FROM {SCHEMA}.{TABLE} '
        'GROUP BY rbpdt_id_product HAVING COUNT(*) > 1) AS d')
    if duplicated:
        raise RuntimeError(
            f'rbproducts holds {duplicated} product id(s) in more than one row; the new key '
            '(rbpdt_id_product) allows one. Nothing was changed; keep one row per id and retry.')

    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch:
        batch.drop_constraint(PK_NAME, type_='primary')
        batch.alter_column('rbpdt_id_set', existing_type=sa.Text(), nullable=True)
        batch.create_primary_key(PK_NAME, ['rbpdt_id_product'])
        batch.add_column(sa.Column('rbpdt_category', sa.Text(), nullable=True,
                                   comment='Cardmarket category name'))
        batch.add_column(sa.Column('rbpdt_kind', sa.String(16), nullable=True,
                                   comment='Product kind (booster, box, case, ...); '
                                           'NULL = not set'))
        batch.add_column(sa.Column('rbpdt_kind_locked', sa.Boolean(), nullable=False,
                                   server_default=sa.false(),
                                   comment='The refresh never changes the kind'))
        batch.add_column(sa.Column('rbpdt_set_locked', sa.Boolean(), nullable=False,
                                   server_default=sa.false(),
                                   comment='The refresh never changes the set'))
        batch.add_column(sa.Column('rbpdt_hidden', sa.Boolean(), nullable=False,
                                   server_default=sa.false(), comment='Hidden from the catalog'))
        batch.add_column(sa.Column('rbpdt_listed', sa.Boolean(), nullable=False,
                                   server_default=sa.true(),
                                   comment='In the latest Cardmarket non-singles file'))
        batch.add_column(sa.Column('rbpdt_updated_at', sa.DateTime(), nullable=True,
                                   comment='Last change by the refresh (UTC)'))
        batch.create_check_constraint(
            KIND_CHECK, f"rbpdt_kind IN ({', '.join(repr(k) for k in KINDS)})")


def downgrade():
    without_set = _scalar(f'SELECT COUNT(*) FROM {SCHEMA}.{TABLE} WHERE rbpdt_id_set IS NULL')
    if without_set:
        raise RuntimeError(
            f'rbproducts holds {without_set} product(s) without rbpdt_id_set; the '
            f'{down_revision} key (rbpdt_id_set, rbpdt_id_product) needs one. Nothing was '
            'changed; set it or delete them first '
            f'(DELETE FROM {SCHEMA}.{TABLE} WHERE rbpdt_id_set IS NULL) and retry.')

    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch:
        batch.drop_constraint(KIND_CHECK, type_='check')
        for column in reversed(NEW_COLUMNS):
            batch.drop_column(column)
        batch.drop_constraint(PK_NAME, type_='primary')
        batch.alter_column('rbpdt_id_set', existing_type=sa.Text(), nullable=False)
        batch.create_primary_key(PK_NAME, ['rbpdt_id_set', 'rbpdt_id_product'])
