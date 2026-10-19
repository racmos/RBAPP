"""JSON vs HTML negotiation of errors and of "not logged in" (API-8, D18).

An error or unauthorized answer is JSON when the path is under
/riftbound/api/, or the body is JSON, or Accept prefers application/json over
text/html (a bare `*/*` counts as JSON, as `fetch` sends it). Otherwise it is
HTML, and a request WITHOUT an Accept header is HTML (the baseline tests rely
on it).
"""
import pytest

from app.errors import wants_json

BROWSER = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'


def is_json_envelope(resp, status, error):
    body = resp.get_json()
    return (resp.status_code == status and resp.content_type.startswith('application/json')
            and body['success'] is False and body['error'] == error and bool(body['message']))


# ---------------------------------------------------------------------------
# The predicate itself
# ---------------------------------------------------------------------------

class TestWantsJson:
    @pytest.mark.parametrize('path,headers,expected', [
        ('/riftbound/nope', {}, False),                                   # no Accept: HTML
        ('/riftbound/nope', {'Accept': BROWSER}, False),
        ('/riftbound/nope', {'Accept': 'text/html'}, False),
        ('/riftbound/nope', {'Accept': '*/*'}, True),                     # fetch default
        ('/riftbound/nope', {'Accept': 'application/json'}, True),
        ('/riftbound/nope', {'Accept': 'application/json, text/plain, */*'}, True),
        ('/riftbound/nope', {'Accept': 'text/html;q=0.5, application/json'}, True),
        ('/riftbound/nope', {'Accept': 'text/html, application/json;q=0.5'}, False),
        ('/riftbound/api/v1/nope', {}, True),                              # API prefix wins
        ('/riftbound/api/v1/nope', {'Accept': 'text/html'}, True),
        ('/riftbound/collection/api/sets', {}, False),                     # legacy /api/ is not the prefix
        ('/api/noticias', {}, False),                                      # landing partials neither
    ])
    def test_by_path_and_accept(self, app, path, headers, expected):
        with app.test_request_context(path, headers=headers):
            assert wants_json() is expected

    def test_a_json_body_is_json_whatever_the_accept(self, app):
        with app.test_request_context('/riftbound/nope', method='POST', json={'a': 1},
                                      headers={'Accept': 'text/html'}):
            assert wants_json() is True

    def test_a_form_body_without_accept_is_html(self, app):
        with app.test_request_context('/riftbound/nope', method='POST', data={'a': '1'}):
            assert wants_json() is False


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------

class TestNotFound:
    def test_browser_gets_an_html_404(self, client):
        resp = client.get('/riftbound/nope', headers={'Accept': BROWSER})
        assert resp.status_code == 404
        assert resp.content_type.startswith('text/html')

    def test_no_accept_gets_an_html_404(self, client):
        resp = client.get('/riftbound/nope')
        assert resp.status_code == 404
        assert resp.content_type.startswith('text/html')

    def test_fetch_wildcard_gets_a_json_404(self, client):
        assert is_json_envelope(client.get('/riftbound/nope', headers={'Accept': '*/*'}),
                                404, 'Not Found')

    def test_api_path_gets_json_even_for_a_browser(self, client):
        assert is_json_envelope(client.get('/riftbound/api/v1/x', headers={'Accept': BROWSER}),
                                404, 'Not Found')


# ---------------------------------------------------------------------------
# Not logged in
# ---------------------------------------------------------------------------

class TestUnauthorized:
    def test_no_accept_on_a_protected_page_redirects_to_login(self, client):
        resp = client.get('/riftbound/')
        assert resp.status_code == 302
        assert resp.headers['Location'].startswith('/riftbound/login')

    def test_the_redirect_keeps_the_next_parameter_and_the_flash(self, client):
        resp = client.get('/riftbound/set', headers={'Accept': BROWSER})
        assert resp.status_code == 302
        assert resp.headers['Location'] == '/riftbound/login?next=%2Friftbound%2Fset'
        with client.session_transaction() as sess:
            assert sess['_flashes'] == [('message', 'Please log in to access this page.')]

    def test_json_accept_gets_a_json_401(self, client):
        resp = client.get('/riftbound/collection/api/sets', headers={'Accept': 'application/json'})
        assert is_json_envelope(resp, 401, 'Unauthorized')
        assert 'Location' not in resp.headers

    def test_fetch_wildcard_gets_a_json_401(self, client):
        resp = client.get('/riftbound/collection/api/sets', headers={'Accept': '*/*'})
        assert is_json_envelope(resp, 401, 'Unauthorized')

    def test_a_json_body_gets_a_json_401(self, client):
        resp = client.post('/riftbound/collection/add', json={'a': 1})
        assert is_json_envelope(resp, 401, 'Unauthorized')

    def test_an_admin_route_is_401_json_for_anonymous_json_clients(self, client):
        resp = client.post('/riftbound/set/add', json={'a': 1})
        assert is_json_envelope(resp, 401, 'Unauthorized')

    def test_api_paths_are_json_without_any_header(self, client):
        assert is_json_envelope(client.post('/riftbound/api/v1/auth/logout'), 401, 'Unauthorized')

    def test_a_logged_in_user_is_not_affected(self, authenticated_client):
        resp = authenticated_client.get('/riftbound/collection/api/sets',
                                        headers={'Accept': 'application/json'})
        assert resp.status_code == 200

    def test_a_plain_user_on_an_admin_route_is_still_403_json_or_html(self, authenticated_client):
        json_resp = authenticated_client.post('/riftbound/set/add', json={'a': 1})
        assert is_json_envelope(json_resp, 403, 'Forbidden')
        html_resp = authenticated_client.post('/riftbound/set/add', data={},
                                              headers={'Accept': BROWSER})
        assert html_resp.status_code == 403
        assert html_resp.content_type.startswith('text/html')


# ---------------------------------------------------------------------------
# Other errors use the same predicate
# ---------------------------------------------------------------------------

class TestOtherErrors:
    def test_405_under_the_api_is_json(self, client):
        assert is_json_envelope(client.post('/riftbound/api/v1/health'), 405, 'Method Not Allowed')

    def test_405_for_a_browser_is_html(self, client):
        resp = client.get('/riftbound/logout', headers={'Accept': BROWSER})
        assert resp.status_code == 405
        assert resp.content_type.startswith('text/html')

    def test_405_for_a_fetch_is_json_with_the_allow_header(self, client):
        resp = client.get('/riftbound/logout', headers={'Accept': '*/*'})
        assert is_json_envelope(resp, 405, 'Method Not Allowed')
        assert 'POST' in resp.headers['Allow']

    def test_415_under_the_api_is_json(self, client):
        resp = client.post('/riftbound/api/v1/auth/login', data='x', content_type='text/plain')
        assert resp.is_json and resp.get_json()['success'] is False
        assert resp.status_code in (400, 415)

    def test_csrf_error_under_the_api_is_json(self, csrf_app, client):
        resp = client.post('/riftbound/api/v1/auth/login', json={'username': 'u', 'password': 'p'},
                           headers={'Accept': 'text/html'})
        assert is_json_envelope(resp, 400, 'CSRF Error')

    def test_csrf_error_for_a_browser_form_is_html(self, csrf_app, client):
        resp = client.post('/riftbound/login', data={'username': 'x'}, headers={'Accept': BROWSER})
        assert resp.status_code == 400
        assert resp.content_type.startswith('text/html')

    def test_csrf_error_for_a_form_without_accept_is_html(self, csrf_app, client):
        resp = client.post('/riftbound/login', data={'username': 'x'})
        assert resp.status_code == 400
        assert resp.content_type.startswith('text/html')

    def test_csrf_error_for_a_fetch_wildcard_is_json(self, csrf_app, client):
        resp = client.post('/riftbound/login', data={'username': 'x'}, headers={'Accept': '*/*'})
        assert is_json_envelope(resp, 400, 'CSRF Error')

    def test_429_follows_the_same_rule(self, limited_app, client, monkeypatch):
        from werkzeug.security import generate_password_hash
        from app.services import auth
        cheap = generate_password_hash('dummy', method='pbkdf2:sha256:1000')
        monkeypatch.setattr(auth, '_dummy_hash', lambda: cheap)
        for i in range(10):
            client.post('/riftbound/login', data={'username': f'g{i}', 'password': 'nope-nope'})
        html = client.post('/riftbound/login', data={'username': 'g', 'password': 'nope-nope'})
        assert html.status_code == 429
        assert html.content_type.startswith('text/html')
        fetch = client.post('/riftbound/login', data={'username': 'g', 'password': 'nope-nope'},
                            headers={'Accept': '*/*'})
        assert is_json_envelope(fetch, 429, 'Too Many Requests')
        assert fetch.headers['Retry-After'].isdigit()

    def test_an_unhandled_error_on_a_page_is_html_for_browsers(self, app, client):
        def boom():
            raise RuntimeError('internal detail')
        app.add_url_rule('/riftbound/boom-page', 'boom_page_for_test', boom)
        resp = client.get('/riftbound/boom-page', headers={'Accept': BROWSER})
        assert resp.status_code == 500
        assert resp.content_type.startswith('text/html')
        assert 'internal detail' not in resp.get_data(as_text=True)
        fetch = client.get('/riftbound/boom-page', headers={'Accept': '*/*'})
        assert is_json_envelope(fetch, 500, 'Internal Server Error')
        assert 'internal detail' not in fetch.get_data(as_text=True)
