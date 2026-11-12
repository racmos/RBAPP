"""legacy schema cleanup: drop rbdecks and the legacy columns

F11-f (D-F11-9, owner decision 2026-11-12). Drops what nothing reads any more:

- the table `rbdecks` (legacy decks; every deck lives in `rbdeckheads` / `rbdeckversions`
  since F5-c, and `flask decks migrate` is gone);
- `rbcollection.rbcol_playset` and its CHECK `rbcollection_playset_chk` (replaced by
  `rbuserprefs.rbprf_playset_size` and `rbkeepplayset`, F3-a);
- `rbcards.rbcar_banned` (bans live in `rbcardbans`, F2-a);
- `rbuserprefs.rbprf_lang` and its CHECK `rbuserprefs_lang_chk` (the app is English-only);
- the decks v2 provenance fields `rbdeckheads.rbdkh_legacy_name` and
  `rbdeckversions.rbdkv_legacy_id` with its unique constraint `rbdeckversions_legacy_uq`.

`rbcollection.rbcol_selling` stays (collection reads and writes use it).

Data loss on upgrade: every `rbdecks` row and every value of the five dropped columns is
lost. No data is converted (a production data reset follows). Take a backup first
(`scripts/db_backup.py`, docs/migrations.md) and restart the app right after the upgrade:
the previous code reads the dropped columns.

Downgrade: the downgrade restores the structure only. It re-creates `rbdecks` empty, with
the columns, primary key, unique constraint and owner foreign key it had after
0002_drop_legacy_tables (`fk_deck_user` -> `rbusers.username`, ON UPDATE CASCADE ON DELETE
RESTRICT), and adds the five columns back with their types, defaults, comments, CHECKs and
unique constraint. Existing rows get NULL in them (`rbcar_banned` its column default 'N');
the dropped values never come back.

Portable: column drops and adds run in batch mode (SQLite rebuilds the table, PostgreSQL
alters it in place).

Revision ID: 0028_legacy_schema_cleanup
Revises: 0027_jobs_price_alerts
Create Date: 2026-11-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0028_legacy_schema_cleanup'
down_revision = '0027_jobs_price_alerts'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
JSON_DOC = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def upgrade():
    op.drop_table('rbdecks', schema=SCHEMA)

    with op.batch_alter_table('rbcollection', schema=SCHEMA) as batch:
        batch.drop_constraint('rbcollection_playset_chk', type_='check')
        batch.drop_column('rbcol_playset')

    with op.batch_alter_table('rbcards', schema=SCHEMA) as batch:
        batch.drop_column('rbcar_banned')

    with op.batch_alter_table('rbuserprefs', schema=SCHEMA) as batch:
        batch.drop_constraint('rbuserprefs_lang_chk', type_='check')
        batch.drop_column('rbprf_lang')

    with op.batch_alter_table('rbdeckversions', schema=SCHEMA) as batch:
        batch.drop_constraint('rbdeckversions_legacy_uq', type_='unique')
        batch.drop_column('rbdkv_legacy_id')

    with op.batch_alter_table('rbdeckheads', schema=SCHEMA) as batch:
        batch.drop_column('rbdkh_legacy_name')


def downgrade():
    with op.batch_alter_table('rbdeckheads', schema=SCHEMA) as batch:
        batch.add_column(sa.Column(
            'rbdkh_legacy_name', sa.String(length=200), nullable=True,
            comment='rbdecks name it was migrated from (NULL = new)'))

    with op.batch_alter_table('rbdeckversions', schema=SCHEMA) as batch:
        batch.add_column(sa.Column(
            'rbdkv_legacy_id', sa.Integer(), nullable=True,
            comment='rbdecks.id it was migrated from (NULL = new)'))
        batch.create_unique_constraint('rbdeckversions_legacy_uq', ['rbdkv_legacy_id'])

    with op.batch_alter_table('rbuserprefs', schema=SCHEMA) as batch:
        batch.add_column(sa.Column('rbprf_lang', sa.String(length=2), nullable=True))
        batch.create_check_constraint('rbuserprefs_lang_chk', "rbprf_lang IN ('es', 'en')")

    with op.batch_alter_table('rbcards', schema=SCHEMA) as batch:
        batch.add_column(sa.Column(
            'rbcar_banned', sa.Text(), server_default='N', nullable=True,
            comment='Si ha sido baneada para jugarse en competitivo, S o N'))

    with op.batch_alter_table('rbcollection', schema=SCHEMA) as batch:
        batch.add_column(sa.Column(
            'rbcol_playset', sa.Integer(), nullable=True,
            comment='Nº de copias reservadas para playset (1, 2 o 3)'))
        batch.create_check_constraint(
            'rbcollection_playset_chk', 'rbcol_playset IS NULL OR rbcol_playset IN (1, 2, 3)')

    op.create_table(
        'rbdecks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rbdck_user', sa.String(length=80), nullable=False),
        sa.Column('rbdck_name', sa.String(length=200), nullable=False),
        sa.Column('rbdck_seq', sa.Integer(), server_default=sa.text('1'), nullable=True),
        sa.Column('rbdck_snapshot', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'),
                  nullable=False),
        sa.Column('rbdck_description', sa.Text(), nullable=True),
        sa.Column('rbdck_mode', sa.String(length=50), server_default='1v1', nullable=True),
        sa.Column('rbdck_format', sa.String(length=50), server_default='Standard', nullable=True),
        sa.Column('rbdck_max_set', sa.String(length=100), nullable=True),
        sa.Column('rbdck_ncards', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('rbdck_orden', sa.Numeric(), nullable=True),
        sa.Column('rbdck_cards', JSON_DOC, nullable=True),
        sa.ForeignKeyConstraint(
            ['rbdck_user'], [f'{SCHEMA}.rbusers.username'], name='fk_deck_user',
            onupdate='CASCADE', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name='rbdecks_pkey'),
        sa.UniqueConstraint(
            'rbdck_user', 'rbdck_name', 'rbdck_seq',
            name='rbdecks_rbdck_user_rbdck_name_rbdck_seq_key'),
        schema=SCHEMA,
    )
