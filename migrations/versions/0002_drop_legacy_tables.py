"""drop the legacy tables old1_rbusers and old_rbdecks (backup first)

Steps, in this order (design D8, specs MIG-4 / MIG-5):

1. refuse offline (--sql) mode: the revision has to read rows and write a file;
2. abort, changing nothing, if a deck in `rbdecks` has an owner that is not in
   `rbusers` (it would break the repointed FK);
3. warn about each `old_rbdecks` deck (user/name) that has no match in
   `rbdecks` (it is kept only in the backup) and carry on;
4. write every row of both legacy tables to
   `<backup dir>/legacy_tables_<UTC>.sql` as INSERT statements, mode 0600, only
   when there is at least one row. If that fails nothing has been dropped;
5. repoint `rbdecks.fk_deck_user` from old1_rbusers to rbusers(username)
   (ON UPDATE CASCADE ON DELETE RESTRICT), then drop both legacy tables (and
   their sequence on PostgreSQL).

The backup directory is `LEGACY_BACKUP_DIR` (Flask config), else the
`RB_LEGACY_BACKUP_DIR` environment variable, else `<instance_path>/backups`
(git-ignored). The file holds e-mail addresses and password hashes: NEVER
commit it.

downgrade() recreates both tables, replays the newest backup file (if any)
and points the FK back at old1_rbusers.

Revision ID: 0002_drop_legacy_tables
Revises: 0001_baseline
Create Date: 2026-10-18

"""
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.engine.default import DefaultDialect
from flask import current_app

# revision identifiers, used by Alembic.
revision = '0002_drop_legacy_tables'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
LEGACY_USERS_SEQUENCE = 'rbusers_rbus_id_seq'
BACKUP_PREFIX = 'legacy_tables_'
# Dump order: users first, then decks (replay order does not matter: no FKs
# between the two legacy tables).
LEGACY_TABLES = ('old1_rbusers', 'old_rbdecks')

log = logging.getLogger('alembic.env')


# --- helpers -------------------------------------------------------------------

def _refuse_offline():
    if context.is_offline_mode():
        raise RuntimeError(
            f'{revision} cannot run in offline (--sql) mode: it reads the legacy '
            'tables and writes a backup file. Run `flask db upgrade` against a '
            'live database instead.')


def _backup_dir() -> Path:
    configured = (current_app.config.get('LEGACY_BACKUP_DIR')
                  or os.environ.get('RB_LEGACY_BACKUP_DIR'))
    return Path(configured) if configured else Path(current_app.instance_path) / 'backups'


def _is_postgresql(bind) -> bool:
    return bind.dialect.name == 'postgresql'


def _orphan_deck_owners(bind):
    return [r[0] for r in bind.execute(sa.text(
        'SELECT DISTINCT d.rbdck_user FROM riftbound.rbdecks d'
        ' LEFT JOIN riftbound.rbusers u ON u.username = d.rbdck_user'
        ' WHERE u.username IS NULL ORDER BY 1'))]


def _legacy_decks_missing_from_rbdecks(bind):
    return [tuple(r) for r in bind.execute(sa.text(
        'SELECT DISTINCT o.rbdck_user, o.rbdck_name FROM riftbound.old_rbdecks o'
        ' WHERE NOT EXISTS (SELECT 1 FROM riftbound.rbdecks d'
        '  WHERE d.rbdck_user = o.rbdck_user AND d.rbdck_name = o.rbdck_name)'
        ' ORDER BY 1, 2'))]


def _backup_statements(bind):
    """INSERT statements (literal values) for every legacy row.

    Rendered with the generic dialect on purpose: the PostgreSQL driver
    dialects double '%' inside literals, which would corrupt the data when the
    file is replayed."""
    dialect = DefaultDialect()
    metadata = sa.MetaData()
    statements = []
    for name in LEGACY_TABLES:
        table = sa.Table(name, metadata, schema=SCHEMA, autoload_with=bind)
        query = sa.select(table).order_by(*table.primary_key.columns)
        for row in bind.execute(query):
            insert = sa.insert(table).values(**row._mapping)
            statements.append(str(insert.compile(
                dialect=dialect, compile_kwargs={'literal_binds': True})))
    return statements


def _write_backup(statements) -> Path:
    """Write the backup (0600) or raise RuntimeError. Called BEFORE any DDL."""
    folder = _backup_dir()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    try:
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        path, n = folder / f'{BACKUP_PREFIX}{stamp}.sql', 1
        while path.exists():                       # two runs in the same second
            n += 1
            path = folder / f'{BACKUP_PREFIX}{stamp}_{n}.sql'
        header = (
            '-- Riftbound legacy tables (old1_rbusers, old_rbdecks) saved by '
            f'{revision}.\n'
            '-- CONTAINS E-MAIL ADDRESSES AND PASSWORD HASHES. NEVER COMMIT THIS FILE.\n'
            '-- Replayed by `flask db downgrade 0001_baseline`.\n')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='') as handle:
                handle.write(header)
                for statement in statements:
                    handle.write(statement + ';\n')
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        os.chmod(path, 0o600)
        return path
    except OSError as exc:
        raise RuntimeError(
            f'Cannot write the legacy-table backup under {folder}: {exc.strerror or exc}. '
            'Nothing was changed. Fix the directory (or set RB_LEGACY_BACKUP_DIR) and retry.'
        ) from exc


def _split_statements(text):
    """Split an SQL script on ';' outside single-quoted strings; skip `--` lines."""
    buffer, in_string = [], False
    for line in text.splitlines(keepends=True):
        if not in_string and line.lstrip().startswith('--'):
            continue
        for char in line:
            if char == "'":
                in_string = not in_string
            if char == ';' and not in_string:
                statement = ''.join(buffer).strip()
                buffer = []
                if statement:
                    yield statement
            else:
                buffer.append(char)
    rest = ''.join(buffer).strip()
    if rest:
        yield rest


def _newest_backup():
    folder = _backup_dir()
    found = sorted(folder.glob(f'{BACKUP_PREFIX}*.sql')) if folder.is_dir() else []
    return found[-1] if found else None


def _replay_backup(bind, path: Path) -> int:
    """Run the INSERTs of a backup file. Only INSERTs into the two legacy
    tables are accepted: the file is data, never a script to trust."""
    allowed = tuple(f'INSERT INTO {SCHEMA}.{name} ' for name in LEGACY_TABLES)
    cursor = bind.connection.cursor()           # raw DBAPI: '%' and ':' stay literal
    count = 0
    try:
        with open(path, encoding='utf-8', newline='') as handle:
            for statement in _split_statements(handle.read()):
                if not statement.startswith(allowed):
                    raise RuntimeError(
                        f'Unexpected statement in {path}: only INSERTs into '
                        f'{", ".join(LEGACY_TABLES)} are replayed.')
                cursor.execute(statement)
                count += 1
    finally:
        cursor.close()
    return count


def _create_legacy_tables(bind):
    """The two legacy tables exactly as 0001_baseline created them."""
    pg = _is_postgresql(bind)
    now = sa.func.now()
    current_ts = sa.text('CURRENT_TIMESTAMP')
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
        sa.Column('rbus_created', sa.DateTime(), server_default=current_ts, nullable=True),
        sa.Column('rbus_updated', sa.DateTime(), server_default=current_ts, nullable=True),
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
        'old_rbdecks',
        sa.Column('rbdck_snapshot', sa.DateTime(), server_default=now, nullable=False),
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


# --- revision --------------------------------------------------------------------

def upgrade():
    _refuse_offline()
    bind = op.get_bind()

    orphans = _orphan_deck_owners(bind)
    if orphans:
        raise RuntimeError(
            'rbdecks has decks whose owner is not in rbusers: '
            + ', '.join(repr(o) for o in orphans)
            + '. Nothing was changed. Create those users or fix rbdck_user, then retry.')

    for user, deck in _legacy_decks_missing_from_rbdecks(bind):
        log.warning(
            "old_rbdecks deck '%s/%s' has no match in rbdecks: it survives only in the "
            'legacy-table backup', user, deck)

    statements = _backup_statements(bind)
    if statements:
        path = _write_backup(statements)
        log.warning('Legacy tables saved to %s (contains e-mails and password hashes; '
                    'never commit it)', path)

    # Repoint the FK BEFORE dropping the table it references.
    with op.batch_alter_table('rbdecks', schema=SCHEMA) as batch:
        batch.drop_constraint('fk_deck_user', type_='foreignkey')
        batch.create_foreign_key(
            'fk_deck_user', 'rbusers', ['rbdck_user'], ['username'],
            referent_schema=SCHEMA, onupdate='CASCADE', ondelete='RESTRICT')

    op.drop_table('old_rbdecks', schema=SCHEMA)
    op.drop_table('old1_rbusers', schema=SCHEMA)
    if _is_postgresql(bind):
        op.execute(f'DROP SEQUENCE IF EXISTS {SCHEMA}.{LEGACY_USERS_SEQUENCE}')


def downgrade():
    _refuse_offline()
    bind = op.get_bind()

    _create_legacy_tables(bind)

    backup = _newest_backup()
    if backup is not None:
        count = _replay_backup(bind, backup)
        log.warning('Restored %d legacy row(s) from %s', count, backup)
        if _is_postgresql(bind):
            op.execute(
                f"SELECT setval('{SCHEMA}.{LEGACY_USERS_SEQUENCE}', max(rbus_id)) "
                f'FROM {SCHEMA}.old1_rbusers')
    else:
        log.warning('No %s*.sql backup found under %s: the legacy tables come back empty',
                    BACKUP_PREFIX, _backup_dir())

    with op.batch_alter_table('rbdecks', schema=SCHEMA) as batch:
        batch.drop_constraint('fk_deck_user', type_='foreignkey')
        batch.create_foreign_key(
            'fk_deck_user', 'old1_rbusers', ['rbdck_user'], ['rbus_username'],
            referent_schema=SCHEMA)
