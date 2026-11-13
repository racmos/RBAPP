"""user profile: rbuserprofile, optional e-mail and password, password_changed_at

Spec S1 of F9-b (docs/requirements/F9/F9-b-profile-reauth.md).

Upgrade: creates `riftbound.rbuserprofile` (one private profile per user: display name, bio,
country, city, avatar file and version, update time; the user's row is deleted with the user)
and alters `rbusers` (batch mode, so SQLite rebuilds the table): `email` and `password_hash`
accept NULL (an account without an e-mail, an OAuth-only account without a password; the
`rbusers_email_key` UNIQUE constraint stays and allows several NULLs on PostgreSQL and
SQLite) and the new `password_changed_at` (NULL = unknown; no backfill). No data changes.

Downgrade: refuses, changing nothing, while an account has no e-mail or no password (it lists
up to 20 usernames; pattern of 0003), and in offline `--sql` mode, where it cannot look;
otherwise it restores NOT NULL on both columns, drops `password_changed_at` and drops the
table. Data loss on downgrade: it deletes every profile (display names, bios, countries,
cities, avatar references) and every `password_changed_at` value.

Revision ID: 0030_user_profile
Revises: 0029_sessions
Create Date: 2026-11-13

"""
from alembic import context, op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0030_user_profile'
down_revision = '0029_sessions'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
LISTED_MAX = 20


def _set_nullable(nullable):
    with op.batch_alter_table('rbusers', schema=SCHEMA) as batch:
        batch.alter_column('email', existing_type=sa.String(length=120), nullable=nullable)
        batch.alter_column('password_hash', existing_type=sa.String(length=256),
                           nullable=nullable)
        if nullable:
            batch.add_column(sa.Column('password_changed_at', sa.DateTime(), nullable=True))
        else:
            batch.drop_column('password_changed_at')


def upgrade():
    op.create_table(
        'rbuserprofile',
        sa.Column('rbupf_user_id', sa.Integer(), nullable=False, comment='User id'),
        sa.Column('rbupf_display_name', sa.String(length=40), nullable=True,
                  comment='Display name'),
        sa.Column('rbupf_bio', sa.String(length=240), nullable=True,
                  comment='Short bio; line breaks allowed'),
        sa.Column('rbupf_country', sa.CHAR(length=2), nullable=True,
                  comment='ISO 3166-1 alpha-2 country code, upper case'),
        sa.Column('rbupf_city', sa.String(length=80), nullable=True, comment='City'),
        sa.Column('rbupf_avatar_file', sa.String(length=64), nullable=True,
                  comment='Avatar file name (F9-c); NULL = no avatar'),
        sa.Column('rbupf_avatar_version', sa.Integer(), server_default='0', nullable=False,
                  comment='Bumped on every avatar change (F9-c)'),
        sa.Column('rbupf_updated_at', sa.DateTime(), nullable=False,
                  comment='Last profile change (UTC)'),
        sa.PrimaryKeyConstraint('rbupf_user_id', name='rbuserprofile_pkey'),
        sa.ForeignKeyConstraint(['rbupf_user_id'], [f'{SCHEMA}.rbusers.id'],
                                name='rbuserprofile_user_fk', ondelete='CASCADE'),
        schema=SCHEMA,
        comment='Private profile of a user (F9).',
    )
    _set_nullable(True)


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError(
            f'{revision} checks for accounts without an e-mail or a password before the '
            'downgrade and cannot run in offline (--sql) mode. Run `flask db downgrade` '
            'against a live database.')
    names = [name for (name,) in op.get_bind().execute(sa.text(
        f'SELECT username FROM {SCHEMA}.rbusers '
        'WHERE email IS NULL OR password_hash IS NULL ORDER BY username'))]
    if names:
        listed = ', '.join(names[:LISTED_MAX])
        more = f' and {len(names) - LISTED_MAX} more' if len(names) > LISTED_MAX else ''
        raise RuntimeError(
            f'rbusers holds {len(names)} account(s) without an e-mail or a password '
            f'(usernames): {listed}{more}. The {down_revision} schema requires both. '
            'Nothing was changed; give those accounts an e-mail and a password (or delete '
            'them) and retry.')
    _set_nullable(False)
    op.drop_table('rbuserprofile', schema=SCHEMA)
