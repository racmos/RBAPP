"""F9-a S13 (AC5): `flask sessions purge [--dry-run]` deletes the ended sessions only."""
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa

from app import db
from app.models import RbSession

NOW = datetime(2030, 1, 1, 12, 0, 0)


@pytest.fixture
def cli(app):
    runner = app.test_cli_runner(mix_stderr=False)

    def _invoke(*args):
        return runner.invoke(args=list(args))

    return _invoke


def add(user_id, name, *, remember=False, last_seen=NOW, expires=None, revoked=None):
    db.session.add(RbSession(
        rbses_user_id=user_id, rbses_token_hash=name.ljust(64, '0'), rbses_created_at=NOW,
        rbses_last_seen_at=last_seen, rbses_remember=remember, rbses_expires_at=expires,
        rbses_revoked_at=revoked, rbses_user_agent=name))


@pytest.fixture
def seeded(make_user, frozen_clock):
    """Four ended sessions and three active ones, as of NOW (the frozen clock)."""
    user = make_user('ana').id
    add(user, 'revoked', revoked=NOW - timedelta(minutes=1))
    add(user, 'revoked-remembered', remember=True, expires=NOW + timedelta(days=5),
        revoked=NOW - timedelta(days=1))
    add(user, 'idle', last_seen=NOW - timedelta(hours=12))
    add(user, 'expired', remember=True, expires=NOW, last_seen=NOW)
    add(user, 'active', last_seen=NOW - timedelta(hours=11, minutes=59))
    add(user, 'remembered', remember=True, expires=NOW + timedelta(seconds=1),
        last_seen=NOW - timedelta(days=20))
    add(user, 'fresh')
    db.session.commit()


def names():
    db.session.expire_all()
    return [r.rbses_user_agent for r in db.session.execute(
        sa.select(RbSession).order_by(RbSession.rbses_id)).scalars()]


def test_purge_deletes_the_ended_sessions_only(cli, seeded):
    result = cli('sessions', 'purge')
    assert (result.exit_code, result.stdout, result.stderr) == (0, 'Purged 4 session(s)\n', '')
    assert names() == ['active', 'remembered', 'fresh']


def test_dry_run_counts_and_deletes_nothing(cli, seeded):
    result = cli('sessions', 'purge', '--dry-run')
    assert (result.exit_code, result.stdout, result.stderr) == (
        0, 'Would purge 4 session(s)\n', '')
    assert len(names()) == 7


def test_nothing_to_purge(cli, app):
    result = cli('sessions', 'purge')
    assert (result.exit_code, result.stdout) == (0, 'Purged 0 session(s)\n')
