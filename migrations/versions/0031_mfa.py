"""mfa: rbusermfa and rbrecoverycodes (TOTP two-factor authentication)

Spec S3 of F9-d (docs/requirements/F9/F9-d-totp-enrolment.md).

Upgrade: creates `riftbound.rbusermfa` (one row per user with two-factor authentication on or
being set up: the Fernet ciphertext of the TOTP secret, when it was turned on, the last
accepted TOTP step, creation time) and `riftbound.rbrecoverycodes` (the sha256 of each
recovery code and when it was used). Both rows are deleted with their user. No data changes.

Downgrade: drops both tables, with no check. Data loss on downgrade: every user's two-factor
authentication is lost (secrets, pending setups and recovery codes); after an upgrade again
every user who had it on must set it up from scratch.

Revision ID: 0031_mfa
Revises: 0030_user_profile
Create Date: 2026-11-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0031_mfa'
down_revision = '0030_user_profile'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'


def upgrade():
    op.create_table(
        'rbusermfa',
        sa.Column('rbmfa_user_id', sa.Integer(), nullable=False, comment='User id'),
        sa.Column('rbmfa_secret_enc', sa.Text(), nullable=False,
                  comment='Fernet ciphertext of the TOTP secret; never the secret'),
        sa.Column('rbmfa_enabled_at', sa.DateTime(), nullable=True,
                  comment='When 2FA was turned on (UTC); NULL = pending setup'),
        sa.Column('rbmfa_last_step', sa.BigInteger(), nullable=True,
                  comment='Last accepted TOTP step (unix time // 30); replay guard'),
        sa.Column('rbmfa_created_at', sa.DateTime(), nullable=False,
                  comment='When the secret was created (UTC)'),
        sa.PrimaryKeyConstraint('rbmfa_user_id', name='rbusermfa_pkey'),
        sa.ForeignKeyConstraint(['rbmfa_user_id'], [f'{SCHEMA}.rbusers.id'],
                                name='rbusermfa_user_fk', ondelete='CASCADE'),
        schema=SCHEMA,
        comment='TOTP two-factor authentication of a user (F9).',
    )
    op.create_table(
        'rbrecoverycodes',
        sa.Column('rbrco_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
                  autoincrement=True, nullable=False, comment='Recovery code id'),
        sa.Column('rbrco_user_id', sa.Integer(), nullable=False, comment='User id'),
        sa.Column('rbrco_code_hash', sa.CHAR(length=64), nullable=False,
                  comment='sha256 of the normalised code (64 hex); never the code'),
        sa.Column('rbrco_used_at', sa.DateTime(), nullable=True,
                  comment='When the code was used (UTC); NULL = unused'),
        sa.PrimaryKeyConstraint('rbrco_id', name='rbrecoverycodes_pkey'),
        sa.ForeignKeyConstraint(['rbrco_user_id'], [f'{SCHEMA}.rbusers.id'],
                                name='rbrecoverycodes_user_fk', ondelete='CASCADE'),
        schema=SCHEMA,
        comment='Two-factor recovery codes, hashed (F9).',
    )
    op.create_index('ix_rbrecoverycodes_user', 'rbrecoverycodes', ['rbrco_user_id'],
                    schema=SCHEMA)


def downgrade():
    op.drop_index('ix_rbrecoverycodes_user', table_name='rbrecoverycodes', schema=SCHEMA)
    op.drop_table('rbrecoverycodes', schema=SCHEMA)
    op.drop_table('rbusermfa', schema=SCHEMA)
