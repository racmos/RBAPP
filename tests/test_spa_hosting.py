"""SPA hosting (F1 unit b, specs HOST-1..HOST-7).

`spa_bp` serves the Vite build from FRONTEND_DIST at /riftbound/app/. Every test
here points the app at a temporary dist (`spa_dist` / `spa_app` in conftest), so
the Python lane never needs Node (CI-9).

Layout:
  - TestExistingRoutes ....... HOST-1 "existing routes unaffected" (CHAR)
  - TestMountAndRedirect ..... HOST-1
  - TestCacheRules ........... HOST-2 (+ D3 pure helper)
  - TestExtensionAwareCatchAll HOST-3 (+ D2 pure helper)
  - TestMimetypes ............ HOST-4 (D4)
  - TestMissingBuild ......... HOST-5 (R11, D5)
  - TestNoSecretsInTheShell .. HOST-6
  - TestDocs ................. HOST-7
"""
import re
from pathlib import Path

import pytest

from tests.conftest import SPA_INDEX_HTML

ROOT = Path(__file__).resolve().parent.parent
BROWSER_ACCEPT = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'


def _static_file():
    """URL of a real file under app/static (pinned before spa_bp exists)."""
    return '/riftbound/static/css/style.css'


# ---------------------------------------------------------------------------
# HOST-1 "Existing routes unaffected" (CHAR: passes before and after spa_bp)
# ---------------------------------------------------------------------------

class TestExistingRoutes:
    def test_login_page(self, client):
        resp = client.get('/riftbound/login')
        assert resp.status_code == 200
        assert resp.content_type.startswith('text/html')

    def test_api_health(self, client):
        resp = client.get('/riftbound/api/v1/health')
        assert resp.status_code == 200
        assert resp.content_type.startswith('application/json')
        assert resp.get_json()['data']['status'] == 'ok'

    def test_static_file(self, client):
        resp = client.get(_static_file())
        assert resp.status_code == 200
        assert resp.content_type.startswith('text/css')

    def test_no_existing_rule_lives_under_the_spa_prefix(self, app):
        under = [r.rule for r in app.url_map.iter_rules()
                 if r.rule.startswith('/riftbound/app') and r.endpoint.split('.')[0] != 'spa']
        assert under == []

    def test_unknown_paths_next_to_the_prefix_still_404(self, client):
        assert client.get('/riftbound/application').status_code == 404


# ---------------------------------------------------------------------------
# HOST-1
# ---------------------------------------------------------------------------

class TestMountAndRedirect:
    def test_without_slash_redirects_to_the_slash(self, spa_app, client):
        resp = client.get('/riftbound/app')
        assert resp.status_code in (301, 302, 307, 308)
        assert resp.headers['Location'].endswith('/riftbound/app/')

    def test_entry_document_for_an_anonymous_client(self, spa_app, client):
        resp = client.get('/riftbound/app/')
        assert resp.status_code == 200
        assert resp.content_type.startswith('text/html')
        assert resp.get_data(as_text=True) == SPA_INDEX_HTML

    def test_head_is_allowed(self, spa_app, client):
        assert client.head('/riftbound/app/').status_code == 200

    def test_unsafe_methods_are_not_allowed(self, spa_app, client):
        resp = client.post('/riftbound/app/', data={})
        assert resp.status_code == 405

    def test_the_dist_is_read_per_request(self, spa_app, client, spa_dist):
        assert client.get('/riftbound/app/').status_code == 200
        (spa_dist / 'index.html').write_text('<!doctype html><p>v2</p>', encoding='utf-8')
        assert client.get('/riftbound/app/').get_data(as_text=True) == '<!doctype html><p>v2</p>'


# ---------------------------------------------------------------------------
# HOST-2 / D3
# ---------------------------------------------------------------------------

IMMUTABLE = 'public, max-age=31536000, immutable'


class TestCacheControlHelper:
    @pytest.mark.parametrize('path', ['assets/app-abc123.js', 'assets/fonts/x.woff2',
                                      'assets/img.webp'])
    def test_hashed_assets_are_immutable(self, path):
        from app.routes.spa import _cache_control
        assert _cache_control(path) == IMMUTABLE

    @pytest.mark.parametrize('path', ['index.html', 'sw.js', 'workbox-1a2b3c.js', 'registerSW.js',
                                      'manifest.webmanifest', 'pwa-192x192.png', 'favicon.ico',
                                      'account/interface', '', 'assetsfoo/x.js'])
    def test_everything_else_revalidates(self, path):
        from app.routes.spa import _cache_control
        assert _cache_control(path) == 'no-cache'


class TestCacheRules:
    def test_hashed_asset_is_immutable(self, spa_app, client):
        resp = client.get('/riftbound/app/assets/app-abc123.js')
        assert resp.status_code == 200
        cc = resp.headers['Cache-Control']
        assert 'public' in cc and 'max-age=31536000' in cc and 'immutable' in cc

    @pytest.mark.parametrize('url', ['/riftbound/app/', '/riftbound/app/index.html',
                                     '/riftbound/app/sw.js',
                                     '/riftbound/app/manifest.webmanifest'])
    def test_shell_files_revalidate(self, spa_app, client, url):
        cc = client.get(url).headers['Cache-Control']
        assert 'no-cache' in cc
        assert 'immutable' not in cc

    def test_icons_are_not_immutable(self, spa_app, client):
        resp = client.get('/riftbound/app/pwa-192x192.png')
        assert resp.status_code == 200
        assert 'immutable' not in resp.headers['Cache-Control']

    @pytest.mark.parametrize('url', ['/riftbound/app/sw.js', '/riftbound/app/',
                                     '/riftbound/app/assets/app-abc123.js'])
    def test_conditional_request_gets_304(self, spa_app, client, url):
        first = client.get(url)
        etag = first.headers['ETag']
        again = client.get(url, headers={'If-None-Match': etag})
        assert again.status_code == 304

    def test_the_fallback_document_revalidates_too(self, spa_app, client):
        resp = client.get('/riftbound/app/account/interface')
        assert 'no-cache' in resp.headers['Cache-Control']


# ---------------------------------------------------------------------------
# HOST-3 / D2
# ---------------------------------------------------------------------------

class TestFileLikeHelper:
    @pytest.mark.parametrize('path', ['a/b.js', 'x.woff2', 'x.map', 'assets/missing.css',
                                      'assets/a.js.map', 'logo.SVG'])
    def test_file_like(self, path):
        from app.routes.spa import _is_file_like
        assert _is_file_like(path)

    @pytest.mark.parametrize('path', ['account/interface', 'cards', '', 'account/',
                                      'a.b/c', 'x.toolongext1'])
    def test_routes(self, path):
        from app.routes.spa import _is_file_like
        assert not _is_file_like(path)


class TestExtensionAwareCatchAll:
    def test_deep_link_gets_the_shell(self, spa_app, client):
        resp = client.get('/riftbound/app/account/interface')
        assert resp.status_code == 200
        assert resp.content_type.startswith('text/html')
        assert resp.get_data(as_text=True) == SPA_INDEX_HTML
        assert 'no-cache' in resp.headers['Cache-Control']

    def test_a_directory_name_is_a_client_route(self, spa_app, client):
        resp = client.get('/riftbound/app/assets')
        assert resp.status_code == 200
        assert resp.get_data(as_text=True) == SPA_INDEX_HTML

    @pytest.mark.parametrize('path', ['assets/missing.js', 'missing.css', 'missing.woff2',
                                      'assets/missing.js.map'])
    def test_a_missing_file_is_a_real_404(self, spa_app, client, path):
        resp = client.get(f'/riftbound/app/{path}')
        assert resp.status_code == 404
        assert SPA_INDEX_HTML not in resp.get_data(as_text=True)

    @pytest.mark.parametrize('url', [
        '/riftbound/app/..%2Fsecret.txt',
        '/riftbound/app/../secret.txt',
        '/riftbound/app/%2e%2e/secret.txt',
        '/riftbound/app/assets/..%2F..%2Fsecret.txt',
        '/riftbound/app/..%2F..%2F..%2Fetc%2Fpasswd',
    ])
    def test_traversal_never_returns_the_file(self, spa_app, client, url):
        resp = client.get(url)
        body = resp.get_data(as_text=True)
        assert 'TOP-SECRET-OUTSIDE-DIST' not in body
        assert 'root:' not in body
        if resp.status_code == 200:                 # a route-looking path gets the shell
            assert body == SPA_INDEX_HTML

    def test_traversal_to_a_file_is_404(self, spa_app, client):
        assert client.get('/riftbound/app/..%2Fsecret.txt').status_code == 404

    def test_a_null_byte_is_not_a_500(self, spa_app, client):
        assert client.get('/riftbound/app/assets/x%00.js').status_code == 404


# ---------------------------------------------------------------------------
# HOST-4 / D4
# ---------------------------------------------------------------------------

class TestMimetypes:
    def test_map_entries(self):
        from app.routes.spa import SPA_MIMETYPES
        assert SPA_MIMETYPES['.webmanifest'] == 'application/manifest+json'
        assert SPA_MIMETYPES['.woff2'] == 'font/woff2'
        assert SPA_MIMETYPES['.webp'] == 'image/webp'
        assert SPA_MIMETYPES['.js'] == 'text/javascript'
        assert SPA_MIMETYPES['.svg'] == 'image/svg+xml'

    def test_manifest_content_type(self, spa_app, client):
        resp = client.get('/riftbound/app/manifest.webmanifest')
        assert resp.status_code == 200
        assert resp.headers['Content-Type'].startswith('application/manifest+json')

    @pytest.mark.parametrize('name, expected', [
        ('assets/app-abc123.js', 'text/javascript'),
        ('assets/font.woff2', 'font/woff2'),
        ('assets/bg.webp', 'image/webp'),
        ('assets/logo.svg', 'image/svg+xml'),
        ('pwa-192x192.png', 'image/png'),
    ])
    def test_content_types(self, spa_app, spa_dist, client, name, expected):
        target = spa_dist / name
        if not target.exists():
            target.write_bytes(b'x' * 8)
        resp = client.get(f'/riftbound/app/{name}')
        assert resp.status_code == 200
        assert resp.headers['Content-Type'].startswith(expected)


# ---------------------------------------------------------------------------
# HOST-5 / R11 / D5
# ---------------------------------------------------------------------------

@pytest.fixture(params=['missing-dir', 'no-index'])
def broken_dist(request, app, tmp_path):
    """FRONTEND_DIST that does not exist, or exists without index.html."""
    if request.param == 'missing-dir':
        path = tmp_path / 'nope'
    else:
        path = tmp_path / 'empty'
        path.mkdir()
        (path / 'sw.js').write_text('x', encoding='utf-8')
    app.config['FRONTEND_DIST'] = str(path)
    return path


class TestMissingBuild:
    @pytest.mark.parametrize('url', ['/riftbound/app/', '/riftbound/app/assets/x.js',
                                     '/riftbound/app/account/interface', '/riftbound/app/sw.js'])
    def test_browser_gets_minimal_html_503(self, broken_dist, client, url):
        resp = client.get(url, headers={'Accept': BROWSER_ACCEPT})
        assert resp.status_code == 503
        assert resp.content_type.startswith('text/html')
        body = resp.get_data(as_text=True)
        assert 'npm run build' in body
        assert resp.headers['Cache-Control'] == 'no-store'
        assert 'Set-Cookie' not in resp.headers
        assert 'csrf' not in body.lower()
        assert 'navbar' not in body and 'base.html' not in body and '<link' not in body

    def test_no_accept_header_is_html_too(self, broken_dist, client):
        resp = client.get('/riftbound/app/')
        assert resp.status_code == 503
        assert resp.content_type.startswith('text/html')

    @pytest.mark.parametrize('headers', [{'Accept': '*/*'}, {'Accept': 'application/json'}])
    def test_json_clients_get_the_envelope(self, broken_dist, client, headers):
        resp = client.get('/riftbound/app/assets/x.js', headers=headers)
        assert resp.status_code == 503
        body = resp.get_json()
        assert body['success'] is False
        assert body['error'] == 'Service Unavailable'
        assert body['message'].strip() != ''
        assert resp.headers['Cache-Control'] == 'no-store'
        assert 'Set-Cookie' not in resp.headers

    def test_the_redirect_is_followed_by_the_503(self, broken_dist, client):
        resp = client.get('/riftbound/app', follow_redirects=True,
                          headers={'Accept': BROWSER_ACCEPT})
        assert resp.status_code == 503

    def test_the_app_still_starts_and_stays_healthy(self, broken_dist, client):
        resp = client.get('/riftbound/api/v1/health')
        assert resp.status_code == 200
        assert resp.get_json()['data']['status'] == 'ok'
        assert client.get('/riftbound/login').status_code == 200

    def test_create_app_does_not_require_the_dist(self, clean_env, tmp_path):
        from app import create_app
        clean_env.setenv('FRONTEND_DIST', str(tmp_path / 'absent'))
        app = create_app(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                         SECRET_KEY='test-secret-key')
        assert app.config['FRONTEND_DIST'] == str(tmp_path / 'absent')

    def test_the_404_for_a_missing_file_is_also_minimal(self, spa_app, client):
        resp = client.get('/riftbound/app/assets/missing.js', headers={'Accept': BROWSER_ACCEPT})
        assert resp.status_code == 404
        assert resp.content_type.startswith('text/html')
        assert 'Set-Cookie' not in resp.headers
        assert 'navbar' not in resp.get_data(as_text=True)

    def test_the_404_for_json_clients_is_the_envelope(self, spa_app, client):
        resp = client.get('/riftbound/app/assets/missing.js', headers={'Accept': '*/*'})
        assert resp.status_code == 404
        assert resp.get_json()['error'] == 'Not Found'


# ---------------------------------------------------------------------------
# HOST-6 / D3
# ---------------------------------------------------------------------------

SPA_URLS = ['/riftbound/app/', '/riftbound/app/account/interface',
            '/riftbound/app/assets/app-abc123.js', '/riftbound/app/sw.js',
            '/riftbound/app/manifest.webmanifest', '/riftbound/app/pwa-192x192.png',
            '/riftbound/app/assets/missing.js']


class TestNoSecretsInTheShell:
    @pytest.mark.parametrize('url', SPA_URLS)
    def test_no_set_cookie(self, spa_app, client, url):
        assert 'Set-Cookie' not in client.get(url).headers

    def test_no_set_cookie_with_csrf_and_limiter_on(self, spa_app, csrf_app, limited_app, client):
        for url in SPA_URLS:
            assert 'Set-Cookie' not in client.get(url).headers, url

    def test_a_logged_in_visitor_gets_the_same_static_shell(self, spa_app, authenticated_client):
        resp = authenticated_client.get('/riftbound/app/')
        assert resp.get_data(as_text=True) == SPA_INDEX_HTML
        assert 'Set-Cookie' not in resp.headers

    @pytest.mark.parametrize('url', SPA_URLS)
    def test_security_headers(self, spa_app, client, url):
        resp = client.get(url)
        assert resp.headers['X-Content-Type-Options'] == 'nosniff'
        assert resp.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'

    def test_security_headers_on_the_redirect_and_the_503(self, app, client, tmp_path):
        app.config['FRONTEND_DIST'] = str(tmp_path / 'absent')
        resp = client.get('/riftbound/app/')
        assert resp.status_code == 503
        assert resp.headers['X-Content-Type-Options'] == 'nosniff'
        assert resp.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'

    def test_other_routes_do_not_get_the_spa_referrer_policy(self, client):
        assert 'Referrer-Policy' not in client.get('/riftbound/login').headers

    def test_the_shell_fixture_embeds_no_csrf_token(self):
        assert 'csrf' not in SPA_INDEX_HTML.lower()

    def test_the_spa_does_not_touch_the_session(self, spa_app, client):
        client.get('/riftbound/app/')
        with client.session_transaction() as sess:
            assert dict(sess) == {}


# ---------------------------------------------------------------------------
# HOST-7
# ---------------------------------------------------------------------------

class TestDocs:
    def test_env_example_lists_frontend_dist(self):
        text = (ROOT / '.env.example').read_text()
        assert re.search(r'^#\s*FRONTEND_DIST=', text, re.MULTILINE)

    def test_readme_describes_it_and_the_build(self):
        text = (ROOT / 'README.md').read_text(encoding='utf-8')
        assert 'FRONTEND_DIST' in text
        assert 'npm ci && npm run build' in text
        assert 'docs/frontend.md' in text

    def test_frontend_doc_covers_build_deploy_and_nginx(self):
        text = (ROOT / 'docs' / 'frontend.md').read_text(encoding='utf-8')
        for needle in ('npm ci', 'npm run build', 'FRONTEND_DIST', '503', 'frontend-dist',
                       'Nginx needs no change'):
            assert needle in text, needle

    def test_agents_names_the_blueprint_and_file(self):
        text = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
        assert 'spa_bp' in text
        assert 'app/routes/spa.py' in text or 'spa.py' in text

    def test_nginx_doc_keeps_two_proxy_pass_lines(self):
        text = (ROOT / 'docs' / 'nginx_config').read_text()
        assert len(re.findall(r'proxy_pass\s+http://\w+;', text)) == 2
        assert '/riftbound/app/' in text                 # the optional notes exist
