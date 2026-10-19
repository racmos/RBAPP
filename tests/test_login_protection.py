"""Login protection (LOGIN-2..6, LOGIN-9, R3, R4).

Service level: `app.services.auth.authenticate` with the injectable clock
(`frozen_clock`), so a 24 hour lock costs nothing. Route level: the Jinja login
and register forms. CLI: `flask users unlock`.

R3: escalation uses `failed_login_count` only (5th failure locks 15 min, each
further failure doubles it, 24 h cap). R4: a blocked account is answered
exactly like a wrong password.
"""
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from werkzeug.security import generate_password_hash

from app import db
from app.models import User
from app.services import auth
from app.services.auth import AuthStatus
from tests.conftest import DEFAULT_PASSWORD, login_as

LOCKED_MESSAGE = 'Invalid credentials or account temporarily locked'


def fresh(username):
    db.session.expire_all()
    return User.query.filter_by(username=username).one()


def fail(username, times=1):
    """`times` wrong-password attempts through the service; returns the last result."""
    result = None
    for _ in range(times):
        result = auth.authenticate(username, 'wrong-password')
    return result


def flashes(client):
    with client.session_transaction() as sess:
        return [message for _category, message in sess.get('_flashes', [])]


def logged_in(client):
    return client.get('/riftbound/').status_code == 200


@pytest.fixture
def hash_counter(monkeypatch):
    """Count every password-hash verification made by the auth service."""
    counter = MagicMock(wraps=auth.check_password_hash)
    monkeypatch.setattr(auth, 'check_password_hash', counter)
    return counter


# ---------------------------------------------------------------------------
# LOGIN-2 lockout
# ---------------------------------------------------------------------------

class TestLockout:
    def test_failures_one_to_four_are_plain_invalid_and_count(self, app, make_user, frozen_clock):
        make_user('u')
        for expected in (1, 2, 3, 4):
            result = fail('u')
            assert result.status is AuthStatus.INVALID
            assert result.user is None and result.retry_after is None
            assert fresh('u').failed_login_count == expected
            assert fresh('u').locked_until is None

    def test_fifth_failure_locks_for_fifteen_minutes_and_the_sixth_is_refused(
            self, app, make_user, frozen_clock):
        make_user('u')
        start = frozen_clock.now
        assert fail('u', 5).status is AuthStatus.INVALID      # the 5th still answers "invalid"
        assert fresh('u').locked_until == start + timedelta(minutes=15)
        assert fresh('u').failed_login_count == 5

        frozen_clock.advance(minutes=1)
        result = auth.authenticate('u', DEFAULT_PASSWORD)     # even the CORRECT password
        assert result.status is AuthStatus.LOCKED
        assert result.user is None
        assert 1 <= result.retry_after <= 900
        assert result.retry_after == 14 * 60

    def test_the_lock_expires(self, app, make_user, frozen_clock):
        make_user('u')
        fail('u', 5)
        frozen_clock.advance(minutes=16)
        result = auth.authenticate('u', DEFAULT_PASSWORD)
        assert result.status is AuthStatus.OK
        assert result.user.username == 'u'

    def test_attempts_during_the_lock_change_nothing(self, app, make_user, frozen_clock):
        make_user('u')
        fail('u', 5)
        locked_until = fresh('u').locked_until
        for password in ('wrong-1', 'wrong-2', DEFAULT_PASSWORD):
            frozen_clock.advance(minutes=1)
            assert auth.authenticate('u', password).status is AuthStatus.LOCKED
        user = fresh('u')
        assert user.failed_login_count == 5
        assert user.locked_until == locked_until

    def test_retry_after_shrinks_with_the_clock_and_is_never_zero(self, app, make_user,
                                                                  frozen_clock):
        make_user('u')
        fail('u', 5)
        frozen_clock.advance(minutes=14, seconds=59, microseconds=500_000)
        assert auth.authenticate('u', 'x').retry_after == 1


class TestEscalation:
    @pytest.mark.parametrize('before, minutes', [
        (5, 30), (6, 60), (7, 120), (8, 240), (9, 480), (10, 960), (11, 1440), (12, 1440),
        (40, 1440)])
    def test_each_failure_after_an_expired_lock_doubles_it_up_to_a_day(
            self, app, make_user, frozen_clock, before, minutes):
        user = make_user('u')
        user.failed_login_count = before
        user.locked_until = frozen_clock.now - timedelta(seconds=1)      # expired
        db.session.commit()
        assert fail('u').status is AuthStatus.INVALID
        after = fresh('u')
        assert after.failed_login_count == before + 1
        assert after.locked_until == frozen_clock.now + timedelta(minutes=minutes)

    def test_the_count_is_not_reset_when_a_lock_starts(self, app, make_user, frozen_clock):
        make_user('u')
        fail('u', 5)
        frozen_clock.advance(minutes=16)
        fail('u')
        assert fresh('u').failed_login_count == 6
        assert fresh('u').locked_until == frozen_clock.now + timedelta(minutes=30)

    def test_thresholds_come_from_the_config(self, app, make_user, frozen_clock):
        app.config.update(LOGIN_MAX_FAILURES=2, LOGIN_LOCK_BASE_MINUTES=1, LOGIN_LOCK_MAX_MINUTES=3)
        make_user('u')
        fail('u', 2)
        assert fresh('u').locked_until == frozen_clock.now + timedelta(minutes=1)
        frozen_clock.advance(minutes=2)
        fail('u')
        assert fresh('u').locked_until == frozen_clock.now + timedelta(minutes=2)
        frozen_clock.advance(minutes=3)
        fail('u')
        assert fresh('u').locked_until == frozen_clock.now + timedelta(minutes=3)       # cap


# ---------------------------------------------------------------------------
# LOGIN-4 success resets; a lock does not end a session
# ---------------------------------------------------------------------------

class TestSuccess:
    def test_success_resets_the_state_and_stamps_last_login(self, app, make_user, frozen_clock):
        make_user('u')
        fail('u', 3)
        assert fresh('u').last_login_at is None
        result = auth.authenticate('u', DEFAULT_PASSWORD)
        assert result.status is AuthStatus.OK
        user = fresh('u')
        assert user.failed_login_count == 0
        assert user.locked_until is None
        assert user.last_login_at == frozen_clock.now

    def test_success_after_an_expired_lock_clears_the_lock(self, app, make_user, frozen_clock):
        make_user('u')
        fail('u', 6)
        frozen_clock.advance(hours=2)
        assert auth.authenticate('u', DEFAULT_PASSWORD).status is AuthStatus.OK
        user = fresh('u')
        assert (user.failed_login_count, user.locked_until) == (0, None)

    def test_a_lock_does_not_end_an_existing_session(self, app, make_user):
        make_user('u')
        first = login_as(app.test_client(), 'u')
        assert logged_in(first)
        attacker = app.test_client()
        for _ in range(5):
            attacker.post('/riftbound/login', data={'username': 'u', 'password': 'nope'})
        assert fresh('u').locked_until is not None
        assert logged_in(first)


# ---------------------------------------------------------------------------
# LOGIN-5 / R4 no account oracle
# ---------------------------------------------------------------------------

class TestNoOracle:
    def test_unknown_and_known_users_do_one_hash_check_each(self, app, make_user, hash_counter):
        make_user('u')
        assert auth.authenticate('ghost', 'whatever-1').status is AuthStatus.INVALID
        assert hash_counter.call_count == 1
        hash_counter.reset_mock()
        assert auth.authenticate('u', 'whatever-1').status is AuthStatus.INVALID
        assert hash_counter.call_count == 1

    def test_a_locked_user_also_costs_one_hash_check(self, app, make_user, frozen_clock,
                                                     hash_counter):
        make_user('u')
        fail('u', 5)
        hash_counter.reset_mock()
        assert auth.authenticate('u', DEFAULT_PASSWORD).status is AuthStatus.LOCKED
        assert hash_counter.call_count == 1

    def test_blocked_with_the_correct_password_is_invalid_and_changes_nothing(
            self, app, make_user, hash_counter):
        make_user('b', is_blocked=True)
        result = auth.authenticate('b', DEFAULT_PASSWORD)
        assert result.status is AuthStatus.INVALID
        assert result.user is None
        assert hash_counter.call_count == 1
        user = fresh('b')
        assert (user.failed_login_count, user.locked_until, user.last_login_at) == (0, None, None)

    def test_blocked_users_are_not_locked_out_and_cannot_be_probed(self, app, make_user):
        make_user('b', is_blocked=True)
        statuses = {auth.authenticate('b', 'wrong').status for _ in range(8)}
        assert statuses == {AuthStatus.INVALID}
        assert fresh('b').failed_login_count == 0

    def test_http_responses_are_identical_for_unknown_wrong_and_blocked(self, app, make_user):
        make_user('known')
        make_user('blocked', is_blocked=True)
        responses = {}
        for name, user, password in (('unknown', 'ghost', 'wrong-pass'),
                                     ('wrong', 'known', 'wrong-pass'),
                                     ('blocked', 'blocked', DEFAULT_PASSWORD)):
            client = app.test_client()
            resp = client.post('/riftbound/login', data={'username': user, 'password': password})
            responses[name] = (resp.status_code, resp.headers['Location'], flashes(client))
        assert len(set(map(str, responses.values()))) == 1
        status, location, messages = responses['unknown']
        assert status == 302 and location.endswith('/riftbound/login')
        assert messages and 'Invalid' in messages[0]


# ---------------------------------------------------------------------------
# Jinja login route (LOGIN-2, LOGIN-9)
# ---------------------------------------------------------------------------

class TestLoginRoute:
    def test_failures_one_to_four_redirect_with_an_invalid_flash(self, app, make_user):
        make_user('u')
        client = app.test_client()
        for _ in range(4):
            resp = client.post('/riftbound/login', data={'username': 'u', 'password': 'bad-pass'})
            assert resp.status_code == 302
            assert resp.headers['Location'].endswith('/riftbound/login')
            assert 'Invalid' in flashes(client)[-1]
            page = client.get('/riftbound/login')
            assert 'Invalid username or password' in page.get_data(as_text=True)

    def test_a_locked_account_gets_429_retry_after_and_no_session(self, app, make_user,
                                                                  frozen_clock):
        make_user('u')
        client = app.test_client()
        for _ in range(5):
            client.post('/riftbound/login', data={'username': 'u', 'password': 'bad-pass'})
        frozen_clock.advance(minutes=1)
        resp = client.post('/riftbound/login', data={'username': 'u', 'password': DEFAULT_PASSWORD})
        assert resp.status_code == 429
        assert resp.headers['Retry-After'].isdigit()
        assert 1 <= int(resp.headers['Retry-After']) <= 900
        html = resp.get_data(as_text=True)
        assert LOCKED_MESSAGE in html
        assert 'name="password"' in html                       # the login page again
        assert not logged_in(client)

    def test_the_lock_message_does_not_name_the_account_state(self, app, make_user, frozen_clock):
        make_user('u')
        client = app.test_client()
        for _ in range(5):
            client.post('/riftbound/login', data={'username': 'u', 'password': 'bad-pass'})
        html = client.post('/riftbound/login',
                           data={'username': 'u', 'password': 'bad-pass'}).get_data(as_text=True)
        assert 'locked until' not in html.lower()

    def test_login_works_again_when_the_lock_expires(self, app, make_user, frozen_clock):
        make_user('u')
        client = app.test_client()
        for _ in range(5):
            client.post('/riftbound/login', data={'username': 'u', 'password': 'bad-pass'})
        frozen_clock.advance(minutes=16)
        resp = client.post('/riftbound/login', data={'username': 'u', 'password': DEFAULT_PASSWORD})
        assert resp.status_code == 302
        assert logged_in(client)

    def test_a_legacy_username_still_logs_in(self, app):
        user = User(username='Old User (1)', email='old@legacy.io')
        user.password_hash = generate_password_hash('legacy-pass', method='pbkdf2:sha256:1000')
        db.session.add(user)
        db.session.commit()
        client = app.test_client()
        resp = client.post('/riftbound/login', data={'username': 'Old User (1)',
                                                     'password': 'legacy-pass'})
        assert resp.status_code == 302
        assert logged_in(client)

    @pytest.mark.parametrize('form', [
        {}, {'username': 'u'}, {'password': 'x'}, {'username': '', 'password': ''}])
    def test_empty_fields_are_answered_like_a_wrong_password(self, app, make_user, form):
        make_user('u')
        client = app.test_client()
        resp = client.post('/riftbound/login', data=form)
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/riftbound/login')
        assert 'Invalid' in flashes(client)[-1]
        assert fresh('u').failed_login_count == 0

    def test_a_successful_login_stamps_the_user(self, app, make_user, frozen_clock):
        make_user('u')
        login_as(app.test_client(), 'u')
        assert fresh('u').last_login_at == frozen_clock.now


# ---------------------------------------------------------------------------
# Jinja register route (LOGIN-9)
# ---------------------------------------------------------------------------

VALID = {'username': 'newbie', 'email': 'newbie@test.com', 'password': 'longenough1'}


def register(client, **changes):
    return client.post('/riftbound/register', data={**VALID, **changes})


class TestRegisterRoute:
    @pytest.mark.parametrize('changes', [
        {'username': 'ab'}, {'username': 'bad name!'}, {'username': 'x' * 33},
        {'username': 'semi;colon'}, {'username': ''},
        {'email': 'x'}, {'email': ''}, {'email': 'a' * 120 + '@x.io'},
        {'password': 'short7!'}, {'password': 'p' * 129}, {'password': ''},
    ])
    def test_invalid_input_creates_no_row(self, app, client, changes):
        resp = register(client, **changes)
        assert resp.status_code in (200, 302)
        assert User.query.count() == 0
        assert flashes(client) or resp.status_code == 200

    @pytest.mark.parametrize('username', ['abc', 'A_b.c-d', 'x' * 32, 'user.name-1'])
    def test_valid_usernames_are_accepted(self, app, client, username):
        assert register(client, username=username).status_code == 302
        assert User.query.filter_by(username=username).count() == 1

    def test_valid_registration_creates_a_plain_user_and_does_not_log_in(self, app, client):
        resp = register(client)
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/riftbound/login')
        user = User.query.filter_by(username='newbie').one()
        assert (user.is_admin, user.is_blocked, user.failed_login_count) == (False, False, 0)
        assert user.check_password('longenough1')
        assert not logged_in(client)

    def test_duplicate_username_is_refused(self, app, client, make_user):
        make_user('dup')
        resp = register(client, username='dup')
        assert resp.status_code == 302
        assert any('already' in m for m in flashes(client))
        assert 'Username already exists' in flashes(client)
        assert User.query.filter_by(username='dup').count() == 1

    def test_duplicate_email_is_refused(self, app, client, make_user):
        make_user('dup', email='dup@test.com')
        register(client, email='dup@test.com')
        assert 'Email already registered' in flashes(client)
        assert User.query.count() == 1

    def test_duplicate_email_ignores_case_and_spaces(self, app, client, make_user):
        make_user('dup', email='dup@test.com')
        register(client, email='  DUP@Test.com ')
        assert 'Email already registered' in flashes(client)
        assert User.query.count() == 1

    def test_the_stored_email_is_trimmed(self, app, client):
        register(client, email='  newbie@test.com ')
        assert User.query.filter_by(username='newbie').one().email == 'newbie@test.com'

    def test_extra_privileged_fields_are_ignored(self, app, client):
        register(client, is_admin='true', failed_login_count='99')
        user = User.query.filter_by(username='newbie').one()
        assert (user.is_admin, user.failed_login_count) == (False, 0)


# ---------------------------------------------------------------------------
# LOGIN-6 unlock CLI
# ---------------------------------------------------------------------------

def users_cli(app, *args):
    return app.test_cli_runner().invoke(args=['users', *args])


class TestUnlockCommand:
    def test_unlock_lets_the_correct_password_in_at_once(self, app, make_user, frozen_clock):
        make_user('u')
        fail('u', 5)
        assert auth.authenticate('u', DEFAULT_PASSWORD).status is AuthStatus.LOCKED
        result = users_cli(app, 'unlock', 'u')
        assert result.exit_code == 0, result.output
        user = fresh('u')
        assert (user.failed_login_count, user.locked_until) == (0, None)
        assert auth.authenticate('u', DEFAULT_PASSWORD).status is AuthStatus.OK

    def test_unlock_of_an_unlocked_user_is_fine(self, app, make_user):
        make_user('u')
        assert users_cli(app, 'unlock', 'u').exit_code == 0

    def test_unknown_user_fails_and_changes_nothing(self, app, make_user, frozen_clock):
        make_user('u')
        fail('u', 5)
        before = (fresh('u').failed_login_count, fresh('u').locked_until)
        result = users_cli(app, 'unlock', 'ghost')
        assert result.exit_code != 0
        assert 'ghost' in result.output
        assert (fresh('u').failed_login_count, fresh('u').locked_until) == before

    def test_unlock_does_not_touch_other_users_or_the_roles(self, app, make_user, frozen_clock):
        make_user('u')
        make_user('v', is_admin=True)
        fail('u', 5)
        fail('v', 5)
        users_cli(app, 'unlock', 'u')
        assert fresh('v').locked_until is not None
        assert fresh('v').is_admin is True

    def test_list_marks_locked_accounts(self, app, make_user, frozen_clock):
        make_user('u')
        fail('u', 5)
        assert 'locked' in users_cli(app, 'list').output


# ---------------------------------------------------------------------------
# LOGIN-7 rate limits (limited_app)
# ---------------------------------------------------------------------------

def wrong_login(client, n=1, ip=None, **headers):
    """`n` login POSTs for an unknown user (lockout irrelevant); returns the last response."""
    if ip:
        headers['X-Forwarded-For'] = ip
    resp = None
    for i in range(n):
        resp = client.post('/riftbound/login', data={'username': f'ghost{i}', 'password': 'nope-nope'},
                           headers=headers)
    return resp


def register_post(client, n=1, ip=None, **headers):
    """`n` register POSTs with an invalid username (they must still count)."""
    if ip:
        headers['X-Forwarded-For'] = ip
    resp = None
    for _ in range(n):
        resp = client.post('/riftbound/register', data={**VALID, 'username': 'ab'}, headers=headers)
    return resp


class TestRateLimits:
    @pytest.fixture(autouse=True)
    def cheap_dummy_hash(self, monkeypatch):
        """Unknown users cost one (slow scrypt) dummy verification; these tests send ~200."""
        cheap = generate_password_hash('dummy', method='pbkdf2:sha256:1000')
        monkeypatch.setattr(auth, '_dummy_hash', lambda: cheap)

    def test_the_eleventh_login_in_a_minute_is_429_with_retry_after(self, limited_app, client):
        assert all(wrong_login(client).status_code == 302 for _ in range(10))
        resp = wrong_login(client)
        assert resp.status_code == 429
        assert resp.headers['Retry-After'].isdigit()
        assert 1 <= int(resp.headers['Retry-After']) <= 60

    def test_the_fifty_first_login_in_an_hour_is_429_even_when_the_minute_window_reset(
            self, limited_app, client, monkeypatch):
        import time
        now = [time.time()]
        monkeypatch.setattr(time, 'time', lambda: now[0])
        for _ in range(5):
            assert all(wrong_login(client).status_code == 302 for _ in range(10))
            now[0] += 61                       # next minute window
        resp = wrong_login(client)
        assert resp.status_code == 429
        assert 60 < int(resp.headers['Retry-After']) <= 3600

    def test_the_sixth_register_in_an_hour_is_429(self, limited_app, client):
        assert all(register_post(client).status_code == 302 for _ in range(5))
        resp = register_post(client)
        assert resp.status_code == 429
        assert resp.headers['Retry-After'].isdigit()

    def test_only_posts_count(self, limited_app, client):
        for _ in range(30):
            assert client.get('/riftbound/login').status_code == 200
            assert client.get('/riftbound/register').status_code == 200
        assert wrong_login(client).status_code == 302

    def test_login_and_register_have_separate_counters(self, limited_app, client):
        wrong_login(client, 10)
        assert register_post(client).status_code == 302

    def test_json_clients_get_the_envelope(self, limited_app, client):
        wrong_login(client, 10)
        resp = client.post('/riftbound/login', json={'username': 'a', 'password': 'b'})
        assert resp.status_code == 429
        body = resp.get_json()
        assert body['success'] is False
        assert body['error'] == 'Too Many Requests'
        assert body['message']
        assert resp.headers['Retry-After'].isdigit()

    def test_requests_without_accept_get_an_html_page(self, limited_app, client):
        # API-8: no Accept header means HTML (unit d answered JSON with its interim predicate).
        wrong_login(client, 10)
        resp = wrong_login(client)
        assert resp.status_code == 429
        assert resp.content_type.startswith('text/html')
        assert resp.headers['Retry-After'].isdigit()

    def test_fetch_wildcard_accept_gets_the_envelope(self, limited_app, client):
        wrong_login(client, 10)
        resp = wrong_login(client, Accept='*/*')
        assert resp.status_code == 429 and resp.is_json
        assert resp.get_json()['error'] == 'Too Many Requests'

    def test_browsers_get_an_html_page(self, limited_app, client):
        wrong_login(client, 10)
        resp = wrong_login(client, Accept='text/html,application/xhtml+xml,*/*;q=0.8')
        assert resp.status_code == 429
        assert resp.content_type.startswith('text/html')
        assert resp.headers['Retry-After'].isdigit()
        assert 'csrf-token' in resp.get_data(as_text=True)      # extends base.html

    def test_addresses_are_counted_separately(self, limited_app, client):
        assert wrong_login(client, 10, ip='203.0.113.9').status_code == 302
        assert wrong_login(client, 1, ip='203.0.113.9').status_code == 429
        assert wrong_login(client, 1, ip='203.0.113.10').status_code == 302

    def test_the_limit_applies_before_the_password_is_checked(self, limited_app, client,
                                                              make_user):
        make_user('u')
        wrong_login(client, 10)
        resp = client.post('/riftbound/login', data={'username': 'u', 'password': DEFAULT_PASSWORD})
        assert resp.status_code == 429
        assert not logged_in(client)

    def test_disabled_by_config_nothing_is_limited(self, app, client):
        assert app.config['RATELIMIT_ENABLED'] is False
        assert all(wrong_login(client).status_code == 302 for _ in range(60))
        assert all(register_post(client).status_code == 302 for _ in range(8))

    def test_counters_are_reset_between_tests(self, limited_app, client):
        assert wrong_login(client, 10).status_code == 302
