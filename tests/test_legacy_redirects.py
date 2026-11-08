"""Old Jinja URLs after the retirement of the Jinja web (PR 3/3).

`/`, `/riftbound` and the bookmarks of the old pages answer a 302 (not 301: the
landing page comes back in F8) to the matching screen of the React app. They are
public, GET (and HEAD) only, and never touch the session. An anonymous browser
that reaches a protected non-API page is sent to the app's login screen with
`next` = the path and query it asked for.
"""
import pytest
from flask_login import login_required

APP = '/riftbound/app/'

REDIRECTS = [
    ('/', APP),
    ('/riftbound', APP),
    ('/riftbound/', APP),
    ('/riftbound/login', '/riftbound/app/login'),
    ('/riftbound/register', '/riftbound/app/register'),
    ('/riftbound/card', '/riftbound/app/cards'),
    ('/riftbound/collection', '/riftbound/app/collection'),
    ('/riftbound/deck', '/riftbound/app/decks'),
    ('/riftbound/deck/view/7', '/riftbound/app/decks'),
    ('/riftbound/deck/view/My%20Deck', '/riftbound/app/decks'),
    ('/riftbound/profile', '/riftbound/app/account/profile'),
    ('/riftbound/price', '/riftbound/app/admin/cardmarket'),
    ('/riftbound/set', APP),
]


@pytest.mark.parametrize('path, target', REDIRECTS)
class TestEachOldUrl:
    def test_get_is_a_302_to_the_app(self, client, path, target):
        resp = client.get(path)
        assert resp.status_code == 302
        assert resp.headers['Location'] == target

    def test_head_is_the_same_302(self, client, path, target):
        resp = client.head(path)
        assert resp.status_code == 302
        assert resp.headers['Location'] == target

    def test_post_is_a_405(self, client, path, target):
        resp = client.post(path, data={})
        assert resp.status_code == 405
        assert 'Location' not in resp.headers

    def test_the_session_is_never_touched(self, client, path, target):
        assert 'Set-Cookie' not in client.get(path).headers

    def test_a_signed_in_user_gets_the_same_redirect(self, authenticated_client, path, target):
        resp = authenticated_client.get(path)
        assert (resp.status_code, resp.headers['Location']) == (302, target)


def test_query_strings_of_the_other_pages_are_dropped(client):
    resp = client.get('/riftbound/collection?set=OGN&page=2')
    assert resp.headers['Location'] == '/riftbound/app/collection'


def test_post_with_csrf_on_is_still_a_405(csrf_app, client):
    assert client.post('/riftbound/login', data={'username': 'u'}).status_code == 405


class TestLoginNext:
    @pytest.mark.parametrize('next_, encoded', [
        ('/riftbound/collection', '%2Friftbound%2Fcollection'),
        ('/riftbound/app/decks/3?tab=stats', '%2Friftbound%2Fapp%2Fdecks%2F3%3Ftab%3Dstats'),
    ])
    def test_a_safe_next_is_kept(self, client, next_, encoded):
        resp = client.get('/riftbound/login', query_string={'next': next_})
        assert resp.status_code == 302
        assert resp.headers['Location'] == f'/riftbound/app/login?next={encoded}'

    @pytest.mark.parametrize('next_', [
        '',
        'https://evil.example/riftbound/',
        '//evil.example/riftbound/',
        '/other/path',
        '/riftbound/../etc/passwd',
        '/riftbound/%2e%2e/admin',
        '/riftbound/%252e%252e/admin',
        '/riftbound/\\evil',
        '/riftbound/a\nb',
        '/riftbound/%0aSet-Cookie',
    ])
    def test_an_unsafe_next_is_dropped(self, client, next_):
        resp = client.get('/riftbound/login', query_string={'next': next_})
        assert resp.status_code == 302
        assert resp.headers['Location'] == '/riftbound/app/login'

    def test_register_ignores_next(self, client):
        resp = client.get('/riftbound/register?next=%2Friftbound%2Fcollection')
        assert resp.headers['Location'] == '/riftbound/app/register'


# --- Not signed in on a protected non-API page --------------------------------------

@pytest.fixture
def protected_app(app):
    """`app` with a test-only protected HTML route (added before the first request)."""
    @app.route('/riftbound/test-protected')
    @login_required
    def _protected():
        return 'secret page'
    return app


class TestUnauthorized:
    def test_a_browser_goes_to_the_app_login_with_next(self, protected_app, client):
        resp = client.get('/riftbound/test-protected')
        assert resp.status_code == 302
        assert resp.headers['Location'] == \
            '/riftbound/app/login?next=%2Friftbound%2Ftest-protected'

    def test_next_keeps_the_query(self, protected_app, client):
        resp = client.get('/riftbound/test-protected?a=1&b=x%20y')
        assert resp.headers['Location'] == \
            '/riftbound/app/login?next=%2Friftbound%2Ftest-protected%3Fa%3D1%26b%3Dx%2520y'

    def test_no_flash_is_stored(self, protected_app, client):
        resp = client.get('/riftbound/test-protected', headers={'Accept': 'text/html'})
        assert resp.status_code == 302
        assert 'Set-Cookie' not in resp.headers

    def test_a_json_client_still_gets_a_json_401(self, protected_app, client):
        resp = client.get('/riftbound/test-protected', headers={'Accept': 'application/json'})
        assert resp.status_code == 401
        assert 'Location' not in resp.headers
        assert resp.get_json() == {'success': False, 'error': 'Unauthorized',
                                   'message': 'Authentication is required',
                                   'code': 'unauthenticated'}

    def test_the_api_still_answers_a_json_401(self, client):
        resp = client.get('/riftbound/api/v1/me/prefs')
        assert resp.status_code == 401
        assert resp.get_json()['code'] == 'unauthenticated'

    def test_a_signed_in_user_gets_the_page(self, protected_app, authenticated_client):
        resp = authenticated_client.get('/riftbound/test-protected')
        assert (resp.status_code, resp.get_data(as_text=True)) == (200, 'secret page')
