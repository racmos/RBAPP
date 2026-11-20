"""products: the owner's product kinds taxonomy (2026-11-20)

The stored kinds of `rbproducts.rbpdt_kind` follow the Cardmarket categories the owner uses:
`booster` (Booster), `booster_box` (Booster Boxes / Display; a case is a booster box too),
`champion_deck` (Champion Decks; also the Trial Decks of Box Sets), `sealed_box_set` (Box Sets),
`accessory` (every accessory category; the Cardmarket category name stays in `rbpdt_category`)
and `other` (an unknown category). Cardmarket's Sets (`RB Set`) and Sealed Products are not used:
they never get a kind (`refresh_products` skips them), and singles (`card`) are never stored.

Upgrade: the old CHECK is dropped, the stored kinds are renamed (box -> booster_box, case ->
booster_box, starter -> champion_deck, bundle -> sealed_box_set, sleeves -> accessory; booster,
accessory, other and NULL unchanged; locked kinds are renamed the same way, the lock stays) and
the new CHECK `rbproducts_kind_chk` allows only the new kinds. The column comment follows.

Downgrade: the reverse rename (booster_box -> box, champion_deck -> starter, sealed_box_set ->
bundle) and the old CHECK. Not restorable: a former `case` comes back as `box` and former
`sleeves` stay `accessory` (the upgrade merged them).

Portable: SQLite (batch mode, the table is recreated) and PostgreSQL 18 (plain ALTER TABLE).
The UPDATE runs between the two batches, while no kind CHECK exists.

Revision ID: 0033_product_kinds
Revises: 0032_api_keys
Create Date: 2026-11-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0033_product_kinds'
down_revision = '0032_api_keys'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
TABLE = 'rbproducts'
CHECK_NAME = 'rbproducts_kind_chk'
# Frozen copies of PRODUCT_KINDS (app/models/cardmarket.py) before and after this revision.
KINDS_BEFORE = ('booster', 'box', 'case', 'bundle', 'starter', 'sleeves', 'accessory', 'other')
KINDS_AFTER = ('booster', 'booster_box', 'champion_deck', 'sealed_box_set', 'accessory', 'other')
UPGRADE_MAP = {'box': 'booster_box', 'case': 'booster_box', 'starter': 'champion_deck',
               'bundle': 'sealed_box_set', 'sleeves': 'accessory'}
DOWNGRADE_MAP = {'booster_box': 'box', 'champion_deck': 'starter', 'sealed_box_set': 'bundle'}
COMMENT_BEFORE = 'Product kind (booster, box, case, ...); NULL = not set'
COMMENT_AFTER = 'Product kind (booster, booster_box, champion_deck, ...); NULL = not set'


def _check(kinds):
    return f"rbpdt_kind IN ({', '.join(repr(k) for k in kinds)})"


def _rename(mapping):
    """One UPDATE: every row whose kind is a key of `mapping` gets its value."""
    table = sa.table(TABLE, sa.column('rbpdt_kind', sa.String(16)), schema=SCHEMA)
    op.execute(sa.update(table)
               .where(table.c.rbpdt_kind.in_(list(mapping)))
               .values(rbpdt_kind=sa.case(mapping, value=table.c.rbpdt_kind)))


def _switch(mapping, kinds, comment, old_comment):
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch:
        batch.drop_constraint(CHECK_NAME, type_='check')
    _rename(mapping)
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch:
        batch.alter_column('rbpdt_kind', existing_type=sa.String(16), existing_nullable=True,
                           comment=comment, existing_comment=old_comment)
        batch.create_check_constraint(CHECK_NAME, _check(kinds))


def upgrade():
    _switch(UPGRADE_MAP, KINDS_AFTER, COMMENT_AFTER, COMMENT_BEFORE)


def downgrade():
    _switch(DOWNGRADE_MAP, KINDS_BEFORE, COMMENT_BEFORE, COMMENT_AFTER)
