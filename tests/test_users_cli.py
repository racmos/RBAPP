"""F9-a S9 (AC5): `flask users block` and `flask users set-password` end the user's sessions
and say how many; the other `flask users` messages stay as they were."""
import pytest
import sqlalchemy as sa

from app import db
from app.models import RbSession, User
from tests.conftest import DEFAULT_PASSWORD, login_as

SESSION = '/riftbound/api/v1/auth/session'
NEW_PASSWORD = 'brand-new-pass'


@pytest.fixture
def cli(app):
    runner = app.test_cli_runner(mix_stderr=False)

    def _invoke(*args, input=None):
        return runner.invoke(args=list(args), input=input)

    return _invoke


def authenticated(client):
    return client.get(SESSION).get_json()['data']['authenticated']


def active_count(user_id):
    db.session.expire_all()
    return db.session.execute(sa.select(sa.func.count()).select_from(RbSession).where(
        RbSession.rbses_user_id == user_id, RbSession.rbses_revoked_at.is_(None))).scalar_one()


@pytest.fixture
def signed_in(app, make_user):
    """`ana` signed in on two clients, `bo` on one."""
    ana, bo = make_user('ana'), make_user('bo')
    clients = {'ana': [login_as(app.test_client(), 'ana'), login_as(app.test_client(), 'ana')],
               'bo': [login_as(app.test_client(), 'bo')]}
    return ana.id, bo.id, clients


class TestBlock:
    def test_ends_every_session_and_counts_them(self, cli, signed_in):
        ana, bo, clients = signed_in
        result = cli('users', 'block', 'ana')
        assert (result.exit_code, result.stdout, result.stderr) == (
            0, "'ana' is now blocked; 2 session(s) ended\n", '')
        assert not any(authenticated(c) for c in clients['ana'])
        assert authenticated(clients['bo'][0])
        assert (active_count(ana), active_count(bo)) == (0, 1)

    def test_no_session_is_zero(self, cli, make_user):
        make_user('ana')
        result = cli('users', 'block', 'ana')
        assert (result.exit_code, result.stdout) == (0, "'ana' is now blocked; 0 session(s) ended\n")

    def test_already_blocked_keeps_its_message(self, cli, make_user):
        make_user('ana', is_blocked=True)
        result = cli('users', 'block', 'ana')
        assert (result.exit_code, result.stdout, result.stderr) == (
            0, "'ana' is already blocked\n", '')

    def test_an_unknown_user_changes_nothing(self, cli, signed_in):
        ana, _, _ = signed_in
        result = cli('users', 'block', 'ghost')
        assert (result.exit_code, result.stderr) == (1, "Error: No such user: 'ghost'\n")
        assert active_count(ana) == 2

    def test_unblock_keeps_its_message(self, cli, make_user):
        make_user('ana', is_blocked=True)
        result = cli('users', 'unblock', 'ana')
        assert (result.exit_code, result.stdout) == (0, "'ana' is now unblocked\n")


class TestSetPassword:
    def test_ends_every_session_and_counts_them(self, app, cli, signed_in):
        ana, bo, clients = signed_in
        result = cli('users', 'set-password', 'ana', input=f'{NEW_PASSWORD}\n{NEW_PASSWORD}\n')
        assert result.exit_code == 0, result.stderr
        assert result.stdout.endswith("Password updated for 'ana'; 2 session(s) ended\n")
        assert result.stderr == ''
        assert not any(authenticated(c) for c in clients['ana'])
        assert authenticated(clients['bo'][0])
        assert (active_count(ana), active_count(bo)) == (0, 1)
        assert login_as(app.test_client(), 'ana', NEW_PASSWORD)

    def test_mismatched_passwords_change_and_end_nothing(self, cli, signed_in):
        ana, _, clients = signed_in
        result = cli('users', 'set-password', 'ana', input=f'{NEW_PASSWORD}\nsomething-else\n')
        assert result.exit_code == 1
        assert result.stderr == 'Error: The two passwords do not match; nothing was changed.\n'
        assert all(authenticated(c) for c in clients['ana'])
        assert active_count(ana) == 2
        db.session.expire_all()
        assert db.session.execute(sa.select(User).where(User.username == 'ana')).scalar_one(
        ).check_password(DEFAULT_PASSWORD)
