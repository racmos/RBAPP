"""ALTCHA on register (LOGIN-8, D16, R11).

`altcha_app` switches the provider on with `ALTCHA_MAX_NUMBER=1000`, so a test
solves a challenge in milliseconds with the `altcha` library, exactly as the
widget does in the browser. Time comes from `frozen_clock` (the replay-store
expiry and the challenge expiry both read `app.utils.clock`).
"""
import base64
import hashlib
import hmac
import html
import json
import re
from datetime import timedelta

import pytest
from altcha import ChallengeOptionsV1, create_challenge_v1, solve_challenge_v1

from app import db
from app.models import RbCaptchaUsed, User
from app.services import captcha
from app.utils import clock

CHALLENGE_ATTR = re.compile(r"challengejson='([^']*)'")
VALID = {'username': 'newbie', 'email': 'newbie@test.com', 'password': 'longenough1'}


def challenge_of(page_html):
    """The challenge JSON the page hands to the widget, or None."""
    match = CHALLENGE_ATTR.search(page_html)
    return json.loads(html.unescape(match.group(1))) if match else None


def solve(issued, **tamper):
    """The base64 payload the widget posts back for the `issued` challenge dict;
    `tamper` overrides payload fields."""
    solution = solve_challenge_v1(issued['challenge'], issued['salt'],
                                  issued['algorithm'], issued['maxNumber'])
    assert solution is not None, 'challenge not solvable within max_number'
    payload = {'algorithm': issued['algorithm'], 'challenge': issued['challenge'],
               'number': solution.number, 'salt': issued['salt'],
               'signature': issued['signature']}
    payload.update(tamper)
    return base64.b64encode(json.dumps(payload).encode()).decode()


def fresh_payload(client):
    """GET the register page, solve its challenge."""
    challenge = challenge_of(client.get('/riftbound/register').get_data(as_text=True))
    assert challenge, 'register page has no challenge'
    return solve(challenge)


def register(client, payload=None, **changes):
    data = {**VALID, **changes}
    if payload is not None:
        data['altcha'] = payload
    return client.post('/riftbound/register', data=data)


def flashes(client):
    with client.session_transaction() as sess:
        return [m for _c, m in sess.get('_flashes', [])]


def user_count():
    return User.query.count()


# --- the challenge on the page -------------------------------------------------

class TestRegisterPage:
    def test_carries_the_challenge_json_and_the_widget(self, altcha_app, client):
        page = client.get('/riftbound/register').get_data(as_text=True)
        challenge = challenge_of(page)
        assert set(challenge) == {'algorithm', 'challenge', 'maxNumber', 'salt', 'signature'}
        assert challenge['maxNumber'] == 1000
        assert '<altcha-widget' in page
        assert 'vendor/altcha/altcha.min.js' in page

    def test_every_visit_gets_a_new_challenge(self, altcha_app, client):
        first = challenge_of(client.get('/riftbound/register').get_data(as_text=True))
        second = challenge_of(client.get('/riftbound/register').get_data(as_text=True))
        assert first['challenge'] != second['challenge']

    def test_challenge_expires_after_the_configured_ttl(self, altcha_app, client, frozen_clock):
        challenge = challenge_of(client.get('/riftbound/register').get_data(as_text=True))
        expires = int(re.search(r'expires=(\d+)', challenge['salt']).group(1))
        epoch = frozen_clock.now.replace(tzinfo=__import__('datetime').timezone.utc).timestamp()
        assert expires == int(epoch) + 300                                   # R11

    def test_login_page_has_no_widget(self, altcha_app, client):
        assert '<altcha-widget' not in client.get('/riftbound/login').get_data(as_text=True)

    def test_provider_none_renders_no_widget_and_no_script(self, client):
        page = client.get('/riftbound/register').get_data(as_text=True)
        assert '<altcha-widget' not in page
        assert 'altcha' not in page.lower()


# --- verification through the register form ----------------------------------------

class TestRegisterWithAltcha:
    def test_missing_payload_is_rejected_and_the_form_is_shown_again(self, altcha_app, client):
        resp = register(client)
        assert resp.status_code == 302
        assert user_count() == 0
        assert any('captcha' in m.lower() for m in flashes(client))
        page = client.get('/riftbound/register').get_data(as_text=True)
        assert 'captcha' in page.lower() and '<altcha-widget' in page

    def test_a_solved_challenge_creates_a_plain_user(self, altcha_app, client):
        resp = register(client, fresh_payload(client))
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/riftbound/login')
        user = User.query.filter_by(username='newbie').one()
        assert user.is_admin is False

    def test_the_extra_fields_the_widget_adds_are_tolerated(self, altcha_app, client):
        challenge = challenge_of(client.get('/riftbound/register').get_data(as_text=True))
        assert register(client, solve(challenge, took=123)).status_code == 302
        assert user_count() == 1

    def test_a_payload_cannot_be_used_twice(self, altcha_app, client):
        payload = fresh_payload(client)
        assert register(client, payload).status_code == 302
        assert user_count() == 1
        replay = register(client, payload, username='second', email='second@test.com')
        assert replay.status_code == 302
        assert user_count() == 1
        assert User.query.filter_by(username='second').count() == 0
        assert any('captcha' in m.lower() for m in flashes(client))

    def test_the_replay_store_keeps_the_sha256_of_the_challenge(self, altcha_app, client):
        challenge = challenge_of(client.get('/riftbound/register').get_data(as_text=True))
        register(client, solve(challenge))
        [row] = RbCaptchaUsed.query.all()
        assert row.rbcap_hash == hashlib.sha256(challenge['challenge'].encode()).hexdigest()
        assert len(row.rbcap_hash) == 64

    def test_an_expired_payload_is_rejected(self, altcha_app, client, frozen_clock):
        payload = fresh_payload(client)
        frozen_clock.advance(minutes=5, seconds=2)
        register(client, payload)
        assert user_count() == 0
        assert any('captcha' in m.lower() for m in flashes(client))

    def test_a_payload_just_inside_the_ttl_is_accepted(self, altcha_app, client, frozen_clock):
        payload = fresh_payload(client)
        frozen_clock.advance(minutes=4, seconds=50)
        assert register(client, payload).status_code == 302
        assert user_count() == 1

    @pytest.mark.parametrize('tamper', [
        {'signature': '0' * 64}, {'challenge': 'f' * 64}, {'salt': 'abcdef0123456789&'},
        {'number': 7}, {'algorithm': 'SHA-1'}])
    def test_a_tampered_payload_is_rejected(self, altcha_app, client, tamper):
        challenge = challenge_of(client.get('/riftbound/register').get_data(as_text=True))
        register(client, solve(challenge, **tamper))
        assert user_count() == 0

    def test_extending_the_expiry_inside_the_salt_is_rejected(self, altcha_app, client):
        challenge = challenge_of(client.get('/riftbound/register').get_data(as_text=True))
        forged_salt = re.sub(r'expires=\d+', 'expires=9999999999', challenge['salt'])
        payload = base64.b64encode(json.dumps({
            'algorithm': challenge['algorithm'], 'challenge': challenge['challenge'],
            'number': 0, 'salt': forged_salt, 'signature': challenge['signature']}).encode()).decode()
        register(client, payload)
        assert user_count() == 0

    def test_a_challenge_signed_with_another_key_is_rejected(self, altcha_app, client):
        foreign = create_challenge_v1(ChallengeOptionsV1(hmac_key='some-other-key', max_number=1000))
        register(client, solve(foreign.to_dict()))
        assert user_count() == 0

    @pytest.mark.parametrize('garbage', ['', 'not base64 at all', 'e30=', 'W10=', 'bnVsbA==',
                                         base64.b64encode(b'{"number": "x"}').decode()])
    def test_garbage_payloads_are_rejected_without_an_error(self, altcha_app, client, garbage):
        resp = register(client, garbage)
        assert resp.status_code == 302
        assert user_count() == 0

    def test_invalid_fields_do_not_burn_the_payload(self, altcha_app, client):
        payload = fresh_payload(client)
        register(client, payload, username='ab')               # rejected by the schema first
        assert user_count() == 0 and RbCaptchaUsed.query.count() == 0
        assert register(client, payload).status_code == 302    # the same payload still works
        assert user_count() == 1

    def test_the_database_stays_usable_after_a_replay(self, altcha_app, client):
        payload = fresh_payload(client)
        register(client, payload)
        register(client, payload, username='x' * 5, email='x5@test.com')
        assert User.query.count() == 1                           # no poisoned transaction
        assert RbCaptchaUsed.query.count() == 1

    def test_provider_none_needs_no_payload(self, app, client):
        assert app.config['CAPTCHA_PROVIDER'] == 'none'
        assert register(client).status_code == 302
        assert user_count() == 1


# --- provider unit tests -------------------------------------------------------------

class TestProviders:
    def test_the_none_provider_has_no_challenge_and_accepts_anything(self, app):
        provider = captcha.get_captcha_provider()
        assert provider.name == 'none'
        assert provider.challenge() is None
        assert provider.verify(None) is True
        assert provider.verify('whatever') is True

    def test_altcha_provider_is_chosen_by_config(self, altcha_app):
        provider = captcha.get_captcha_provider()
        assert provider.name == 'altcha'
        assert provider.verify(None) is False
        assert provider.verify('') is False

    def test_hmac_key_defaults_to_hmac_sha256_of_the_secret_key(self, altcha_app):
        altcha_app.config['ALTCHA_HMAC_KEY'] = None
        expected = hmac.new(altcha_app.config['SECRET_KEY'].encode(), b'altcha',
                            hashlib.sha256).hexdigest()
        assert captcha.altcha_hmac_key(altcha_app.config) == expected
        # a challenge from the provider verifies against that very key
        provider = captcha.get_captcha_provider()
        assert provider.verify(solve(provider.challenge())) is True

    def test_an_explicit_hmac_key_wins(self, altcha_app):
        altcha_app.config['ALTCHA_HMAC_KEY'] = 'explicit-key-for-the-test'
        assert captcha.altcha_hmac_key(altcha_app.config) == 'explicit-key-for-the-test'
        provider = captcha.get_captcha_provider()
        assert provider.verify(solve(provider.challenge())) is True
        # ... and the derived key no longer matches
        altcha_app.config['ALTCHA_HMAC_KEY'] = None
        assert captcha.get_captcha_provider().verify(solve(provider.challenge())) is False

    def test_expired_replay_rows_are_purged_on_verify(self, altcha_app, frozen_clock):
        now = clock.utcnow()
        db.session.add_all([
            RbCaptchaUsed(rbcap_hash='a' * 64, rbcap_expires_at=now - timedelta(seconds=1)),
            RbCaptchaUsed(rbcap_hash='b' * 64, rbcap_expires_at=now - timedelta(hours=3)),
            RbCaptchaUsed(rbcap_hash='c' * 64, rbcap_expires_at=now + timedelta(minutes=2)),
        ])
        db.session.commit()
        provider = captcha.get_captcha_provider()
        assert provider.verify(solve(provider.challenge())) is True
        assert {r.rbcap_hash for r in RbCaptchaUsed.query.all()} >= {'c' * 64}
        assert 'a' * 64 not in {r.rbcap_hash for r in RbCaptchaUsed.query.all()}
        assert 'b' * 64 not in {r.rbcap_hash for r in RbCaptchaUsed.query.all()}
        assert RbCaptchaUsed.query.count() == 2             # the live row + this verification

    def test_purge_also_runs_when_the_payload_is_bad(self, altcha_app, frozen_clock):
        db.session.add(RbCaptchaUsed(rbcap_hash='a' * 64,
                                     rbcap_expires_at=clock.utcnow() - timedelta(minutes=1)))
        db.session.commit()
        assert captcha.get_captcha_provider().verify('garbage') is False
        assert RbCaptchaUsed.query.count() == 0

    def test_replayed_rows_live_until_the_challenge_would_have_expired(self, altcha_app,
                                                                       frozen_clock):
        provider = captcha.get_captcha_provider()
        payload = solve(provider.challenge())
        assert provider.verify(payload) is True
        [row] = RbCaptchaUsed.query.all()
        assert row.rbcap_expires_at == frozen_clock.now + timedelta(seconds=300)
        frozen_clock.advance(minutes=4)
        assert provider.verify(payload) is False             # still remembered
