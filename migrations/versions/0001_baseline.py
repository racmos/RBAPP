"""baseline: the dev database as of 2026-10-18

Reproduces openspec/changes/f0-foundation/dev-schema-snapshot.txt (copy in
tests/fixtures/dev_schema_snapshot.txt): 16 tables, including the legacy
`old1_rbusers` / `old_rbdecks` and the wrong `rbdecks.fk_deck_user ->
old1_rbusers(rbus_username)`. 0002 repoints and drops them (D4).

The dev database is adopted with `flask db stamp 0001_baseline` (no DDL);
every other database is built by `flask db upgrade`. Column order, constraint
and index names and defaults follow the snapshot (D5). DDL is portable:
CHECKs are written as IN (...), BigInteger/JSONB have SQLite variants and the
partial index carries both `postgresql_where` and `sqlite_where`.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'

# bigint on PostgreSQL, plain INTEGER (rowid alias) on SQLite
BIGINT_PK = sa.BigInteger().with_variant(sa.Integer(), 'sqlite')
JSON_DOC = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')
NOW = sa.func.now()                       # DEFAULT now() / CURRENT_TIMESTAMP
CURRENT_TS = sa.text('CURRENT_TIMESTAMP')

# (table, serial column): PostgreSQL SERIAL names the sequence <table>_<col>_seq,
# exactly the names the dev database has.
LEGACY_USERS_SEQUENCE = 'rbusers_rbus_id_seq'


def _is_postgresql():
    return op.get_bind().dialect.name == 'postgresql'


def upgrade():
    # --- core --------------------------------------------------------------
    op.create_table(
        'rbset',
        sa.Column('rbset_id', sa.Text(), nullable=False),
        sa.Column('rbset_name', sa.Text(), nullable=False),
        sa.Column('rbset_ncard', sa.SmallInteger(), nullable=True),
        sa.Column('rbset_outdat', sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint('rbset_id', name='rbset_pk'),
        schema=SCHEMA,
    )

    op.create_table(
        'rbusers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=NOW, nullable=True),
        sa.PrimaryKeyConstraint('id', name='rbusers_pkey'),
        sa.UniqueConstraint('email', name='rbusers_email_key'),
        sa.UniqueConstraint('username', name='rbusers_username_key'),
        schema=SCHEMA,
    )

    op.create_table(
        'rbcards',
        sa.Column('rbcar_rbset_id', sa.Text(), nullable=False),
        sa.Column('rbcar_id', sa.Text(), nullable=False),
        sa.Column('rbcar_name', sa.Text(), nullable=False),
        sa.Column('rbcar_domain', sa.Text(), nullable=True),
        sa.Column('rbcar_type', sa.Text(), nullable=True),
        sa.Column('rbcar_tags', sa.Text(), nullable=True),
        sa.Column('rbcar_energy', sa.SmallInteger(), nullable=True),
        sa.Column('rbcar_power', sa.SmallInteger(), nullable=True),
        sa.Column('rbcar_might', sa.SmallInteger(), nullable=True),
        sa.Column('rbcar_ability', sa.Text(), nullable=True),
        sa.Column('rbcar_rarity', sa.Text(), nullable=True),
        sa.Column('rbcar_artist', sa.Text(), nullable=True),
        sa.Column('rbcar_banned', sa.Text(), server_default='N', nullable=True),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('image', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ['rbcar_rbset_id'], [f'{SCHEMA}.rbset.rbset_id'],
            name='rbcards_rbset_fk_1', onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('rbcar_rbset_id', 'rbcar_id', name='rbcards_pk'),
        schema=SCHEMA,
    )

    op.create_table(
        'rbcardmarket',
        sa.Column('rbcmk_snapshot', sa.DateTime(), server_default=NOW, nullable=False),
        sa.Column('rbcmk_rbset_id', sa.Text(), nullable=False),
        sa.Column('rbcmk_rbcar_id', sa.Text(), nullable=False),
        sa.Column('rbcmk_name', sa.Text(), nullable=False),
        sa.Column('rbcmk_foil', sa.Text(), server_default='N', nullable=False),
        sa.Column('rbcmk_price', sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(
            ['rbcmk_rbset_id', 'rbcmk_rbcar_id'],
            [f'{SCHEMA}.rbcards.rbcar_rbset_id', f'{SCHEMA}.rbcards.rbcar_id'],
            name='rbcmk_rbcar_fk_1', onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint(
            'rbcmk_snapshot', 'rbcmk_rbset_id', 'rbcmk_rbcar_id', 'rbcmk_foil',
            name='rbcmk_pk'),
        schema=SCHEMA,
    )

    op.create_table(
        'rbproducts',
        sa.Column('rbpdt_id_set', sa.Text(), nullable=False),
        sa.Column('rbpdt_id_product', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('rbpdt_name', sa.Text(), nullable=False),
        sa.Column('rbpdt_description', sa.Text(), nullable=True),
        sa.Column('rbpdt_type', sa.Text(), nullable=True),
        sa.Column('rbpdt_image_url', sa.Text(), nullable=True),
        sa.Column('rbpdt_image', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('rbpdt_id_set', 'rbpdt_id_product', name='rbproducts_pkey'),
        schema=SCHEMA,
    )

    # --- collection, legacy users, decks, legacy decks ----------------------
    op.create_table(
        'rbcollection',
        sa.Column('rbcol_rbset_id', sa.Text(), nullable=False),
        sa.Column('rbcol_rbcar_id', sa.Text(), nullable=False),
        sa.Column('rbcol_foil', sa.Text(), server_default='N', nullable=False),
        sa.Column('rbcol_quantity', sa.Text(), nullable=False),
        sa.Column('rbcol_chadat', sa.DateTime(), nullable=False),
        sa.Column('rbcol_user', sa.String(length=64), nullable=False),
        sa.Column('rbcol_selling', sa.Text(), server_default='N', nullable=True),
        sa.Column('rbcol_playset', sa.Integer(), nullable=True),
        sa.Column('rbcol_sell_price', sa.Numeric(), nullable=True),
        sa.Column('rbcol_condition', sa.String(length=8), nullable=True),
        sa.Column('rbcol_language', sa.String(length=40), nullable=True),
        sa.Column('rbcol_id', BIGINT_PK, autoincrement=True, nullable=False),
        sa.CheckConstraint(
            'rbcol_playset IS NULL OR rbcol_playset IN (1, 2, 3)',
            name='rbcollection_playset_chk'),
        sa.CheckConstraint(
            "rbcol_selling IN ('Y', 'N', 'S')", name='rbcollection_selling_chk'),
        sa.ForeignKeyConstraint(
            ['rbcol_rbset_id', 'rbcol_rbcar_id'],
            [f'{SCHEMA}.rbcards.rbcar_rbset_id', f'{SCHEMA}.rbcards.rbcar_id'],
            name='rbcollection_rbcar_fk_1', onupdate='CASCADE', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['rbcol_user'], [f'{SCHEMA}.rbusers.username'],
            name='rbcollection_user_fk_1', onupdate='CASCADE', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('rbcol_id', name='rbcollection_pk'),
        schema=SCHEMA,
    )
    op.create_index('idx_rbcollection_selling', 'rbcollection',
                    ['rbcol_user', 'rbcol_selling'], schema=SCHEMA)
    op.create_index('idx_rbcollection_user_card_foil', 'rbcollection',
                    ['rbcol_user', 'rbcol_rbset_id', 'rbcol_rbcar_id', 'rbcol_foil'],
                    schema=SCHEMA)

    # Legacy users table (renamed from `rbusers` in dev). Created BEFORE rbdecks
    # because the wrong FK `rbdecks.fk_deck_user` points at it.
    pg = _is_postgresql()
    if pg:
        op.execute(f'CREATE SEQUENCE {SCHEMA}.{LEGACY_USERS_SEQUENCE} AS integer')
    op.create_table(
        'old1_rbusers',
        sa.Column(
            'rbus_id', sa.Integer(), nullable=False, autoincrement=not pg,
            server_default=(
                sa.text(f"nextval('{SCHEMA}.{LEGACY_USERS_SEQUENCE}'::regclass)")
                if pg else None)),
        sa.Column('rbus_username', sa.String(length=80), nullable=False),
        sa.Column('rbus_email', sa.String(length=120), nullable=False),
        sa.Column('rbus_password', sa.String(length=256), nullable=False),
        sa.Column('rbus_created', sa.DateTime(), server_default=CURRENT_TS, nullable=True),
        sa.Column('rbus_updated', sa.DateTime(), server_default=CURRENT_TS, nullable=True),
        sa.PrimaryKeyConstraint('rbus_id', name='rbusers_pkey1'),
        sa.UniqueConstraint('rbus_email', name='rbusers_rbus_email_key'),
        sa.UniqueConstraint('rbus_username', name='rbusers_rbus_username_key'),
        schema=SCHEMA,
    )
    if pg:
        op.execute(
            f'ALTER SEQUENCE {SCHEMA}.{LEGACY_USERS_SEQUENCE} '
            f'OWNED BY {SCHEMA}.old1_rbusers.rbus_id')
    op.create_index('idx_rbusers_email', 'old1_rbusers', ['rbus_email'], schema=SCHEMA)
    op.create_index('idx_rbusers_username', 'old1_rbusers', ['rbus_username'], schema=SCHEMA)

    op.create_table(
        'rbdecks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rbdck_user', sa.String(length=80), nullable=False),
        sa.Column('rbdck_name', sa.String(length=200), nullable=False),
        sa.Column('rbdck_seq', sa.Integer(), server_default=sa.text('1'), nullable=True),
        sa.Column('rbdck_snapshot', sa.DateTime(), server_default=CURRENT_TS, nullable=False),
        sa.Column('rbdck_description', sa.Text(), nullable=True),
        sa.Column('rbdck_mode', sa.String(length=50), server_default='1v1', nullable=True),
        sa.Column('rbdck_format', sa.String(length=50), server_default='Standard', nullable=True),
        sa.Column('rbdck_max_set', sa.String(length=100), nullable=True),
        sa.Column('rbdck_ncards', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('rbdck_orden', sa.Numeric(), nullable=True),
        sa.Column('rbdck_cards', JSON_DOC, nullable=True),
        sa.ForeignKeyConstraint(
            ['rbdck_user'], [f'{SCHEMA}.old1_rbusers.rbus_username'], name='fk_deck_user'),
        sa.PrimaryKeyConstraint('id', name='rbdecks_pkey'),
        sa.UniqueConstraint(
            'rbdck_user', 'rbdck_name', 'rbdck_seq',
            name='rbdecks_rbdck_user_rbdck_name_rbdck_seq_key'),
        schema=SCHEMA,
    )

    op.create_table(
        'old_rbdecks',
        sa.Column('rbdck_snapshot', sa.DateTime(), server_default=NOW, nullable=False),
        sa.Column('rbdck_name', sa.Text(), nullable=False),
        sa.Column('rbdck_decription', sa.Text(), nullable=True),   # sic, as in dev
        sa.Column('rbdck_mode', sa.Text(), server_default='1v1', nullable=False),
        sa.Column('rbdck_format', sa.Text(), server_default='Standard', nullable=False),
        sa.Column('rbdck_max_set', sa.Text(), nullable=False),
        sa.Column('rbdck_rbset_id', sa.Text(), nullable=False),
        sa.Column('rbdck_rbcar_id', sa.Text(), nullable=False),
        sa.Column('rbdck_ncards', sa.Numeric(), server_default=sa.text('1'), nullable=False),
        sa.Column('rbdck_sideboard', sa.Text(), server_default='N', nullable=False),
        sa.Column('rbdck_user', sa.Text(), nullable=False),
        sa.Column('rbdck_orden', sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(
            ['rbdck_rbset_id', 'rbdck_rbcar_id'],
            [f'{SCHEMA}.rbcards.rbcar_rbset_id', f'{SCHEMA}.rbcards.rbcar_id'],
            name='rbdck_rbcar_fk_1', onupdate='CASCADE', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['rbdck_user'], [f'{SCHEMA}.rbusers.username'],
            name='rbdecks_user_fk_1', onupdate='CASCADE', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint(
            'rbdck_snapshot', 'rbdck_rbset_id', 'rbdck_rbcar_id', 'rbdck_sideboard',
            'rbdck_user', name='rbdck_pk'),
        schema=SCHEMA,
    )

    # --- Cardmarket (rbcm_*): deliberately no FKs, as in dev ----------------
    op.create_table(
        'rbcm_categories',
        sa.Column('rbcat_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rbcat_name', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('rbcat_id', name='rbcm_categories_pkey'),
        schema=SCHEMA,
    )

    op.create_table(
        'rbcm_expansions',
        sa.Column('rbexp_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rbexp_name', sa.Text(), nullable=True),
        sa.Column('rbexp_rbset_id', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('rbexp_id', name='rbcm_expansions_pkey'),
        schema=SCHEMA,
    )
    op.create_index(
        'idx_rbcm_expansions_unmapped', 'rbcm_expansions', ['rbexp_rbset_id'],
        schema=SCHEMA,
        postgresql_where=sa.text('rbexp_rbset_id IS NULL'),
        sqlite_where=sa.text('rbexp_rbset_id IS NULL'))

    op.create_table(
        'rbcm_ignored',
        sa.Column('rbig_id_product', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('rbig_name', sa.Text(), nullable=False),
        sa.Column('rbig_ignored_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('rbig_id_product', 'rbig_name', name='rbcm_ignored_pkey'),
        schema=SCHEMA,
    )
    op.create_index('idx_rbcm_ignored_id', 'rbcm_ignored', ['rbig_id_product'], schema=SCHEMA)

    op.create_table(
        'rbcm_load_history',
        sa.Column('rblh_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rblh_date', sa.Text(), nullable=False),
        sa.Column('rblh_file_type', sa.Text(), nullable=False),
        sa.Column('rblh_hash', sa.Text(), nullable=False),
        sa.Column('rblh_rows', sa.Integer(), nullable=True),
        sa.Column('rblh_status', sa.Text(), nullable=True),
        sa.Column('rblh_message', sa.Text(), nullable=True),
        sa.Column('rblh_loaded_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('rblh_id', name='rbcm_load_history_pkey'),
        schema=SCHEMA,
    )

    op.create_table(
        'rbcm_price',
        sa.Column('rbprc_date', sa.Text(), nullable=False),
        sa.Column('rbprc_id_product', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('rbprc_id_category', sa.Integer(), nullable=True),
        sa.Column('rbprc_avg', sa.Numeric(), nullable=True),
        sa.Column('rbprc_low', sa.Numeric(), nullable=True),
        sa.Column('rbprc_trend', sa.Numeric(), nullable=True),
        sa.Column('rbprc_avg1', sa.Numeric(), nullable=True),
        sa.Column('rbprc_avg7', sa.Numeric(), nullable=True),
        sa.Column('rbprc_avg30', sa.Numeric(), nullable=True),
        sa.Column('rbprc_avg_foil', sa.Numeric(), nullable=True),
        sa.Column('rbprc_low_foil', sa.Numeric(), nullable=True),
        sa.Column('rbprc_trend_foil', sa.Numeric(), nullable=True),
        sa.Column('rbprc_avg1_foil', sa.Numeric(), nullable=True),
        sa.Column('rbprc_avg7_foil', sa.Numeric(), nullable=True),
        sa.Column('rbprc_avg30_foil', sa.Numeric(), nullable=True),
        sa.Column('rbprc_low_ex', sa.Numeric(), nullable=True),
        sa.PrimaryKeyConstraint('rbprc_date', 'rbprc_id_product', name='rbcm_price_pkey'),
        schema=SCHEMA,
    )

    op.create_table(
        'rbcm_product_card_map',
        sa.Column('rbpcm_id_product', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rbpcm_rbset_id', sa.Text(), nullable=False),
        sa.Column('rbpcm_rbcar_id', sa.Text(), nullable=False),
        sa.Column('rbpcm_match_type', sa.Text(), nullable=True),
        sa.Column('rbpcm_confidence', sa.Numeric(), nullable=True),
        sa.Column('rbpcm_foil', sa.String(length=1), nullable=True),
        sa.CheckConstraint(
            "rbpcm_foil IS NULL OR rbpcm_foil IN ('N', 'S')", name='rbcm_pcm_foil_chk'),
        sa.PrimaryKeyConstraint('rbpcm_id_product', name='rbcm_product_card_map_pkey'),
        schema=SCHEMA,
    )
    op.create_index(
        'idx_rbcm_pcm_card_foil', 'rbcm_product_card_map',
        ['rbpcm_rbset_id', 'rbpcm_rbcar_id', 'rbpcm_foil'], schema=SCHEMA)

    op.create_table(
        'rbcm_products',
        sa.Column('rbprd_date', sa.Text(), nullable=False),
        sa.Column('rbprd_id_product', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('rbprd_name', sa.Text(), nullable=False),
        sa.Column('rbprd_id_category', sa.Integer(), nullable=True),
        sa.Column('rbprd_category_name', sa.Text(), nullable=True),
        sa.Column('rbprd_id_expansion', sa.Integer(), nullable=True),
        sa.Column('rbprd_id_metacard', sa.Integer(), nullable=True),
        sa.Column('rbprd_date_added', sa.Text(), nullable=True),
        sa.Column('rbprd_type', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('rbprd_date', 'rbprd_id_product', name='rbcm_products_pkey'),
        schema=SCHEMA,
    )


def downgrade():
    # Reverse dependency order. Indexes and owned sequences go with their table.
    for table in (
        'rbcm_products', 'rbcm_product_card_map', 'rbcm_price', 'rbcm_load_history',
        'rbcm_ignored', 'rbcm_expansions', 'rbcm_categories',
        'old_rbdecks', 'rbdecks', 'old1_rbusers', 'rbcollection',
        'rbproducts', 'rbcardmarket', 'rbcards', 'rbusers', 'rbset',
    ):
        op.drop_table(table, schema=SCHEMA)
    if _is_postgresql():
        op.execute(f'DROP SEQUENCE IF EXISTS {SCHEMA}.{LEGACY_USERS_SEQUENCE}')
