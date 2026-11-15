"""Production data reset (RESET-b): empties the database for production, keeping exactly the
tables, rows and columns the owner chose (docs/requirements/F12/RESET-production-data-reset.md,
sections 3 and 13).

`TABLE_POLICY` classifies EVERY table of `db.metadata` (schema `riftbound`): `keep` (never
written), `wipe` (every row deleted) or `special` (`rbusers`, `rbjobs`, `rbcm_expansions`: rows or
a column partly kept). A new table must be classified here; `tests/test_data_reset_classification.py`
names a forgotten one and the command refuses to run while the database holds a table this dict
does not know.

The reset runs in ONE transaction: explicit DELETEs in reverse `db.metadata.sorted_tables` order
(children before parents, never relying on ON DELETE actions), the special rules, the PostgreSQL
sequences restarted with `ALTER SEQUENCE ... RESTART` (transactional; never `setval`), one
`data.reset` audit row, then a re-check that every kept table is unchanged before the single
commit. It never touches a file on disk or another schema. No Flask request objects here; the CLI
is `app/cli/reset.py`.
"""
import os
import re
# subprocess runs only the PG_RESTORE executable, with a fixed argument list and no shell.
import subprocess  # nosec B404
import time
from dataclasses import dataclass, field
from pathlib import Path

import sqlalchemy as sa
from flask import current_app

from app import db
from app.db_schema import SCHEMA
from app.services import audit

KEEP, WIPE, SPECIAL = 'keep', 'wipe', 'special'

TABLE_POLICY: dict[str, str] = {
    # Cardmarket loads (the price history) and the owner's curated tables (D-Q2, Q4, Q5).
    'rbcm_price': KEEP,
    'rbcm_products': KEEP,
    'rbcm_load_history': KEEP,
    'rbcm_categories': KEEP,
    'rbcm_ignored': KEEP,
    'rbproducts': KEEP,
    'rbcardbans': KEEP,
    # Rows kept, mapping to the (wiped) sets cleared (D-Q1, Q3).
    'rbcm_expansions': SPECIAL,
    # The --keep-user accounts stay; the finished daily_prices jobs stay (D-Q6).
    'rbusers': SPECIAL,
    'rbjobs': SPECIAL,
    # Catalog, regenerated after the reset (D-Q1, Q10, Q11).
    'rbset': WIPE,
    'rbcards': WIPE,
    'rbcardchanges': WIPE,
    'rbcardmarket': WIPE,
    'rbcm_product_card_map': WIPE,
    # User data.
    'rbuserprefs': WIPE,
    'rbkeepplayset': WIPE,
    'rbcollection': WIPE,
    'rbcollection_locations': WIPE,
    'rblocations': WIPE,
    'rbdeckheads': WIPE,
    'rbdeckversions': WIPE,
    'rbwishlists': WIPE,
    'rbwishlistlines': WIPE,
    'rbwishlistalerts': WIPE,
    'rbuserproducts': WIPE,
    'rbvaluesnaps': WIPE,
    'rbimportpreviews': WIPE,
    # F9: sessions, profile, two-factor (D-Q8), API keys.
    'rbsessions': WIPE,
    'rbuserprofile': WIPE,
    'rbusermfa': WIPE,
    'rbrecoverycodes': WIPE,
    'rbapikeys': WIPE,
    # Transient and audit (D-Q7: one data.reset row starts the new trail).
    'rbcaptcha_used': WIPE,
    'rbadminaudit': WIPE,
}

KEPT_JOB_KIND = 'daily_prices'
KEPT_JOB_STATUSES = ('success', 'error')
ACTIVE_JOB_STATUSES = ('queued', 'running')
BACKUP_MAX_AGE_HOURS = 6
PG_RESTORE_TIMEOUT_SECONDS = 300
_SEQUENCE_NAME = re.compile(r'^[A-Za-z0-9_."]+$')


class ResetRefused(Exception):
    """A guard or a check said no; the message is shown after `Error: ` (exit 1)."""


class BackupUnreadable(Exception):
    """`pg_restore -l` failed; the message is the first line of its stderr."""


# --- Classification -------------------------------------------------------------------------

def metadata_tables():
    """The app tables in schema `riftbound`, in `db.metadata.sorted_tables` order (parents
    first)."""
    return [t for t in db.metadata.sorted_tables if t.schema == SCHEMA]


def policy_problems(names, policy=None):
    """None when `policy` classifies exactly `names`; else a message naming the tables."""
    policy = TABLE_POLICY if policy is None else policy
    missing, stale = sorted(set(names) - set(policy)), sorted(set(policy) - set(names))
    parts = []
    if missing:
        parts.append(f'Unclassified tables: {", ".join(missing)}')
    if stale:
        parts.append(f'{"s" if parts else "S"}tale TABLE_POLICY keys: {", ".join(stale)}')
    return '; '.join(parts) or None


def delete_order():
    """Every classified table, children before parents (reverse `sorted_tables`)."""
    return [t.name for t in reversed(metadata_tables())]


def unclassified_tables():
    """Tables of schema `riftbound` in the DATABASE that `TABLE_POLICY` does not know."""
    names = sa.inspect(db.engine).get_table_names(schema=SCHEMA)
    return sorted(n for n in names if n != 'alembic_version' and n not in TABLE_POLICY)


# --- Environment readers (replaced in some tests) -------------------------------------------

def connected_database():
    return db.engine.url.database or ''


def current_env():
    return current_app.config.get('RB_ENV') or 'production'


def code_heads():
    from alembic.script import ScriptDirectory
    config = current_app.extensions['migrate'].migrate.get_config()
    return list(ScriptDirectory.from_config(config).get_heads())


def current_revision():
    """The revision stored in `riftbound.alembic_version`, or None without one."""
    if not sa.inspect(db.engine).has_table('alembic_version', schema=SCHEMA):
        return None
    with db.engine.connect() as conn:
        rows = conn.execute(sa.text('SELECT version_num FROM riftbound.alembic_version')).all()
    return ', '.join(sorted(r[0] for r in rows)) or None


def active_job_count():
    jobs = _table('rbjobs')
    return db.session.execute(
        sa.select(sa.func.count()).select_from(jobs)
        .where(jobs.c.rbjob_status.in_(ACTIVE_JOB_STATUSES))).scalar_one()


# --- Guards ---------------------------------------------------------------------------------

def check_target(database, env, allow_test_db):
    """S3, S5, S6, S7 in that order. Raises ResetRefused."""
    unknown = unclassified_tables()
    if unknown:
        raise ResetRefused(f'Unclassified tables: {", ".join(unknown)}. Classify them in '
                           'app/services/data_reset.py; nothing was changed.')
    actual = connected_database()
    if actual != database:
        raise ResetRefused(f"Connected to database '{actual}', not '{database}'; "
                           'nothing was changed.')
    actual_env = current_env()
    if actual_env != env:
        raise ResetRefused(f"RB_ENV is '{actual_env}', not '{env}'; nothing was changed.")
    looks_test = 'test' in actual.lower()
    if looks_test and not allow_test_db:
        raise ResetRefused(f"Database '{actual}' looks like a test database; "
                           'add --allow-test-db for a rehearsal.')
    if allow_test_db and not looks_test:
        raise ResetRefused('--allow-test-db is only for a database whose name contains "test".')


def check_state():
    """S9 and S10. Returns the database revision. Raises ResetRefused."""
    heads = code_heads()
    revision = current_revision()
    if len(heads) != 1 or revision != heads[0]:
        raise ResetRefused(f'The database is at {revision or "no revision"}, the code expects '
                           f'{", ".join(heads)}; run flask db upgrade first.')
    active = active_job_count()
    if active:
        raise ResetRefused(f'{active} job(s) queued or running; stop the timers and wait '
                           '(flask jobs list).')
    return revision


@dataclass
class BackupInfo:
    name: str
    size: int
    entries: int
    age_hours: float


def read_backup_toc(path) -> str:
    """`pg_restore -l PATH` (executable from `PG_RESTORE`, default `pg_restore`): the archive
    listing. Raises BackupUnreadable with the first stderr line when it fails."""
    executable = os.environ.get('PG_RESTORE') or 'pg_restore'
    try:
        result = subprocess.run(  # nosec B603
            [executable, '-l', str(path)], capture_output=True, text=True,
            timeout=PG_RESTORE_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError):
        raise BackupUnreadable(f'cannot run {executable}') from None
    if result.returncode != 0:
        lines = (result.stderr or '').strip().splitlines()
        raise BackupUnreadable(lines[0] if lines else f'exit code {result.returncode}')
    return result.stdout


def check_backup(path, database):
    """S8: a recent, non-empty dump of THIS database with the price data. Raises ResetRefused."""
    path = Path(path)
    if not path.is_file():
        raise ResetRefused(f'Backup file not found: {path}')
    info = path.stat()
    if info.st_size == 0:
        raise ResetRefused(f'Backup file is empty: {path}')
    age_hours = max(0.0, (time.time() - info.st_mtime) / 3600)
    if age_hours >= BACKUP_MAX_AGE_HOURS:
        raise ResetRefused(f'Backup file is older than {BACKUP_MAX_AGE_HOURS} hours: {path}')
    try:
        toc = read_backup_toc(path)
    except BackupUnreadable as error:
        raise ResetRefused(f'pg_restore cannot read the backup ({error}).') from None
    dbname = re.search(r'^;\s+dbname: (.*)$', toc, re.MULTILINE)
    found = dbname.group(1).strip() if dbname else ''
    if found != database:
        raise ResetRefused(f"The backup is of database '{found}', not '{database}'.")
    if not re.search(rf'^\d+; \d+ \d+ TABLE DATA {SCHEMA} rbcm_price ', toc, re.MULTILINE):
        raise ResetRefused(f'The backup has no data for {SCHEMA}.rbcm_price.')
    entries = re.search(r'^;\s+TOC Entries: (\d+)$', toc, re.MULTILINE)
    count = int(entries.group(1)) if entries else sum(
        1 for line in toc.splitlines() if line and not line.startswith(';'))
    return BackupInfo(name=path.name, size=info.st_size, entries=count, age_hours=age_hours)


# --- Plan (what the dry run reports) --------------------------------------------------------

@dataclass
class TableLine:
    name: str
    rows: int
    delete: int = 0
    keep: int = 0
    cleared: int = 0

    def text(self):
        policy = TABLE_POLICY[self.name]
        if self.name == 'rbcm_expansions':
            action = f'keep {self.keep}, mapping cleared {self.cleared}'
        elif policy == KEEP:
            action = 'keep'
        elif policy == WIPE:
            action = f'delete {self.delete}'
        else:
            action = f'delete {self.delete}, keep {self.keep}'
        return f'{self.name}  {self.rows}  {action}'


@dataclass
class Plan:
    tables: list = field(default_factory=list)
    kept_users: list = field(default_factory=list)
    missing_users: list = field(default_factory=list)
    deleted_users: int = 0
    admin_kept: bool = False


def _table(name):
    return db.metadata.tables[f'{SCHEMA}.{name}']


def _count(table, *where):
    query = sa.select(sa.func.count()).select_from(table)
    if where:
        query = query.where(*where)
    return db.session.execute(query).scalar_one()


def _kept_job():
    jobs = _table('rbjobs')
    return sa.and_(jobs.c.rbjob_kind == KEPT_JOB_KIND,
                   jobs.c.rbjob_status.in_(KEPT_JOB_STATUSES))


def build_plan(keep_users):
    """Counts per table and the users the reset keeps, deletes and does not find."""
    wanted = list(dict.fromkeys(keep_users))
    users = _table('rbusers')
    found = dict(db.session.execute(
        sa.select(users.c.username, users.c.is_admin).where(users.c.username.in_(wanted))).all())
    plan = Plan(kept_users=[u for u in wanted if u in found],
                missing_users=[u for u in wanted if u not in found],
                admin_kept=any(found.values()))
    for table in metadata_tables():
        rows = _count(table)
        line = TableLine(table.name, rows)
        policy = TABLE_POLICY[table.name]
        if table.name == 'rbusers':
            line.keep = len(plan.kept_users)
            line.delete = rows - line.keep
            plan.deleted_users = line.delete
        elif table.name == 'rbjobs':
            line.keep = _count(table, _kept_job())
            line.delete = rows - line.keep
        elif table.name == 'rbcm_expansions':
            line.keep = rows
            line.cleared = _count(table, table.c.rbexp_rbset_id.isnot(None))
        elif policy == WIPE:
            line.delete = rows
        plan.tables.append(line)
    return plan


# --- The reset itself -----------------------------------------------------------------------

def _kept_state():
    """Row count of every `keep` table, and the rows and ids of `rbcm_expansions`."""
    state = {name: _count(_table(name)) for name, policy in TABLE_POLICY.items()
             if policy == KEEP}
    expansions = _table('rbcm_expansions')
    ids = db.session.execute(sa.select(expansions.c.rbexp_id)).scalars().all()
    state['rbcm_expansions'] = (len(ids), frozenset(ids))
    return state


def _delete_all(table):
    return db.session.execute(table.delete()).rowcount


def _reset_jobs(kept_user_ids):
    jobs = _table('rbjobs')
    deleted = db.session.execute(jobs.delete().where(sa.not_(_kept_job()))).rowcount
    db.session.execute(
        jobs.update()
        .where(jobs.c.rbjob_requested_by.isnot(None),
               jobs.c.rbjob_requested_by.notin_(kept_user_ids))
        .values(rbjob_requested_by=None))
    return deleted


def _reset_users(keep_users):
    users = _table('rbusers')
    db.session.execute(users.update().where(users.c.username.in_(keep_users))
                       .values(failed_login_count=0, locked_until=None))
    return db.session.execute(
        users.delete().where(users.c.username.notin_(keep_users))).rowcount


def _clear_expansion_mappings():
    expansions = _table('rbcm_expansions')
    return db.session.execute(
        expansions.update().where(expansions.c.rbexp_rbset_id.isnot(None))
        .values(rbexp_rbset_id=None)).rowcount


def _sequence_restarts():
    """(sequence, restart value) of every sequence owned by a column of a table the reset
    empties (1) or partly keeps (`rbusers`, `rbjobs`: max + 1). PostgreSQL only."""
    restarts = []
    for name, policy in TABLE_POLICY.items():
        if policy == KEEP or name == 'rbcm_expansions':
            continue
        table = _table(name)
        for column in table.columns:
            if not isinstance(column.type, sa.Integer):
                continue
            sequence = db.session.execute(
                sa.text('SELECT pg_get_serial_sequence(:t, :c)'),
                {'t': f'{SCHEMA}.{name}', 'c': column.name}).scalar()
            if sequence is None:
                continue
            start = 1
            if policy == SPECIAL:
                start = (db.session.execute(sa.select(sa.func.max(column))).scalar() or 0) + 1
            restarts.append((sequence, start))
    return restarts


def _reset_sequences():
    """S15: `ALTER SEQUENCE ... RESTART WITH n` inside the transaction (never `setval`, which a
    rollback does not undo). Nothing to do on SQLite (the tests)."""
    if db.session.get_bind().dialect.name != 'postgresql':
        return
    for sequence, start in _sequence_restarts():
        if not _SEQUENCE_NAME.match(sequence):
            raise ValueError('unexpected sequence name')
        db.session.execute(sa.text(f'ALTER SEQUENCE {sequence} RESTART WITH {int(start)}'))


def execute(plan, keep_users, database, backup_name):
    """Run the reset in the current transaction and commit once. Returns
    `(rows deleted, tables with deletions, expansion mappings cleared)`. Any failure rolls
    everything back (the caller reports it); a kept table that changed raises ResetRefused."""
    keep_users = list(dict.fromkeys(keep_users))
    try:
        before = _kept_state()
        users = _table('rbusers')
        kept_ids = db.session.execute(
            sa.select(users.c.id).where(users.c.username.in_(keep_users))).scalars().all()
        deleted, cleared = {}, 0
        for name in delete_order():
            policy = TABLE_POLICY[name]
            if policy == WIPE:
                deleted[name] = _delete_all(_table(name))
            elif name == 'rbjobs':
                deleted[name] = _reset_jobs(kept_ids)
            elif name == 'rbusers':
                deleted[name] = _reset_users(keep_users)
            elif name == 'rbcm_expansions':
                cleared = _clear_expansion_mappings()
        _reset_sequences()
        audit.record('data.reset', 'database', target_id=database, actor=audit.SYSTEM, details={
            'deleted': deleted,
            'cleared_expansion_mappings': cleared,
            'kept_users': plan.kept_users,
            'missing_users': plan.missing_users,
            'backup': backup_name,
        })
        db.session.flush()
        after = _kept_state()
        changed = [name for name in before if before[name] != after[name]]
        if changed:
            raise ResetRefused(f'Kept table {changed[0]} changed during the reset; rolled back, '
                               'nothing was changed.')
        db.session.commit()
    except BaseException:
        db.session.rollback()
        raise
    return sum(deleted.values()), sum(1 for n in deleted.values() if n), cleared
