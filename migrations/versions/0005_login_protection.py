"""login protection: lockout columns on rbusers + captcha replay store

Specs LOGIN-1 (lockout columns), LOGIN-8 / D16 (replay store), R3.

rbusers gains
  failed_login_count INTEGER NOT NULL DEFAULT 0   consecutive failures; also the
                                                  escalation level (R3: no
                                                  separate lockout_level column)
  locked_until       TIMESTAMP NULL               set by the lockout, NULL = free
  last_login_at      TIMESTAMP NULL               set on every successful login

`rbcaptcha_used` remembers the sha256 of every ALTCHA challenge that was
accepted, so a solved payload cannot be replayed (not even through another
Gunicorn worker). Rows are only needed until the challenge expires; the
captcha service purges them. `rbcap_hash` is the primary key, so the second
insert of the same challenge fails with IntegrityError.

Existing users start with a zero count and no dates: nobody is locked.

Revision ID: 0005_login_protection
Revises: 0004a_schema_comments
Create Date: 2026-10-19

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0005_login_protection'
down_revision = '0004a_schema_comments'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'


def upgrade():
    with op.batch_alter_table('rbusers', schema=SCHEMA) as batch:
        batch.add_column(sa.Column('failed_login_count', sa.Integer(), nullable=False,
                                   server_default='0'))
        batch.add_column(sa.Column('locked_until', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('last_login_at', sa.DateTime(), nullable=True))

    op.create_table(
        'rbcaptcha_used',
        sa.Column('rbcap_hash', sa.String(length=64), nullable=False),
        sa.Column('rbcap_expires_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('rbcap_hash', name='rbcaptcha_used_pkey'),
        schema=SCHEMA,
    )
    op.create_index('idx_rbcaptcha_used_expires', 'rbcaptcha_used', ['rbcap_expires_at'],
                    schema=SCHEMA)


def downgrade():
    op.drop_index('idx_rbcaptcha_used_expires', table_name='rbcaptcha_used', schema=SCHEMA)
    op.drop_table('rbcaptcha_used', schema=SCHEMA)

    with op.batch_alter_table('rbusers', schema=SCHEMA) as batch:
        batch.drop_column('last_login_at')
        batch.drop_column('locked_until')
        batch.drop_column('failed_login_count')
