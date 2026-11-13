"""sessions: rbsessions and the sessions_purge job kind

Spec S1 of F9-a (docs/requirements/F9/F9-a-sessions.md).

Upgrade: creates `riftbound.rbsessions` (one row per sign-in: the hash of the session token,
times, remember flag, sign-in method, User-Agent and IP prefix, revocation) and widens the
`ck_rbjobs_kind` CHECK with `sessions_purge` (pattern of 0027). No data changes: existing
cookies hold a plain user id and load as anonymous after the deploy, so every user signs in
again once.

Downgrade: refuses, changing nothing, while `sessions_purge` jobs exist (and in offline
`--sql` mode, where it cannot count them); otherwise it restores the CHECK and drops the
table. Data loss on downgrade: it deletes every session, so every user signs in again.

Revision ID: 0029_sessions
Revises: 0028_legacy_schema_cleanup
Create Date: 2026-11-13

"""
from alembic import context, op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0029_sessions'
down_revision = '0028_legacy_schema_cleanup'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
CHECK_NAME = 'ck_rbjobs_kind'
KINDS_BEFORE = ('heartbeat', 'daily_prices', 'riot_sync', 'value_snapshot', 'products_refresh',
                'price_alerts')
KINDS_AFTER = KINDS_BEFORE + ('sessions_purge',)
ADDED_KIND = 'sessions_purge'


def _check(kinds):
    return f"rbjob_kind IN ({', '.join(repr(k) for k in kinds)})"


def _replace_check(kinds):
    with op.batch_alter_table('rbjobs', schema=SCHEMA) as batch:
        batch.drop_constraint(CHECK_NAME, type_='check')
        batch.create_check_constraint(CHECK_NAME, _check(kinds))


def upgrade():
    op.create_table(
        'rbsessions',
        sa.Column('rbses_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
                  autoincrement=True, nullable=False, comment='Session id'),
        sa.Column('rbses_user_id', sa.Integer(), nullable=False, comment='User id'),
        sa.Column('rbses_token_hash', sa.CHAR(length=64), nullable=False,
                  comment='sha256 of the session token (64 hex); never the token'),
        sa.Column('rbses_created_at', sa.DateTime(), nullable=False,
                  comment='Sign-in time (UTC)'),
        sa.Column('rbses_last_seen_at', sa.DateTime(), nullable=False,
                  comment='Last use (UTC), written at most every 5 minutes'),
        sa.Column('rbses_expires_at', sa.DateTime(), nullable=True,
                  comment='Absolute end of a remembered session (UTC); NULL otherwise'),
        sa.Column('rbses_remember', sa.Boolean(), server_default=sa.false(), nullable=False,
                  comment='Signed in with "remember me"'),
        sa.Column('rbses_auth_method', sa.String(length=16), server_default='password',
                  nullable=False,
                  comment='How the user signed in: password, discord or google'),
        sa.Column('rbses_mfa', sa.Boolean(), server_default=sa.false(), nullable=False,
                  comment='Second factor passed at sign-in'),
        sa.Column('rbses_reauth_at', sa.DateTime(), nullable=True,
                  comment='Last re-authentication (UTC)'),
        sa.Column('rbses_user_agent', sa.String(length=255), nullable=True,
                  comment='User-Agent at sign-in, cut to 255 characters'),
        sa.Column('rbses_ip_prefix', sa.String(length=48), nullable=True,
                  comment='IP prefix at sign-in (IPv4 /24, IPv6 /48); never the address'),
        sa.Column('rbses_revoked_at', sa.DateTime(), nullable=True,
                  comment='When the session was ended (UTC); NULL = not revoked'),
        sa.PrimaryKeyConstraint('rbses_id', name='rbsessions_pkey'),
        sa.ForeignKeyConstraint(['rbses_user_id'], [f'{SCHEMA}.rbusers.id'],
                                name='rbsessions_user_fk', ondelete='CASCADE'),
        sa.UniqueConstraint('rbses_token_hash', name='rbsessions_token_hash_key'),
        sa.CheckConstraint("rbses_auth_method IN ('password', 'discord', 'google')",
                           name='ck_rbsessions_auth_method'),
        schema=SCHEMA,
        comment='Server-side sessions: one row per sign-in (F9).',
    )
    op.create_index('ix_rbsessions_user_revoked', 'rbsessions',
                    ['rbses_user_id', 'rbses_revoked_at'], schema=SCHEMA)
    op.create_index('ix_rbsessions_expires_at', 'rbsessions', ['rbses_expires_at'],
                    schema=SCHEMA)
    _replace_check(KINDS_AFTER)


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError(
            f'{revision} checks for {ADDED_KIND} jobs before the downgrade and cannot run '
            'in offline (--sql) mode. Run `flask db downgrade` against a live database.')
    found = op.get_bind().execute(
        sa.text(f'SELECT COUNT(*) FROM {SCHEMA}.rbjobs WHERE rbjob_kind = :kind'),
        {'kind': ADDED_KIND}).scalar_one()
    if found:
        raise RuntimeError(
            f"rbjobs holds {found} '{ADDED_KIND}' job(s); the {down_revision} CHECK does not "
            'allow them. Nothing was changed; delete them first '
            f"(DELETE FROM {SCHEMA}.rbjobs WHERE rbjob_kind = '{ADDED_KIND}') and retry.")
    _replace_check(KINDS_BEFORE)
    op.drop_index('ix_rbsessions_expires_at', table_name='rbsessions', schema=SCHEMA)
    op.drop_index('ix_rbsessions_user_revoked', table_name='rbsessions', schema=SCHEMA)
    op.drop_table('rbsessions', schema=SCHEMA)
