"""storage locations: rblocations and rbcollection_locations

Spec S1, S2 of F16-a (docs/requirements/F16/F16-a-locations-data.md).

`riftbound.rblocations` holds the places where a user keeps their cards (a code, a
description, the user's order, a lock and, from F16-e, the mounted deck);
`riftbound.rbcollection_locations` says how many copies of a collection line are in
each location. Copies of a line that are in no location are "unassigned": derived
(`rbcol_quantity` minus the line's location quantities), never stored. New tables
only: no data loss on upgrade.

The code is unique per user ignoring case: `rblocations_user_code_uq` is a unique
index on `(rbloc_user, lower(rbloc_code))`. Expression indexes exist on PostgreSQL
and on SQLite (3.9+, the tests), so the same DDL runs on both. The code CHECK
(`rblocations_code_chk`: 1-32 letters, digits or `-`) needs a regular expression on
PostgreSQL and `GLOB` on SQLite, so its text depends on the dialect.

`rbloc_deck_id` has no foreign key yet: decks v2 does not exist and the legacy
`rbdecks` stays untouched; F16-e adds the key.

Data loss on downgrade: the downgrade drops both tables, so it drops every user's
locations and the location quantities of every line; the collection lines and their
quantities stay.

Revision ID: 0024_locations
Revises: 0023_card_changes_obsolete
Create Date: 2026-11-03

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0024_locations'
down_revision = '0023_card_changes_obsolete'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
CODE_CHECKS = {
    'postgresql': "rbloc_code ~ '^[A-Za-z0-9-]{1,32}$'",
    'sqlite': "rbloc_code NOT GLOB '*[^A-Za-z0-9-]*' AND length(rbloc_code) BETWEEN 1 AND 32",
}


def upgrade():
    code_check = CODE_CHECKS.get(op.get_bind().dialect.name, CODE_CHECKS['postgresql'])
    op.create_table(
        'rblocations',
        sa.Column('rbloc_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
                  autoincrement=True, nullable=False, comment='Location id'),
        sa.Column('rbloc_user', sa.String(length=64), nullable=False,
                  comment='Owner (rbusers.username)'),
        sa.Column('rbloc_code', sa.String(length=32), nullable=False,
                  comment='Code: 1-32 letters, digits or -; unique per user ignoring case'),
        sa.Column('rbloc_description', sa.String(length=200), nullable=True,
                  comment='Description (optional)'),
        sa.Column('rbloc_position', sa.Integer(), nullable=False,
                  comment="Place in the user's order (1..n, unique per user)"),
        sa.Column('rbloc_locked', sa.Boolean(), server_default=sa.false(), nullable=False,
                  comment='Locked: skipped by automatic takes, quantities read-only'),
        sa.Column('rbloc_deck_id', sa.BigInteger(), nullable=True,
                  comment='Mounted deck (F16-e); NULL for an ordinary location'),
        sa.Column('rbloc_updated_at', sa.DateTime(), nullable=False, comment='Last change (UTC)'),
        sa.PrimaryKeyConstraint('rbloc_id', name='rblocations_pkey'),
        sa.ForeignKeyConstraint(['rbloc_user'], [f'{SCHEMA}.rbusers.username'],
                                name='rblocations_user_fk', onupdate='CASCADE',
                                ondelete='CASCADE'),
        sa.CheckConstraint(code_check, name='rblocations_code_chk'),
        sa.CheckConstraint('rbloc_position >= 1', name='rblocations_position_chk'),
        sa.UniqueConstraint('rbloc_user', 'rbloc_position', name='rblocations_user_position_uq'),
        sa.UniqueConstraint('rbloc_deck_id', name='rblocations_deck_uq'),
        schema=SCHEMA,
        comment='Storage locations of each user (F16).',
    )
    op.create_index('rblocations_user_code_uq', 'rblocations',
                    ['rbloc_user', sa.text('lower(rbloc_code)')], unique=True, schema=SCHEMA)
    op.create_table(
        'rbcollection_locations',
        sa.Column('rbcll_line_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
                  nullable=False, comment='Collection line (rbcollection.rbcol_id)'),
        sa.Column('rbcll_location_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
                  nullable=False, comment='Location (rblocations.rbloc_id)'),
        sa.Column('rbcll_qty', sa.Integer(), nullable=False,
                  comment='Copies of the line in the location'),
        sa.PrimaryKeyConstraint('rbcll_line_id', 'rbcll_location_id',
                                name='rbcollection_locations_pkey'),
        sa.ForeignKeyConstraint(['rbcll_line_id'], [f'{SCHEMA}.rbcollection.rbcol_id'],
                                name='rbcollection_locations_line_fk', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rbcll_location_id'], [f'{SCHEMA}.rblocations.rbloc_id'],
                                name='rbcollection_locations_location_fk', ondelete='CASCADE'),
        sa.CheckConstraint('rbcll_qty >= 1', name='rbcollection_locations_qty_chk'),
        schema=SCHEMA,
        comment='Copies of each collection line per location (F16).',
    )
    op.create_index('ix_rbcollection_locations_location', 'rbcollection_locations',
                    ['rbcll_location_id'], schema=SCHEMA)


def downgrade():
    op.drop_index('ix_rbcollection_locations_location', table_name='rbcollection_locations',
                  schema=SCHEMA)
    op.drop_table('rbcollection_locations', schema=SCHEMA)
    op.drop_index('rblocations_user_code_uq', table_name='rblocations', schema=SCHEMA)
    op.drop_table('rblocations', schema=SCHEMA)
