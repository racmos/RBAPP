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


class TestF9bProfileChanges:
    """F9-b S3 and S13."""

    def test_set_password_stamps_password_changed_at(self, cli, make_user, frozen_clock):
        make_user('ana')
        result = cli('users', 'set-password', 'ana', input=f'{NEW_PASSWORD}\n{NEW_PASSWORD}\n')
        assert result.exit_code == 0, result.stderr
        db.session.expire_all()
        assert User.query.filter_by(username='ana').one().password_changed_at == frozen_clock.now

    def test_list_prints_a_dash_for_a_missing_email(self, cli, make_user):
        make_user('ana')
        make_user('bo', is_admin=True).email = None
        db.session.commit()
        result = cli('users', 'list')
        assert (result.exit_code, result.stdout, result.stderr) == (
            0, 'ana  ana@test.com\nbo  -  admin\n', '')


class TestReset2fa:
    """F9-d S15: `flask users reset-2fa USERNAME` over `mfa.reset(user)`."""

    @staticmethod
    def _turn_on(user, frozen_clock):
        import pyotp
        from datetime import timezone
        from app.services import mfa
        secret = mfa.setup(user)['secret'].replace(' ', '')
        totp = pyotp.TOTP(secret)
        code = totp.generate_otp(totp.timecode(frozen_clock.now.replace(tzinfo=timezone.utc)))
        status, _, _ = mfa.enable(user, code, keep_session_id=None)
        assert status is mfa.MfaStatus.OK
        frozen_clock.advance(seconds=30)
        return secret

    @staticmethod
    def _rows(user_id):
        from app.models import RbRecoveryCode, RbUserMfa
        db.session.expire_all()
        return (db.session.get(RbUserMfa, user_id) is not None,
                db.session.execute(sa.select(sa.func.count()).select_from(RbRecoveryCode).where(
                    RbRecoveryCode.rbrco_user_id == user_id)).scalar_one())

    def test_removes_2fa_and_ends_every_session(self, app, cli, make_user, frozen_clock):
        from tests.auth_helpers import sign_in_2fa
        ana, bo = make_user('ana'), make_user('bo')
        ana_secret = self._turn_on(ana, frozen_clock)
        bo_secret = self._turn_on(bo, frozen_clock)
        # F9-e: a 2FA user signs in with the password and then the code.
        clients = [sign_in_2fa(app.test_client(), 'ana', ana_secret, frozen_clock),
                   sign_in_2fa(app.test_client(), 'ana', ana_secret, frozen_clock)]
        bo_client = sign_in_2fa(app.test_client(), 'bo', bo_secret, frozen_clock)
        result = cli('users', 'reset-2fa', 'ana')
        assert (result.exit_code, result.stdout, result.stderr) == (
            0, "Two-factor authentication removed for 'ana'; 2 session(s) ended\n", '')
        assert self._rows(ana.id) == (False, 0)
        assert self._rows(bo.id) == (True, 10)
        assert not any(authenticated(c) for c in clients)
        assert authenticated(bo_client)

    def test_a_user_without_2fa_changes_nothing(self, app, cli, make_user):
        ana = make_user('ana')
        client = login_as(app.test_client(), 'ana')
        result = cli('users', 'reset-2fa', 'ana')
        assert (result.exit_code, result.stdout, result.stderr) == (
            0, "'ana' has no two-factor authentication\n", '')
        assert authenticated(client)
        assert active_count(ana.id) == 1

    def test_an_unknown_user(self, cli):
        result = cli('users', 'reset-2fa', 'ghost')
        assert (result.exit_code, result.stderr) == (1, "Error: No such user: 'ghost'\n")


class TestCreate:
    """RESET-a: `flask users create USERNAME [--email EMAIL] [--admin]` over `register_user`."""

    PASSWORD = 'reset-a-secret-pass'
    EMAIL = 'owner.reset@example.invalid'

    @pytest.fixture
    def create(self, app):
        """Invoke `flask users create`; `env_password` = RB_NEW_PASSWORD (None removes it)."""
        runner = app.test_cli_runner(mix_stderr=False)

        def _invoke(*args, input=None, env_password=None):
            return runner.invoke(args=['users', 'create', *args], input=input,
                                 env={'RB_NEW_PASSWORD': env_password})

        return _invoke

    @staticmethod
    def _user(username):
        db.session.expire_all()
        return db.session.execute(sa.select(User).where(User.username == username)).scalar_one()

    @staticmethod
    def _count():
        db.session.expire_all()
        return db.session.execute(sa.select(sa.func.count()).select_from(User)).scalar_one()

    def _secret_free(self, result, *secrets):
        for text in (result.stdout, result.stderr):
            for secret in (self.PASSWORD, self.EMAIL, *secrets):
                assert secret not in text
                assert secret.lower() not in text.lower()

    # S1, S2, S4, S5 (AC1)

    def test_with_the_environment_variable(self, app, create):
        result = create('carol', '--email', self.EMAIL, env_password=self.PASSWORD)
        assert (result.exit_code, result.stdout, result.stderr) == (0, "Created 'carol'.\n", '')
        self._secret_free(result)
        user = self._user('carol')
        assert user.email == self.EMAIL
        assert user.check_password(self.PASSWORD)
        assert user.password_changed_at is not None
        login_as(app.test_client(), 'carol', self.PASSWORD)

    def test_with_the_hidden_prompt_twice(self, app, create):
        result = create('carol', input=f'{self.PASSWORD}\n{self.PASSWORD}\n')
        assert result.exit_code == 0, result.stderr
        assert result.stdout == "New password: \nRepeat the password: \nCreated 'carol'.\n"
        assert result.stderr == ''
        self._secret_free(result)
        login_as(app.test_client(), 'carol', self.PASSWORD)

    def test_an_empty_variable_falls_back_to_the_prompt(self, create):
        result = create('carol', input=f'{self.PASSWORD}\n{self.PASSWORD}\n', env_password='')
        assert result.exit_code == 0, result.stderr
        assert result.stdout.endswith("Created 'carol'.\n")
        assert 'New password' in result.stdout
        assert self._user('carol').check_password(self.PASSWORD)

    def test_admin_sets_is_admin(self, create):
        result = create('carol', '--admin', env_password=self.PASSWORD)
        assert (result.exit_code, result.stdout, result.stderr) == (
            0, "Created 'carol' (admin).\n", '')
        assert self._user('carol').is_admin is True

    def test_without_admin_the_account_is_plain(self, create):
        assert create('carol', env_password=self.PASSWORD).exit_code == 0
        assert self._user('carol').is_admin is False

    def test_without_email_stores_null(self, create):
        assert create('carol', env_password=self.PASSWORD).exit_code == 0
        assert self._user('carol').email is None

    def test_a_blank_email_stores_null(self, create):
        assert create('carol', '--email', '  ', env_password=self.PASSWORD).exit_code == 0
        assert self._user('carol').email is None

    def test_the_new_account_is_active_unlocked_without_session_or_profile(self, create):
        from app.models import RbUserProfile
        assert create('carol', '--admin', env_password=self.PASSWORD).exit_code == 0
        user = self._user('carol')
        assert (user.is_blocked, user.failed_login_count, user.locked_until) == (False, 0, None)
        assert active_count(user.id) == 0
        assert db.session.get(RbUserProfile, user.id) is None

    def test_the_variable_wins_over_the_prompt(self, create):
        result = create('carol', input='ignored-input-1\nignored-input-2\n',
                        env_password=self.PASSWORD)
        assert (result.exit_code, result.stdout) == (0, "Created 'carol'.\n")
        assert self._user('carol').check_password(self.PASSWORD)

    def test_password_is_not_an_option(self, create):
        result = create('carol', '--password', self.PASSWORD)
        assert result.exit_code == 2
        assert self._count() == 0

    # S2, S3 (AC2, AC3): exact message, exit 1, nothing created

    def _refused(self, result, message, before, *secrets):
        assert result.exit_code == 1
        assert result.stderr == f'Error: {message}\n'
        assert self._count() == before
        self._secret_free(result, *secrets)

    def test_mismatched_passwords(self, create):
        result = create('carol', '--email', self.EMAIL,
                        input=f'{self.PASSWORD}\nsomething-else-entirely\n')
        self._refused(result, 'The two passwords do not match; nothing was changed.', 0,
                      'something-else-entirely')

    @pytest.mark.parametrize('length', [7, 129])
    def test_password_length_from_the_prompt(self, create, length):
        secret = 'p' * length
        result = create('carol', '--email', self.EMAIL, input=f'{secret}\n{secret}\n')
        self._refused(result, 'The password must have 8 to 128 characters.', 0, secret)

    @pytest.mark.parametrize('length', [7, 129])
    def test_password_length_from_the_variable(self, create, length):
        secret = 'v' * length
        result = create('carol', '--email', self.EMAIL, env_password=secret)
        self._refused(result, 'The password must have 8 to 128 characters.', 0, secret)

    @pytest.mark.parametrize('length', [8, 128])
    def test_password_length_bounds_are_accepted(self, create, length):
        result = create('carol', env_password='b' * length)
        assert (result.exit_code, result.stdout) == (0, "Created 'carol'.\n")

    @pytest.mark.parametrize('username', ['ab', 'bad name', 'x' * 33, 'émile'])
    def test_bad_username(self, create, username):
        result = create(username, '--email', self.EMAIL, env_password=self.PASSWORD)
        self._refused(result, 'Username must be 3-32 characters: letters, digits, ".", "_" or "-"',
                      0)

    def test_bad_username_is_refused_before_the_prompt(self, create):
        result = create('ab', input=f'{self.PASSWORD}\n{self.PASSWORD}\n')
        self._refused(result, 'Username must be 3-32 characters: letters, digits, ".", "_" or "-"',
                      0)
        assert 'New password' not in result.stdout

    def test_bad_email(self, create):
        result = create('carol', '--email', 'not-an-address', env_password=self.PASSWORD)
        self._refused(result, 'Invalid email format', 0, 'not-an-address')

    def test_too_long_email(self, create):
        address = 'a' * 120 + '@example.invalid'
        result = create('carol', '--email', address, env_password=self.PASSWORD)
        self._refused(result, 'Email must have at most 120 characters', 0, address)

    def test_duplicate_username(self, create, make_user):
        ana = make_user('ana')
        result = create('ana', '--email', self.EMAIL, '--admin', env_password=self.PASSWORD)
        self._refused(result, "Username already taken: 'ana'", 1)
        user = self._user('ana')
        assert (user.email, user.is_admin) == ('ana@test.com', False)
        assert user.check_password(DEFAULT_PASSWORD)
        assert user.id == ana.id

    def test_duplicate_email_in_another_case(self, create, make_user):
        make_user('ana', email=self.EMAIL)
        result = create('carol', '--email', self.EMAIL.upper(), '--admin',
                        env_password=self.PASSWORD)
        self._refused(result, 'E-mail already taken.', 1, self.EMAIL.upper())
        assert db.session.execute(sa.select(User).where(User.username == 'carol')).first() is None

    # S6

    def test_users_help_lists_create(self, cli):
        result = cli('users', '--help')
        assert result.exit_code == 0
        assert '  create ' in result.stdout

    def test_create_help_names_the_variable(self, cli):
        result = cli('users', 'create', '--help')
        assert result.exit_code == 0
        assert 'RB_NEW_PASSWORD' in result.stdout
        assert '--email' in result.stdout and '--admin' in result.stdout


class TestCreatePreserve:
    """RESET-a AC4: the commands `create` shares code with behave as before."""

    def test_promote_and_demote_keep_their_messages(self, cli, make_user):
        make_user('ana')
        assert (cli('users', 'promote', 'ana').stdout,
                cli('users', 'promote', 'ana').stdout,
                cli('users', 'demote', 'ana').stdout,
                cli('users', 'demote', 'ana').stdout) == (
            "'ana' is now an admin\n", "'ana' is already an admin\n",
            "'ana' is no longer an admin\n", "'ana' is not an admin\n")
        result = cli('users', 'promote', 'ghost')
        assert (result.exit_code, result.stderr) == (1, "Error: No such user: 'ghost'\n")

    def test_set_password_keeps_its_prompts_and_length_rule(self, cli, make_user):
        make_user('ana')
        result = cli('users', 'set-password', 'ana', input='short\nshort\n')
        assert (result.exit_code, result.stdout, result.stderr) == (
            1, 'New password: \nRepeat the password: \n',
            'Error: The password must have 8 to 128 characters.\n')

    def test_set_password_ignores_the_variable(self, app, make_user):
        make_user('ana')
        runner = app.test_cli_runner(mix_stderr=False)
        result = runner.invoke(args=['users', 'set-password', 'ana'],
                               input=f'{NEW_PASSWORD}\n{NEW_PASSWORD}\n',
                               env={'RB_NEW_PASSWORD': 'from-the-environment'})
        assert result.exit_code == 0, result.stderr
        db.session.expire_all()
        assert User.query.filter_by(username='ana').one().check_password(NEW_PASSWORD)

    def test_api_register_never_makes_an_admin(self, client):
        response = client.post('/riftbound/api/v1/auth/register', json={
            'username': 'mallory', 'password': 'mallory-pass-1', 'is_admin': True})
        assert response.status_code == 201, response.get_json()
        db.session.expire_all()
        assert User.query.filter_by(username='mallory').one().is_admin is False
