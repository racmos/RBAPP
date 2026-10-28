"""
Authorization matrix (ACL-5).

Every URL rule of the app is classified exactly once as

  P  public         anyone, including anonymous
  U  authenticated  anonymous is sent to the login page
  A  admin          anonymous goes to login, a plain user gets 403, an admin passes

in the explicit table below. A rule the table does not know fails the suite and
is named in the message, so adding a route forces a decision. `fnmatch`
wildcards cover whole blueprints (`price.*`, `landing.*`). Units d and e add
their rules here.

"Anonymous denial" has two shapes (API-8, R14): HTML clients (no Accept, or a
browser's) get a 302 to the login page; JSON clients (`Accept: application/json`,
a JSON body) and everything under /riftbound/api/ get a JSON 401, never a
redirect.

No test here may reach the internet: `requests.Session.request` is replaced by
a recorder that raises, and the A-class tests assert nothing was recorded for a
plain user.
"""
import re
from fnmatch import fnmatchcase
from types import SimpleNamespace

import pytest
import requests

from tests.conftest import login_as

# endpoint pattern -> class
MATRIX = {
    # --- public -----------------------------------------------------------
    'static': 'P',
    'media.card_image': 'P',                # card images from CARD_IMAGES_DIR (M-d)
    'landing.*': 'P',                       # landing page, HTMX partials, frames
    'auth.login': 'P',
    'auth.register': 'P',
    'api_v1.health': 'P',                   # JSON API v1 (unit e)
    'api_v1.meta_config': 'P',
    'api_v1.meta_game': 'P',                      # game metadata for the catalog UI (F2-b)
    'api_v1.auth_session': 'P',
    'api_v1.auth_captcha': 'P',
    'api_v1.auth_login': 'P',
    'api_v1.auth_register': 'P',
    'spa.*': 'P',                           # SPA shell (F1 unit b): the SPA hosts the login screen
    # --- authenticated ----------------------------------------------------
    'auth.logout': 'U',
    'api_v1.auth_logout': 'U',
    'api_v1.get_me_prefs': 'U',             # unit c of f1-app-shell
    'api_v1.patch_me_prefs': 'U',
    'api_v1.list_bans': 'U',                # F2 unit a (D-F2-3)
    'api_v1.list_cards': 'U',                # F2 unit c
    'api_v1.get_card': 'U',                  # F2 unit d
    'api_v1.list_collection_groups': 'U',    # F3 unit b
    'api_v1.create_collection_line': 'U',    # F3 unit c
    'api_v1.update_collection_line': 'U',
    'api_v1.delete_collection_line': 'U',
    'api_v1.split_collection_line': 'U',
    'api_v1.bulk_collection_lines': 'U',
    'api_v1.keep_collection_playset': 'U',
    'api_v1.get_card_prices': 'U',           # F2 unit d
    'main.dashboard': 'U',
    'sets.sets': 'U',
    'cards.cards': 'U',
    'collection.*': 'U',
    'deck.*': 'U',
    'profile.*': 'U',
    # --- admin ------------------------------------------------------------
    'sets.add_set': 'A',
    'sets.update_set': 'A',
    'cards.add_card': 'A',
    'cards.update_card': 'A',
    'cards.upload_card_image': 'A',
    'price.*': 'A',                         # all 23 routes, including future ones
    'api_admin.*': 'A',                     # /riftbound/api/v1/admin/* (F13-a)
}

LOGIN_PATH = '/riftbound/login'
API_PREFIX = '/riftbound/api/'
# Endpoints that end the caller's session: always requested last.
LOGOUT_ENDPOINTS = ('auth.logout', 'api_v1.auth_logout')
JSON = {'Accept': 'application/json'}


def classify(rule):
    """The class (P/U/A) of one rule, or raise naming it when the table has no
    entry (or more than one)."""
    matches = {pattern for pattern in MATRIX if fnmatchcase(rule.endpoint, pattern)}
    if not matches:
        raise AssertionError(
            f'unclassified rule {rule.rule!r} (endpoint {rule.endpoint!r}): '
            'add it to MATRIX in tests/test_authz_matrix.py as P, U or A')
    classes = {MATRIX[pattern] for pattern in matches}
    if len(matches) > 1:
        raise AssertionError(
            f'rule {rule.rule!r} (endpoint {rule.endpoint!r}) is classified more '
            f'than once: {sorted(matches)}')
    return classes.pop()


def sample_url(rule):
    """A concrete URL for `rule`: ints get 1, every other converter gets 'x'."""
    def fill(match):
        return '1' if match.group(0).startswith('<int:') else 'x'
    return re.sub(r'<[^>]+>', fill, rule.rule)


def method_for(rule):
    methods = rule.methods - {'HEAD', 'OPTIONS'}
    return 'GET' if 'GET' in methods else sorted(methods)[0]


def call(client, rule, **headers):
    """Request `rule` with an empty form (no JSON, no Accept unless given) so the
    answer is what a plain browser form post would get."""
    method = method_for(rule)
    url = sample_url(rule)
    if method == 'GET':
        return client.get(url, headers=headers)
    return client.open(url, method=method, data={}, headers=headers)


def is_login_redirect(resp):
    return resp.status_code == 302 and resp.headers.get('Location', '').startswith(LOGIN_PATH)


def is_json_401(resp):
    body = resp.get_json(silent=True) or {}
    return (resp.status_code == 401 and 'Location' not in resp.headers
            and body.get('success') is False and body.get('error') == 'Unauthorized')


def is_denied(resp):
    return resp.status_code in (401, 403) or is_login_redirect(resp)


@pytest.fixture
def outbound(monkeypatch):
    """Record (and refuse) every HTTP request made through `requests`."""
    calls = []

    def refuse(self, method, url, *args, **kwargs):
        calls.append((method, url))
        raise requests.ConnectionError('network disabled in tests')

    monkeypatch.setattr(requests.Session, 'request', refuse)
    return calls


@pytest.fixture
def rules(app):
    """Every rule, with the logouts last: they end the session of the client that calls them."""
    return sorted(app.url_map.iter_rules(),
                  key=lambda r: (r.endpoint in LOGOUT_ENDPOINTS, r.endpoint, r.rule))


def failures_for(rules_, wanted_class, check):
    failed = []
    for rule in rules_:
        if classify(rule) != wanted_class:
            continue
        problem = check(rule)
        if problem:
            failed.append(f'{method_for(rule)} {rule.rule} ({rule.endpoint}): {problem}')
    return failed


def expect_login_redirect(client):
    """Anonymous denial for a plain (HTML) client: a redirect to the login page,
    except under /riftbound/api/, which always answers a JSON 401."""
    def check(rule):
        resp = call(client, rule)
        if rule.rule.startswith(API_PREFIX):
            if not is_json_401(resp):
                return f'expected a JSON 401 under the API prefix, got {resp.status_code}'
        elif not is_login_redirect(resp):
            return f'expected a redirect to {LOGIN_PATH}, got {resp.status_code}'
    return check


# ---------------------------------------------------------------------------
# The table itself
# ---------------------------------------------------------------------------

class TestMatrixIsComplete:
    def test_every_rule_of_the_app_is_classified_exactly_once(self, rules):
        assert len(rules) > 60                  # the whole url_map, not an empty list
        assert {classify(rule) for rule in rules} == {'P', 'U', 'A'}

    def test_an_unclassified_rule_fails_naming_it(self):
        rule = SimpleNamespace(rule='/riftbound/brand-new', endpoint='brandnew.index')
        with pytest.raises(AssertionError) as err:
            classify(rule)
        assert '/riftbound/brand-new' in str(err.value)
        assert 'brandnew.index' in str(err.value)

    def test_a_rule_matched_by_two_entries_fails(self, monkeypatch):
        monkeypatch.setitem(MATRIX, 'sets.*', 'U')              # overlaps 'sets.sets'
        rule = SimpleNamespace(rule='/riftbound/set', endpoint='sets.sets')
        with pytest.raises(AssertionError, match='more than once'):
            classify(rule)

    def test_no_table_entry_is_stale(self, rules):
        for pattern in MATRIX:
            assert any(fnmatchcase(rule.endpoint, pattern) for rule in rules), (
                f'MATRIX entry {pattern!r} matches no rule; remove it')

    def test_all_price_routes_are_admin_only(self, rules):
        price_rules = [r for r in rules if r.endpoint.startswith('price.')]
        assert len(price_rules) == 23
        assert {classify(r) for r in price_rules} == {'A'}


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------

class TestPublicRules:
    def test_anonymous_is_never_denied(self, app, client, rules, outbound):
        def check(rule):
            resp = call(client, rule)
            if is_denied(resp):
                return f'denied with {resp.status_code}'
        failed = failures_for(rules, 'P', check)
        assert not failed, '\n'.join(failed)

    def test_logged_in_users_are_not_denied_either(self, app, authenticated_client, rules, outbound):
        def check(rule):
            resp = call(authenticated_client, rule)
            if resp.status_code in (401, 403):
                return f'denied with {resp.status_code}'
        failed = failures_for(rules, 'P', check)
        assert not failed, '\n'.join(failed)


class TestSpaIsPublic:
    """HOST-1: the SPA routes are public (F1 unit b)."""

    def test_the_spa_rules_are_classified_public(self, rules):
        spa_rules = [r for r in rules if r.endpoint.startswith('spa.')]
        assert len(spa_rules) == 2
        assert {classify(r) for r in spa_rules} == {'P'}

    @pytest.mark.parametrize('url', ['/riftbound/app/', '/riftbound/app/account/interface'])
    def test_anonymous_gets_the_shell(self, spa_app, client, url):
        assert client.get(url).status_code == 200


class TestAuthenticatedRules:
    def test_anonymous_is_sent_to_the_login_page(self, app, client, rules, outbound):
        failed = failures_for(rules, 'U', expect_login_redirect(client))
        assert not failed, '\n'.join(failed)

    def test_ordinary_users_and_admins_get_through(self, app, authenticated_client,
                                                   admin_client, rules, outbound):
        def check(rule):
            for who, client, username in (('user', authenticated_client, 'testuser'),
                                          ('admin', admin_client, 'admin')):
                if rule.endpoint in LOGOUT_ENDPOINTS:
                    # An earlier logout rule ended this session: start a new one.
                    login_as(client, username)
                resp = call(client, rule)
                if rule.endpoint in LOGOUT_ENDPOINTS:
                    # Logging out answers 302 (form) or 200 (API) by design: prove
                    # it ran with a live session by checking the session is gone.
                    if resp.status_code not in (200, 302) or client.get('/riftbound/').status_code != 302:
                        return f'{who}: logout did not end the session'
                elif is_denied(resp):
                    return f'{who} was denied with {resp.status_code}'
        failed = failures_for(rules, 'U', check)
        assert not failed, '\n'.join(failed)


class TestAdminRules:
    def test_anonymous_is_sent_to_the_login_page_never_403(self, app, client, rules, outbound):
        failed = failures_for(rules, 'A', expect_login_redirect(client))
        assert not failed, '\n'.join(failed)

    def test_a_plain_user_gets_403_and_causes_no_outbound_request(
            self, app, authenticated_client, rules, outbound):
        def check(rule):
            resp = call(authenticated_client, rule)
            if resp.status_code != 403:
                return f'expected 403, got {resp.status_code}'
        failed = failures_for(rules, 'A', check)
        assert not failed, '\n'.join(failed)
        assert outbound == []

    def test_an_admin_passes_the_guard(self, app, admin_client, rules, outbound):
        def check(rule):
            resp = call(admin_client, rule)
            if is_denied(resp):
                return f'admin was denied with {resp.status_code}'
        failed = failures_for(rules, 'A', check)
        assert not failed, '\n'.join(failed)


# ---------------------------------------------------------------------------
# Anonymous JSON clients (API-8, R14)
# ---------------------------------------------------------------------------

class TestAnonymousJsonClients:
    def test_every_protected_rule_answers_a_json_401(self, app, client, rules, outbound):
        def check(rule):
            resp = call(client, rule, **JSON)
            if not is_json_401(resp):
                return f'expected a JSON 401, got {resp.status_code} {resp.content_type}'
        failed = failures_for(rules, 'U', check) + failures_for(rules, 'A', check)
        assert not failed, '\n'.join(failed)

    def test_both_protected_classes_were_checked(self, rules):
        assert sum(classify(r) == 'U' for r in rules) > 10
        assert sum(classify(r) == 'A' for r in rules) > 25

    def test_a_json_body_alone_is_enough(self, app, client, rules, outbound):
        post_rules = [r for r in rules if classify(r) in ('U', 'A') and 'POST' in r.methods]
        assert len(post_rules) > 20

        def check(rule):
            resp = client.post(sample_url(rule), json={})
            if not is_json_401(resp):
                return f'expected a JSON 401, got {resp.status_code}'
        failed = failures_for(post_rules, 'U', check) + failures_for(post_rules, 'A', check)
        assert not failed, '\n'.join(failed)
        assert outbound == []

    def test_public_rules_never_answer_401_to_anonymous_json_clients(self, app, client, rules,
                                                                    outbound):
        def check(rule):
            resp = call(client, rule, **JSON)
            if resp.status_code in (401, 403):
                return f'denied with {resp.status_code}'
        failed = failures_for(rules, 'P', check)
        assert not failed, '\n'.join(failed)
