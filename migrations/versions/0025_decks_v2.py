"""decks v2: rbdeckheads and rbdeckversions

Spec S1 of F5-c (docs/requirements/F5/F5-c-decks-v2-data.md), F5-R5, D-F5-1.

`riftbound.rbdeckheads` holds one row per deck (owner `rbusers.id`, name unique per
user, game mode, visibility, share slug, current version, the legacy name it came
from); `riftbound.rbdeckversions` holds the versions of each deck (number, content v2
as JSON, note, the `rbdecks.id` it was copied from). New tables only: the revision
copies no data. `flask decks migrate [--dry-run]` copies the legacy decks afterwards
(docs/knowledge/ops-runbook.md, "Decks v2 migration"). rbdecks is not modified, neither
by the upgrade nor by the downgrade.

`rbdkh_current_version_id` has no foreign key (heads and versions would reference each
other); `rbdkv_legacy_id` has none either (`rbdecks` goes away in F11).

Data loss on downgrade: the downgrade drops both tables, so it drops every v2 deck and
version, including the ones copied by `flask decks migrate` (copy them again after an
upgrade) and anything saved in v2 since.

Revision ID: 0025_decks_v2
Revises: 0024_locations
Create Date: 2026-11-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0025_decks_v2'
down_revision = '0024_locations'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'


def upgrade():
    op.create_table(
        'rbdeckheads',
        sa.Column('rbdkh_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
                  autoincrement=True, nullable=False, comment='Deck id'),
        sa.Column('rbdkh_user_id', sa.Integer(), nullable=False, comment='Owner (rbusers.id)'),
        sa.Column('rbdkh_name', sa.String(length=80), nullable=False,
                  comment='Deck name, unique per user'),
        sa.Column('rbdkh_mode', sa.String(length=3), nullable=False,
                  comment='Game mode: 1v1 or 2v2'),
        sa.Column('rbdkh_visibility', sa.String(length=8), server_default='private',
                  nullable=False, comment='private or public'),
        sa.Column('rbdkh_share_slug', sa.String(length=24), nullable=True,
                  comment='Read-only share link slug (NULL = not shared)'),
        sa.Column('rbdkh_current_version_id', sa.BigInteger(), nullable=True,
                  comment='Current version (rbdeckversions.rbdkv_id)'),
        sa.Column('rbdkh_legacy_name', sa.String(length=200), nullable=True,
                  comment='rbdecks name it was migrated from (NULL = new)'),
        sa.Column('rbdkh_created_at', sa.DateTime(), nullable=False,
                  comment='When the deck was created (UTC)'),
        sa.Column('rbdkh_updated_at', sa.DateTime(), nullable=False, comment='Last change (UTC)'),
        sa.PrimaryKeyConstraint('rbdkh_id', name='rbdeckheads_pkey'),
        sa.ForeignKeyConstraint(['rbdkh_user_id'], [f'{SCHEMA}.rbusers.id'],
                                name='rbdeckheads_user_fk', ondelete='CASCADE'),
        sa.UniqueConstraint('rbdkh_user_id', 'rbdkh_name', name='rbdeckheads_user_name_uq'),
        sa.UniqueConstraint('rbdkh_share_slug', name='rbdeckheads_share_slug_uq'),
        sa.CheckConstraint("rbdkh_mode IN ('1v1', '2v2')", name='rbdeckheads_mode_chk'),
        sa.CheckConstraint("rbdkh_visibility IN ('private', 'public')",
                           name='rbdeckheads_visibility_chk'),
        schema=SCHEMA,
        comment='Decks v2: one row per deck (F5).',
    )
    op.create_table(
        'rbdeckversions',
        sa.Column('rbdkv_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
                  autoincrement=True, nullable=False, comment='Version id'),
        sa.Column('rbdkv_deck_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
                  nullable=False, comment='Deck (rbdeckheads.rbdkh_id)'),
        sa.Column('rbdkv_seq', sa.Integer(), nullable=False,
                  comment='Version number in the deck (1..n)'),
        sa.Column('rbdkv_content', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'),
                  nullable=False, comment='Content v2 (legend, champion, zones)'),
        sa.Column('rbdkv_note', sa.String(length=200), nullable=True,
                  comment='Free note (optional)'),
        sa.Column('rbdkv_legacy_id', sa.Integer(), nullable=True,
                  comment='rbdecks.id it was migrated from (NULL = new)'),
        sa.Column('rbdkv_created_at', sa.DateTime(), nullable=False,
                  comment='When the version was saved (UTC)'),
        sa.PrimaryKeyConstraint('rbdkv_id', name='rbdeckversions_pkey'),
        sa.ForeignKeyConstraint(['rbdkv_deck_id'], [f'{SCHEMA}.rbdeckheads.rbdkh_id'],
                                name='rbdeckversions_deck_fk', ondelete='CASCADE'),
        sa.UniqueConstraint('rbdkv_deck_id', 'rbdkv_seq', name='rbdeckversions_deck_seq_uq'),
        sa.UniqueConstraint('rbdkv_legacy_id', name='rbdeckversions_legacy_uq'),
        sa.CheckConstraint('rbdkv_seq >= 1', name='rbdeckversions_seq_chk'),
        schema=SCHEMA,
        comment='Decks v2: versions of each deck (F5).',
    )


def downgrade():
    op.drop_table('rbdeckversions', schema=SCHEMA)
    op.drop_table('rbdeckheads', schema=SCHEMA)
