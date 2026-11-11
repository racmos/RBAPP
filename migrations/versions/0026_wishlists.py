"""wishlists: rbwishlists, rbwishlistlines and rbwishlistalerts

F3-f-1 of the wishlists design (docs/requirements/F3/F3-f-wishlists-design.md, "Data
model", owner decisions 2026-11-11).

`riftbound.rbwishlists` holds the wishlists of each user (owner `rbusers.id`, name unique
per user ignoring case, the user's order, the default flag); `riftbound.rbwishlistlines`
holds the wanted cards of each list (card name key and name, an optional printing, the
foil wish, quantity 1..99, an optional max price for the daily alert, a note);
`riftbound.rbwishlistalerts` holds the price alerts raised for each user (card, price
reached, the max price, the day of the price update, read time). New tables only: the
revision copies no data and seeds no rows (the default list is created by the service).

Portable as written: the expression unique indexes (`lower(...)`, `coalesce(...)`) and
the partial indexes (`WHERE`) run on PostgreSQL and on SQLite (3.9+, the tests).
- `rbwishlists_user_name_uq`: `(user, lower(name))`, the name is unique per user
  ignoring case (like `rblocations_user_code_uq`).
- `rbwishlists_user_default_uq`: `(user) WHERE rbwls_is_default`, one default list per
  user (like `ux_rbjobs_active_kind`).
- `rbwishlistlines_target_uq`: `(list, name_key, coalesce(set, '*'), coalesce(card, '*'),
  foil)`. A by-name line has a NULL printing and NULLs never collide in a unique index,
  so the printing goes through `coalesce`; no stored target column is needed. The index
  leads with the list, so it also serves the cascade and the lines of a list.
- `rbwishlistalerts_target_uq`: `(user, name_key, coalesce(set, '*'), coalesce(card,
  '*'), price_date)`: one alert per user, card and day, so a re-run of the job the same
  day cannot duplicate it.
- `ix_rbwishlistalerts_user_unread`: `(user) WHERE rbwal_read_at IS NULL`.

Data loss on downgrade: the downgrade drops the three tables, so it drops every user's
wishlists, their lines and their alerts. No other table is touched.

Revision ID: 0026_wishlists
Revises: 0025_decks_v2
Create Date: 2026-11-11

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0026_wishlists'
down_revision = '0025_decks_v2'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
DEFAULT = 'rbwls_is_default'
UNREAD = 'rbwal_read_at IS NULL'


def _id():
    # BIGINT in PostgreSQL; INTEGER in SQLite, where only an INTEGER PRIMARY KEY autoincrements.
    return sa.BigInteger().with_variant(sa.Integer(), 'sqlite')


def upgrade():
    op.create_table(
        'rbwishlists',
        sa.Column('rbwls_id', _id(), autoincrement=True, nullable=False, comment='Wishlist id'),
        sa.Column('rbwls_user_id', sa.Integer(), nullable=False, comment='Owner (rbusers.id)'),
        sa.Column('rbwls_name', sa.String(length=80), nullable=False,
                  comment='List name, unique per user ignoring case'),
        sa.Column('rbwls_is_default', sa.Boolean(), server_default=sa.false(), nullable=False,
                  comment='Default list of the user (at most one per user)'),
        sa.Column('rbwls_position', sa.Integer(), nullable=False,
                  comment="Place in the user's order (1..n, unique per user)"),
        sa.Column('rbwls_created_at', sa.DateTime(), nullable=False,
                  comment='When the list was created (UTC)'),
        sa.Column('rbwls_updated_at', sa.DateTime(), nullable=False, comment='Last change (UTC)'),
        sa.PrimaryKeyConstraint('rbwls_id', name='rbwishlists_pkey'),
        sa.ForeignKeyConstraint(['rbwls_user_id'], [f'{SCHEMA}.rbusers.id'],
                                name='rbwishlists_user_fk', ondelete='CASCADE'),
        sa.CheckConstraint('length(trim(rbwls_name)) >= 1', name='rbwishlists_name_chk'),
        sa.CheckConstraint('rbwls_position >= 1', name='rbwishlists_position_chk'),
        sa.UniqueConstraint('rbwls_user_id', 'rbwls_position',
                            name='rbwishlists_user_position_uq'),
        schema=SCHEMA,
        comment='Wishlists of each user (F3-f).',
    )
    op.create_index('rbwishlists_user_name_uq', 'rbwishlists',
                    ['rbwls_user_id', sa.text('lower(rbwls_name)')], unique=True, schema=SCHEMA)
    op.create_index('rbwishlists_user_default_uq', 'rbwishlists', ['rbwls_user_id'],
                    unique=True, schema=SCHEMA, postgresql_where=sa.text(DEFAULT),
                    sqlite_where=sa.text(DEFAULT))
    op.create_table(
        'rbwishlistlines',
        sa.Column('rbwsl_id', _id(), autoincrement=True, nullable=False, comment='Line id'),
        sa.Column('rbwsl_list_id', _id(), nullable=False,
                  comment='Wishlist (rbwishlists.rbwls_id)'),
        sa.Column('rbwsl_name_key', sa.String(length=200), nullable=False,
                  comment='Normalised card name (name_key)'),
        sa.Column('rbwsl_name', sa.String(length=200), nullable=False,
                  comment='Card name as shown'),
        sa.Column('rbwsl_rbset_id', sa.Text(), nullable=True,
                  comment='Set of the wanted printing (NULL = any printing)'),
        sa.Column('rbwsl_rbcar_id', sa.Text(), nullable=True,
                  comment='Card number of the wanted printing (NULL = any printing)'),
        sa.Column('rbwsl_foil', sa.String(length=3), server_default='any', nullable=False,
                  comment='Foil wish: any, N (non-foil) or S (foil)'),
        sa.Column('rbwsl_qty', sa.SmallInteger(), server_default='1', nullable=False,
                  comment='Copies wanted (1..99)'),
        sa.Column('rbwsl_max_price', sa.Numeric(precision=10, scale=2), nullable=True,
                  comment='Alert at or below this price (NULL = never alerts)'),
        sa.Column('rbwsl_note', sa.String(length=200), nullable=True,
                  comment='Free note (optional)'),
        sa.Column('rbwsl_created_at', sa.DateTime(), nullable=False,
                  comment='When the line was added (UTC)'),
        sa.Column('rbwsl_updated_at', sa.DateTime(), nullable=False, comment='Last change (UTC)'),
        sa.PrimaryKeyConstraint('rbwsl_id', name='rbwishlistlines_pkey'),
        sa.ForeignKeyConstraint(['rbwsl_list_id'], [f'{SCHEMA}.rbwishlists.rbwls_id'],
                                name='rbwishlistlines_list_fk', ondelete='CASCADE'),
        sa.CheckConstraint('(rbwsl_rbset_id IS NULL) = (rbwsl_rbcar_id IS NULL)',
                           name='rbwishlistlines_printing_chk'),
        sa.CheckConstraint("rbwsl_foil IN ('any', 'N', 'S')", name='rbwishlistlines_foil_chk'),
        sa.CheckConstraint('rbwsl_qty BETWEEN 1 AND 99', name='rbwishlistlines_qty_chk'),
        sa.CheckConstraint('rbwsl_max_price IS NULL OR rbwsl_max_price >= 0',
                           name='rbwishlistlines_max_price_chk'),
        schema=SCHEMA,
        comment='Cards wanted in each wishlist (F3-f).',
    )
    op.create_index('rbwishlistlines_target_uq', 'rbwishlistlines',
                    ['rbwsl_list_id', 'rbwsl_name_key', sa.text("coalesce(rbwsl_rbset_id, '*')"),
                     sa.text("coalesce(rbwsl_rbcar_id, '*')"), 'rbwsl_foil'],
                    unique=True, schema=SCHEMA)
    op.create_index('ix_rbwishlistlines_name_key', 'rbwishlistlines', ['rbwsl_name_key'],
                    schema=SCHEMA)
    op.create_table(
        'rbwishlistalerts',
        sa.Column('rbwal_id', _id(), autoincrement=True, nullable=False, comment='Alert id'),
        sa.Column('rbwal_user_id', sa.Integer(), nullable=False, comment='Owner (rbusers.id)'),
        sa.Column('rbwal_name_key', sa.String(length=200), nullable=False,
                  comment='Normalised card name (name_key)'),
        sa.Column('rbwal_name', sa.String(length=200), nullable=False,
                  comment='Card name as shown'),
        sa.Column('rbwal_rbset_id', sa.Text(), nullable=True,
                  comment='Set of the printing (NULL = any printing)'),
        sa.Column('rbwal_rbcar_id', sa.Text(), nullable=True,
                  comment='Card number of the printing (NULL = any printing)'),
        sa.Column('rbwal_price', sa.Numeric(precision=10, scale=2), nullable=False,
                  comment='Price reached'),
        sa.Column('rbwal_max_price', sa.Numeric(precision=10, scale=2), nullable=False,
                  comment='Max price that raised the alert'),
        sa.Column('rbwal_price_date', sa.Date(), nullable=False,
                  comment='Day of the price update that raised it'),
        sa.Column('rbwal_created_at', sa.DateTime(), nullable=False,
                  comment='When the alert was raised (UTC)'),
        sa.Column('rbwal_read_at', sa.DateTime(), nullable=True,
                  comment='When the user read it (UTC); NULL = unread'),
        sa.PrimaryKeyConstraint('rbwal_id', name='rbwishlistalerts_pkey'),
        sa.ForeignKeyConstraint(['rbwal_user_id'], [f'{SCHEMA}.rbusers.id'],
                                name='rbwishlistalerts_user_fk', ondelete='CASCADE'),
        sa.CheckConstraint('(rbwal_rbset_id IS NULL) = (rbwal_rbcar_id IS NULL)',
                           name='rbwishlistalerts_printing_chk'),
        sa.CheckConstraint('rbwal_price >= 0 AND rbwal_max_price >= 0',
                           name='rbwishlistalerts_price_chk'),
        schema=SCHEMA,
        comment='Wishlist price alerts of each user (F3-f).',
    )
    op.create_index('rbwishlistalerts_target_uq', 'rbwishlistalerts',
                    ['rbwal_user_id', 'rbwal_name_key', sa.text("coalesce(rbwal_rbset_id, '*')"),
                     sa.text("coalesce(rbwal_rbcar_id, '*')"), 'rbwal_price_date'],
                    unique=True, schema=SCHEMA)
    op.create_index('ix_rbwishlistalerts_user_created', 'rbwishlistalerts',
                    ['rbwal_user_id', 'rbwal_created_at'], schema=SCHEMA)
    op.create_index('ix_rbwishlistalerts_user_unread', 'rbwishlistalerts', ['rbwal_user_id'],
                    schema=SCHEMA, postgresql_where=sa.text(UNREAD),
                    sqlite_where=sa.text(UNREAD))


def downgrade():
    op.drop_index('ix_rbwishlistalerts_user_unread', table_name='rbwishlistalerts',
                  schema=SCHEMA)
    op.drop_index('ix_rbwishlistalerts_user_created', table_name='rbwishlistalerts',
                  schema=SCHEMA)
    op.drop_index('rbwishlistalerts_target_uq', table_name='rbwishlistalerts', schema=SCHEMA)
    op.drop_table('rbwishlistalerts', schema=SCHEMA)
    op.drop_index('ix_rbwishlistlines_name_key', table_name='rbwishlistlines', schema=SCHEMA)
    op.drop_index('rbwishlistlines_target_uq', table_name='rbwishlistlines', schema=SCHEMA)
    op.drop_table('rbwishlistlines', schema=SCHEMA)
    op.drop_index('rbwishlists_user_default_uq', table_name='rbwishlists', schema=SCHEMA)
    op.drop_index('rbwishlists_user_name_uq', table_name='rbwishlists', schema=SCHEMA)
    op.drop_table('rbwishlists', schema=SCHEMA)
