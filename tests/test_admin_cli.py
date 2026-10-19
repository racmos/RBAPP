"""
`flask users ...` administration commands (ACL-6, D11).

Run through `app.test_cli_runner()` against the in-memory test database.
"""
import pytest

from app import db
from app.models import User
from tests.conftest import DEFAULT_PASSWORD, login_as


def users(app, *args, input=None):
    """Invoke `flask users <args>`; returns the click Result."""
    return app.test_cli_runner().invoke(args=['users', *args], input=input)


def fresh(username):
    """The user re-read from the database (commands commit on their own)."""
    db.session.expire_all()
    return User.query.filter_by(username=username).one()


def snapshot():
    db.session.expire_all()
    return sorted((u.username, u.is_admin, u.is_blocked, u.password_hash)
                  for u in User.query.all())


class TestPromoteAndDemote:
    def test_promote_makes_the_user_admin_and_is_idempotent(self, app, make_user):
        make_user('alice')
        first = users(app, 'promote', 'alice')
        assert first.exit_code == 0, first.output
        assert fresh('alice').is_admin is True
        second = users(app, 'promote', 'alice')
        assert second.exit_code == 0, second.output
        assert fresh('alice').is_admin is True

    def test_promote_works_while_no_admin_exists(self, app, make_user):
        make_user('first')
        assert User.query.filter_by(is_admin=True).count() == 0
        assert users(app, 'promote', 'first').exit_code == 0
        assert User.query.filter_by(is_admin=True).count() == 1

    def test_promote_unknown_user_fails_and_changes_nothing(self, app, make_user):
        make_user('alice')
        before = snapshot()
        result = users(app, 'promote', 'ghost')
        assert result.exit_code == 1
        assert 'ghost' in result.output
        assert snapshot() == before

    def test_demote_clears_the_flag_and_is_idempotent(self, app, make_user):
        make_user('boss', is_admin=True)
        assert users(app, 'demote', 'boss').exit_code == 0
        assert fresh('boss').is_admin is False
        assert users(app, 'demote', 'boss').exit_code == 0
        assert fresh('boss').is_admin is False

    def test_demote_unknown_user_fails_and_changes_nothing(self, app, make_user):
        make_user('boss', is_admin=True)
        before = snapshot()
        result = users(app, 'demote', 'ghost')
        assert result.exit_code == 1 and 'ghost' in result.output
        assert snapshot() == before

    def test_only_the_named_user_changes(self, app, make_user):
        make_user('alice')
        make_user('bob')
        users(app, 'promote', 'alice')
        assert fresh('bob').is_admin is False

    def test_aliases_make_admin_and_revoke_admin(self, app, make_user):
        make_user('alice')
        assert users(app, 'make-admin', 'alice').exit_code == 0
        assert fresh('alice').is_admin is True
        assert users(app, 'revoke-admin', 'alice').exit_code == 0
        assert fresh('alice').is_admin is False
        ghost = users(app, 'make-admin', 'ghost')
        assert ghost.exit_code == 1 and 'ghost' in ghost.output

    def test_a_promoted_user_gets_through_the_admin_guard(self, app, make_user):
        make_user('alice')
        client = login_as(app.test_client(), 'alice')
        assert client.get('/riftbound/price').status_code == 403
        users(app, 'promote', 'alice')
        assert client.get('/riftbound/price').status_code == 200


class TestBlockAndUnblock:
    def test_block_sets_the_flag_and_is_idempotent(self, app, make_user):
        make_user('alice')
        assert users(app, 'block', 'alice').exit_code == 0
        assert fresh('alice').is_blocked is True
        assert fresh('alice').is_active is False
        assert users(app, 'block', 'alice').exit_code == 0
        assert fresh('alice').is_blocked is True

    def test_unblock_clears_the_flag_and_is_idempotent(self, app, make_user):
        make_user('alice', is_blocked=True)
        assert users(app, 'unblock', 'alice').exit_code == 0
        assert fresh('alice').is_blocked is False
        assert users(app, 'unblock', 'alice').exit_code == 0
        assert fresh('alice').is_blocked is False

    @pytest.mark.parametrize('command', ['block', 'unblock'])
    def test_unknown_user_fails_and_changes_nothing(self, app, make_user, command):
        make_user('alice')
        before = snapshot()
        result = users(app, command, 'ghost')
        assert result.exit_code == 1 and 'ghost' in result.output
        assert snapshot() == before

    def test_blocking_cuts_a_live_session(self, app, make_user):
        make_user('alice')
        client = login_as(app.test_client(), 'alice')
        assert client.get('/riftbound/').status_code == 200
        users(app, 'block', 'alice')
        assert client.get('/riftbound/').status_code == 302
        users(app, 'unblock', 'alice')
        assert client.get('/riftbound/').status_code == 200


class TestSetPassword:
    def test_changes_the_password_with_a_hidden_confirmed_prompt(self, app, make_user):
        make_user('alice')
        result = users(app, 'set-password', 'alice', input='brand-new-pass\nbrand-new-pass\n')
        assert result.exit_code == 0, result.output
        user = fresh('alice')
        assert user.check_password('brand-new-pass')
        assert not user.check_password(DEFAULT_PASSWORD)
        assert 'brand-new-pass' not in result.output          # never echoed

    def test_a_mismatching_confirmation_changes_nothing(self, app, make_user):
        make_user('alice')
        before = snapshot()
        result = users(app, 'set-password', 'alice', input='brand-new-pass\nsomething-else\n')
        assert result.exit_code == 1
        assert 'do not match' in result.output
        assert snapshot() == before

    @pytest.mark.parametrize('short', ['short', '1234567', 'a'])
    def test_passwords_under_8_characters_are_rejected(self, app, make_user, short):
        make_user('alice')
        before = snapshot()
        result = users(app, 'set-password', 'alice', input=f'{short}\n{short}\n')
        assert result.exit_code == 1
        assert '8' in result.output
        assert snapshot() == before

    def test_exactly_8_characters_is_accepted(self, app, make_user):
        make_user('alice')
        assert users(app, 'set-password', 'alice', input='12345678\n12345678\n').exit_code == 0
        assert fresh('alice').check_password('12345678')

    def test_unknown_user_fails_without_asking_for_a_password(self, app, make_user):
        make_user('alice')
        before = snapshot()
        result = users(app, 'set-password', 'ghost', input='brand-new-pass\nbrand-new-pass\n')
        assert result.exit_code == 1 and 'ghost' in result.output
        assert snapshot() == before


class TestList:
    def test_lists_every_user_with_role_and_state_but_no_hashes(self, app, make_user):
        make_user('alice', is_admin=True)
        make_user('bob', is_blocked=True)
        make_user('carol')
        result = users(app, 'list')
        assert result.exit_code == 0, result.output
        lines = {line.split()[0]: line for line in result.output.splitlines() if line.strip()}
        assert 'admin' in lines['alice'] and 'blocked' not in lines['alice']
        assert 'blocked' in lines['bob'] and 'admin' not in lines['bob']
        assert 'admin' not in lines['carol'] and 'blocked' not in lines['carol']
        assert 'alice@test.com' in lines['alice']
        for user in User.query.all():
            assert user.password_hash not in result.output

    def test_works_with_no_users_at_all(self, app):
        result = users(app, 'list')
        assert result.exit_code == 0
        assert 'No users' in result.output

    def test_works_while_nobody_is_admin(self, app, make_user):
        make_user('carol')
        result = users(app, 'list')
        assert result.exit_code == 0 and 'carol' in result.output


class TestRegistration:
    def test_all_commands_are_listed_in_the_help(self, app):
        result = users(app, '--help')
        assert result.exit_code == 0
        for name in ('promote', 'demote', 'block', 'unblock', 'set-password', 'list',
                     'make-admin', 'revoke-admin'):
            assert name in result.output, name
