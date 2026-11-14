"""api_keys: rbapikeys (personal read-only API keys)

Spec S1 of F9-h (docs/requirements/F9/F9-h-api-key.md).

Upgrade: creates `riftbound.rbapikeys` (at most one row per user: the sha256 of the key, its
first 14 characters, when it was created and last used). The row is deleted with its user.
No data changes.

Downgrade: drops the table, with no check. Data loss on downgrade: every API key stops working
(the keys are gone); after an upgrade again each user must create a new key.

Revision ID: 0032_api_keys
Revises: 0031_mfa
Create Date: 2026-11-14

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0032_api_keys'
down_revision = '0031_mfa'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'


def upgrade():
    op.create_table(
        'rbapikeys',
        sa.Column('rbapk_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
                  autoincrement=True, nullable=False, comment='API key id'),
        sa.Column('rbapk_user_id', sa.Integer(), nullable=False, comment='User id'),
        sa.Column('rbapk_prefix', sa.String(length=16), nullable=False,
                  comment='First 14 characters of the key (rb_live_ + 6 hex)'),
        sa.Column('rbapk_key_hash', sa.CHAR(length=64), nullable=False,
                  comment='sha256 of the key (64 hex); never the key'),
        sa.Column('rbapk_created_at', sa.DateTime(), nullable=False,
                  comment='When the key was created (UTC)'),
        sa.Column('rbapk_last_used_at', sa.DateTime(), nullable=True,
                  comment='Last use (UTC), written at most once a minute'),
        sa.PrimaryKeyConstraint('rbapk_id', name='rbapikeys_pkey'),
        sa.ForeignKeyConstraint(['rbapk_user_id'], [f'{SCHEMA}.rbusers.id'],
                                name='rbapikeys_user_fk', ondelete='CASCADE'),
        sa.UniqueConstraint('rbapk_user_id', name='rbapikeys_user_key'),
        sa.UniqueConstraint('rbapk_key_hash', name='rbapikeys_key_hash_key'),
        schema=SCHEMA,
        comment='Personal read-only API keys, hashed (F9).',
    )


def downgrade():
    op.drop_table('rbapikeys', schema=SCHEMA)
