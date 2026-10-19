"""interface preferences: rbuserprefs

Spec PREF-1 / D6 of change f1-app-shell.

`riftbound.rbuserprefs` holds the interface preferences of one account, 1:1
with `rbusers`. Rows are created lazily on the first PATCH /me/prefs, so
existing users need nothing. Every preference column is nullable and NULL
means Auto (the client decides). The domains are named CHECK constraints; a
NULL passes a CHECK. The foreign key cascades, so deleting a user removes the
row.

Portable as written: `IN (...)` and `BETWEEN` CHECKs run on SQLite and
PostgreSQL. SQLite does not enforce the cascade unless PRAGMA foreign_keys is
on, which the app never does; the cascade is tested on PostgreSQL.

Revision ID: 0006_user_prefs
Revises: 0005_login_protection
Create Date: 2026-10-19

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0006_user_prefs'
down_revision = '0005_login_protection'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'


def upgrade():
    op.create_table(
        'rbuserprefs',
        sa.Column('rbprf_user_id', sa.Integer(), nullable=False),
        sa.Column('rbprf_lang', sa.String(length=2), nullable=True),
        sa.Column('rbprf_density', sa.String(length=10), nullable=True),
        sa.Column('rbprf_accent', sa.String(length=10), nullable=True),
        sa.Column('rbprf_bg_intensity', sa.SmallInteger(), nullable=True),
        sa.Column('rbprf_collection_view', sa.String(length=10), nullable=True),
        sa.Column('rbprf_updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('rbprf_user_id', name='rbuserprefs_pkey'),
        sa.ForeignKeyConstraint(['rbprf_user_id'], [f'{SCHEMA}.rbusers.id'],
                                name='rbuserprefs_user_fk', ondelete='CASCADE'),
        sa.CheckConstraint("rbprf_lang IN ('es', 'en')", name='rbuserprefs_lang_chk'),
        sa.CheckConstraint("rbprf_density IN ('compact', 'regular', 'comfy')",
                           name='rbuserprefs_density_chk'),
        sa.CheckConstraint("rbprf_accent IN ('cyan', 'orange')", name='rbuserprefs_accent_chk'),
        sa.CheckConstraint('rbprf_bg_intensity BETWEEN 0 AND 100',
                           name='rbuserprefs_bg_intensity_chk'),
        sa.CheckConstraint("rbprf_collection_view IN ('table', 'grid')",
                           name='rbuserprefs_collection_view_chk'),
        schema=SCHEMA,
    )


def downgrade():
    op.drop_table('rbuserprefs', schema=SCHEMA)
