"""F9-a S2-S4, S6, S7 (AC2): `app.services.sessions`: the identity format, the user loader,
the `last_seen_at` throttle, IP prefixes and device labels.

IP addresses come only from the documentation ranges (RFC 5737, RFC 3849)."""
import hashlib
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy import event

from app import db
from app.models import RbSession, User
from app.services import sessions

NOW = datetime(2030, 1, 1, 12, 0, 0)
FIREFOX_WINDOWS = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 '
                   'Firefox/132.0')
SAFARI_IPHONE = ('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 '
                 '(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1')
CHROME_ANDROID = ('Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like '
                  'Gecko) Chrome/130.0.0.0 Mobile Safari/537.36')
EDGE_WINDOWS = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like '
                'Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0')


class Statements:
    """Records the SQL statements run inside the `with` block."""

    def __enter__(self):
        self.seen = []
        event.listen(db.engine, 'before_cursor_execute', self._record)
        return self

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.seen.append(statement.lstrip().split(None, 1)[0].upper())

    def __exit__(self, *exc):
        event.remove(db.engine, 'before_cursor_execute', self._record)


def sign_in(app, user, remember=False, user_agent=FIREFOX_WINDOWS, addr='192.0.2.10'):
    """Sign `user` in inside a request context; returns the raw identity (`s:<token>`)."""
    headers = {'User-Agent': user_agent} if user_agent is not None else {}
    with app.test_request_context(headers=headers, environ_base={'REMOTE_ADDR': addr}):
        sessions.sign_in(user, remember=remember, auth_method='password')
        return user.get_id()


def load(app, raw_id):
    with app.test_request_context():
        return sessions.load_identity(raw_id)


def only_row():
    db.session.expire_all()
    return db.session.execute(sa.select(RbSession)).scalar_one()


# --- S2: identity format -----------------------------------------------------------------

class TestIdentityFormat:
    def test_the_token_is_never_stored_only_its_sha256(self, app, make_user, frozen_clock):
        user = make_user('ana')
        raw = sign_in(app, user)
        assert raw.startswith('s:')
        token = raw[2:]
        assert len(token) >= 43
        row = only_row()
        assert row.rbses_token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert all(token not in str(getattr(row, column.key))
                   for column in RbSession.__table__.columns)

    def test_two_sign_ins_get_different_tokens(self, app, make_user, frozen_clock):
        user = make_user('ana')
        assert sign_in(app, user) != sign_in(app, user)
        assert db.session.execute(sa.select(sa.func.count()).select_from(
            RbSession)).scalar_one() == 2

    def test_a_user_without_a_session_has_no_id(self, app, make_user):
        assert make_user('ana').get_id() is None
        assert User(username='x', email='x@test.com').get_id() is None


# --- S3: the loader -------------------------------------------------------------------------

class TestLoader:
    def test_a_valid_identity_loads_the_user_with_the_session(self, app, make_user,
                                                              frozen_clock):
        user = make_user('ana')
        raw = sign_in(app, user)
        with app.test_request_context():
            loaded = sessions.load_identity(raw)
            assert loaded.id == user.id
            assert loaded.get_id() == raw
            assert sessions.current().rbses_id == only_row().rbses_id

    @pytest.mark.parametrize('raw', ['1', '42', '', 'x:abc', 's:', 's:unknown-token'])
    def test_anything_else_is_anonymous_and_writes_nothing(self, app, make_user, frozen_clock,
                                                           raw):
        make_user('ana')
        with Statements() as seen:
            assert load(app, raw) is None
        assert 'UPDATE' not in seen.seen and 'INSERT' not in seen.seen

    def test_a_pre_f9_plain_user_id_runs_no_query(self, app, make_user):
        raw = str(make_user('ana').id)
        with Statements() as seen:
            assert load(app, raw) is None
        assert seen.seen == []

    def test_a_revoked_session_is_anonymous(self, app, make_user, frozen_clock):
        raw = sign_in(app, make_user('ana'))
        row = only_row()
        row.rbses_revoked_at = NOW
        db.session.commit()
        assert load(app, raw) is None

    def test_a_blocked_user_is_anonymous(self, app, make_user, frozen_clock):
        user = make_user('ana')
        raw = sign_in(app, user)
        user.is_blocked = True
        db.session.commit()
        assert load(app, raw) is None

    def test_a_session_idle_for_12_hours_ends(self, app, make_user, frozen_clock):
        raw = sign_in(app, make_user('ana'))
        frozen_clock.advance(hours=11, minutes=59, seconds=59)
        assert load(app, raw) is not None          # and this use moves last_seen_at
        frozen_clock.advance(hours=11, minutes=59, seconds=59)
        assert load(app, raw) is not None
        frozen_clock.advance(hours=12)
        assert load(app, raw) is None

    def test_a_remembered_session_ends_after_30_days_whatever_the_use(self, app, make_user,
                                                                      frozen_clock):
        raw = sign_in(app, make_user('ana'), remember=True)
        assert only_row().rbses_expires_at == NOW + timedelta(days=30)
        frozen_clock.advance(days=20)              # idle for longer than 12 hours: still fine
        assert load(app, raw) is not None
        frozen_clock.advance(days=9, hours=23, minutes=59, seconds=59)
        assert load(app, raw) is not None
        assert only_row().rbses_expires_at == NOW + timedelta(days=30)   # use never extends it
        frozen_clock.advance(seconds=1)
        assert load(app, raw) is None

    def test_one_select_per_load(self, app, make_user, frozen_clock):
        raw = sign_in(app, make_user('ana'))
        db.session.expire_all()
        with Statements() as seen:
            with app.test_request_context():
                user = sessions.load_identity(raw)
                assert (user.username, user.is_admin, user.email) == ('ana', False,
                                                                       'ana@test.com')
                assert sessions.current_id() is not None
        assert seen.seen == ['SELECT']


# --- S4: last_seen_at throttle -------------------------------------------------------------

class TestLastSeen:
    def test_written_at_most_once_every_5_minutes(self, app, make_user, frozen_clock):
        raw = sign_in(app, make_user('ana'))
        frozen_clock.advance(minutes=4, seconds=59)
        with Statements() as seen:
            assert load(app, raw) is not None
        assert seen.seen == ['SELECT']
        assert only_row().rbses_last_seen_at == NOW

        frozen_clock.advance(seconds=1)            # exactly 5 minutes
        with Statements() as seen:
            assert load(app, raw) is not None
        assert seen.seen.count('UPDATE') == 1
        assert only_row().rbses_last_seen_at == NOW + timedelta(minutes=5)

        for _ in range(3):                         # a burst right after: no write
            frozen_clock.advance(seconds=30)
            with Statements() as seen:
                assert load(app, raw) is not None
            assert 'UPDATE' not in seen.seen
        assert only_row().rbses_last_seen_at == NOW + timedelta(minutes=5)


# --- S6: IP prefix --------------------------------------------------------------------------

@pytest.mark.parametrize('addr, prefix', [
    ('192.0.2.123', '192.0.2.0/24'),
    ('198.51.100.7', '198.51.100.0/24'),
    ('2001:db8:1234:5678::1', '2001:db8:1234::/48'),
    ('2001:db8::1', '2001:db8::/48'),
    ('::ffff:203.0.113.99', '203.0.113.0/24'),
    (None, None),
    ('', None),
    ('not-an-address', None),
])
def test_ip_prefix(addr, prefix):
    assert sessions.ip_prefix(addr) == prefix


# --- S7: device label -----------------------------------------------------------------------

@pytest.mark.parametrize('user_agent, label', [
    (FIREFOX_WINDOWS, 'Firefox on Windows'),
    (SAFARI_IPHONE, 'Safari on iOS'),
    (CHROME_ANDROID, 'Chrome on Android'),
    (EDGE_WINDOWS, 'Edge on Windows'),
    ('curl/8.0', 'Browser'),
    ('', 'Unknown device'),
    (None, 'Unknown device'),
    ('Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) '
     'Chrome/130.0.0.0 Safari/537.36 OPR/115.0.0.0', 'Opera on macOS'),
    ('Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) '
     'Chrome/130.0.0.0 Safari/537.36', 'Chrome on ChromeOS'),
    ('Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0',
     'Firefox on Linux'),
    ('Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) '
     'CriOS/130.0.0.0 Mobile/15E148 Safari/604.1', 'Chrome on iOS'),
    ('Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) '
     'Version/18.0 Safari/605.1.15', 'Safari on macOS'),
    ('SomeBot/1.0 (Windows)', 'Browser on Windows'),
])
def test_device_label(user_agent, label):
    assert sessions.device_label(user_agent) == label


# --- S5 details the API test does not reach -------------------------------------------------

def test_the_user_agent_is_cut_to_255_and_may_be_absent(app, make_user, frozen_clock):
    user = make_user('ana')
    sign_in(app, user, user_agent='x' * 300)
    sign_in(app, user, user_agent=None)
    db.session.expire_all()
    agents = [r.rbses_user_agent for r in db.session.execute(
        sa.select(RbSession).order_by(RbSession.rbses_id)).scalars()]
    assert agents == ['x' * 255, None]


# --- F9-e S1: the second factor is part of the one sign-in function ---------------------------

class TestSecondFactor:
    def test_a_2fa_user_without_the_second_factor_gets_nothing(self, app, make_user,
                                                               frozen_clock):
        from tests.auth_helpers import turn_on_2fa
        user = make_user('ana')
        turn_on_2fa(user, frozen_clock)
        with app.test_request_context():
            with pytest.raises(sessions.SecondFactorRequired):
                sessions.sign_in(user, remember=True, auth_method='password', mfa_passed=False)
            from flask import session as flask_session
            assert '_user_id' not in flask_session
        assert user.get_id() is None
        assert db.session.execute(sa.select(sa.func.count()).select_from(
            RbSession)).scalar_one() == 0

    def test_the_second_factor_is_stored_on_the_session(self, app, make_user, frozen_clock):
        from tests.auth_helpers import turn_on_2fa
        user = make_user('ana')
        turn_on_2fa(user, frozen_clock)
        with app.test_request_context():
            row = sessions.sign_in(user, remember=False, auth_method='password',
                                   mfa_passed=True)
        assert row.rbses_mfa is True
        assert only_row().rbses_mfa is True

    def test_a_user_without_2fa_signs_in_without_it(self, app, make_user, frozen_clock):
        sign_in(app, make_user('ana'))
        assert only_row().rbses_mfa is False

    def test_a_pending_setup_is_not_2fa(self, app, make_user, frozen_clock):
        from app.services import mfa
        user = make_user('ana')
        mfa.setup(user)
        sign_in(app, user)
        assert only_row().rbses_mfa is False
