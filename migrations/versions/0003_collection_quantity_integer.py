"""rbcollection.rbcol_quantity: Text -> Integer NOT NULL, CHECK >= 1

Specs QTY-1, decision D9 (+ reconciliation R6).

Pre-flight, in Python so it behaves the same on SQLite and PostgreSQL: every
value must be a whole number in 1..9999 once surrounding spaces are trimmed.
Otherwise the revision aborts BEFORE touching anything and lists the offending
`rbcol_id`s. The cast itself is `btrim(rbcol_quantity)::integer` on
PostgreSQL; SQLite rebuilds the table in batch mode (CAST). The CHECK
`rbcollection_quantity_chk` (`rbcol_quantity >= 1`) is added with the type.

downgrade() drops the CHECK and casts back to text (`::text`).

Revision ID: 0003_collection_quantity_integer
Revises: 0002_drop_legacy_tables
Create Date: 2026-10-18

"""
import re

from alembic import context, op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003_collection_quantity_integer'
down_revision = '0002_drop_legacy_tables'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
CHECK_NAME = 'rbcollection_quantity_chk'
QUANTITY_MIN, QUANTITY_MAX = 1, 9999
# ASCII digits and plain spaces only: exactly what PostgreSQL's btrim(...)::integer accepts.
_WHOLE_NUMBER = re.compile(r' *[0-9]+ *')


def _is_valid_quantity(value) -> bool:
    return (isinstance(value, str)
            and _WHOLE_NUMBER.fullmatch(value) is not None
            and QUANTITY_MIN <= int(value) <= QUANTITY_MAX)


def _offending_ids(bind):
    result = bind.execute(sa.text('SELECT rbcol_id, rbcol_quantity FROM riftbound.rbcollection'
                                  ' ORDER BY rbcol_id'))
    return [row.rbcol_id for row in result if not _is_valid_quantity(row.rbcol_quantity)]


def upgrade():
    if context.is_offline_mode():
        raise RuntimeError(
            f'{revision} validates the existing data first and cannot run in offline '
            '(--sql) mode. Run `flask db upgrade` against a live database.')

    bad = _offending_ids(op.get_bind())
    if bad:
        raise RuntimeError(
            f'rbcol_quantity must be a whole number in {QUANTITY_MIN}..{QUANTITY_MAX} '
            f'(offending rbcol_id): {", ".join(map(str, bad))}. '
            'Nothing was changed; fix or delete those lines and retry.')

    with op.batch_alter_table('rbcollection', schema=SCHEMA) as batch:
        batch.alter_column(
            'rbcol_quantity', existing_type=sa.Text(), type_=sa.Integer(),
            existing_nullable=False,
            postgresql_using='btrim(rbcol_quantity)::integer')
        batch.create_check_constraint(CHECK_NAME, 'rbcol_quantity >= 1')


def downgrade():
    with op.batch_alter_table('rbcollection', schema=SCHEMA) as batch:
        batch.drop_constraint(CHECK_NAME, type_='check')
        batch.alter_column(
            'rbcol_quantity', existing_type=sa.Integer(), type_=sa.Text(),
            existing_nullable=False,
            postgresql_using='rbcol_quantity::text')
