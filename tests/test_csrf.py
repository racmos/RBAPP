"""CSRF protection (CSRF-1, CSRF-2, CSRF-4, CSRF-5, D14).

The default `app` has CSRF off; `csrf_app` turns it on. Fixtures that log a
client in through the form (`authenticated_client`, `admin_client`, ...) must be
requested BEFORE `csrf_app`.
"""
import io
import time
import types

import itsdangerous.timed
import pytest

from tests.auth_helpers import form_token, meta_token

JSON_POST = '/riftbound/profile/update'


def post_json(client, token=None, headers=None, **kwargs):
    merged = {'X-CSRFToken': token} if token else {}
    merged.update(headers or {})
    return client.post(JSON_POST, json={'email': 'changed@test.com'}, headers=merged, **kwargs)


# --- CSRF-1 -------------------------------------------------------------------

class TestJsonRequests:
    def test_json_post_without_token_is_rejected_with_the_envelope(self, authenticated_client,
                                                                   csrf_app):
        resp = post_json(authenticated_client)
        assert resp.status_code == 400
        assert resp.is_json
        body = resp.get_json()
        assert body['success'] is False
        assert body['error'] == 'CSRF Error'
        assert body['message']

    def test_token_from_the_meta_tag_is_accepted(self, authenticated_client, csrf_app):
        token = meta_token(authenticated_client, '/riftbound/')
        resp = post_json(authenticated_client, token)
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_forged_token_is_rejected(self, authenticated_client, csrf_app):
        resp = post_json(authenticated_client, 'forged')
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'CSRF Error'

    def test_token_of_another_session_is_rejected(self, authenticated_client, other_user_client,
                                                  csrf_app):
        stolen = meta_token(other_user_client, '/riftbound/')
        resp = post_json(authenticated_client, stolen)
        assert resp.status_code == 400

    @pytest.mark.parametrize('method', ['post', 'put', 'patch', 'delete'])
    def test_every_unsafe_method_needs_the_token(self, client, csrf_app, method):
        # The app has no PUT/PATCH/DELETE routes yet (the API blueprint will), so
        # register a throw-away one before the first request.
        csrf_app.add_url_rule('/riftbound/_unsafe', 'unsafe_probe', lambda: 'reached',
                              methods=['POST', 'PUT', 'PATCH', 'DELETE'])
        assert csrf_app.config['WTF_CSRF_METHODS'] == {'POST', 'PUT', 'PATCH', 'DELETE'}
        resp = getattr(client, method)('/riftbound/_unsafe', json={})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'CSRF Error'

    def test_safe_methods_need_no_token(self, authenticated_client, csrf_app):
        assert authenticated_client.get('/riftbound/').status_code == 200
        assert authenticated_client.head('/riftbound/').status_code == 200
        assert authenticated_client.options('/riftbound/').status_code == 200

    def test_a_token_stays_valid_for_several_requests(self, authenticated_client, csrf_app):
        token = meta_token(authenticated_client, '/riftbound/')
        assert post_json(authenticated_client, token).status_code == 200
        assert post_json(authenticated_client, token).status_code == 200

    def test_token_is_still_accepted_two_hours_later(self, authenticated_client, csrf_app,
                                                     monkeypatch):
        assert csrf_app.config['WTF_CSRF_TIME_LIMIT'] is None
        token = meta_token(authenticated_client, '/riftbound/')
        later = time.time() + 2 * 3600
        # Only itsdangerous (token and session signatures) sees the later clock.
        monkeypatch.setattr(itsdangerous.timed, 'time',
                            types.SimpleNamespace(time=lambda: later))
        assert post_json(authenticated_client, token).status_code == 200

    def test_the_form_field_works_too(self, authenticated_client, csrf_app):
        token = meta_token(authenticated_client, '/riftbound/')
        resp = authenticated_client.post(JSON_POST, data={'csrf_token': token, 'email': 'a@b.io'})
        assert resp.get_json().get('error') != 'CSRF Error'


class TestMultipartUpload:
    @pytest.fixture
    def sandbox(self, app, tmp_path, monkeypatch):
        monkeypatch.setattr(app, 'static_folder', str(tmp_path))
        return tmp_path

    def upload(self, client, token=None):
        # `fetch` (what the page uses for the upload) sends Accept: */*.
        headers = {'Accept': '*/*'}
        if token:
            headers['X-CSRFToken'] = token
        return client.post(
            '/riftbound/card/upload_image', headers=headers, content_type='multipart/form-data',
            data={'set_id': 'ogn', 'image': (io.BytesIO(b'png-bytes'), 'ogn_1.png')})

    def test_upload_with_the_header_passes_csrf(self, admin_client, csrf_app, sandbox):
        token = meta_token(admin_client, '/riftbound/')
        resp = self.upload(admin_client, token)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        assert (sandbox / 'images' / 'cards' / 'ogn' / 'ogn_1.png').exists()

    def test_upload_without_the_header_is_rejected_and_writes_nothing(self, admin_client,
                                                                      csrf_app, sandbox):
        resp = self.upload(admin_client)
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'CSRF Error'
        assert not (sandbox / 'images').exists()


# --- CSRF-2 -------------------------------------------------------------------

class TestErrorFormat:
    def test_browser_form_gets_an_html_page(self, client, csrf_app):
        resp = client.post('/riftbound/login', data={'username': 'x', 'password': 'y'},
                           headers={'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8'})
        assert resp.status_code == 400
        assert resp.content_type.startswith('text/html')
        assert b'csrf-token' in resp.data          # an error page that extends base.html

    def test_a_form_post_without_accept_gets_an_html_page(self, client, csrf_app):
        # API-8: a request with no Accept header is treated as HTML (it was JSON
        # under the interim predicate of unit d).
        resp = client.post('/riftbound/login', data={'username': 'x', 'password': 'y'})
        assert resp.status_code == 400
        assert resp.content_type.startswith('text/html')

    def test_a_json_post_without_accept_gets_json(self, client, csrf_app):
        resp = client.post('/riftbound/login', json={'username': 'x', 'password': 'y'})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'CSRF Error'

    def test_fetch_with_a_wildcard_accept_gets_json(self, client, csrf_app):
        resp = client.post('/riftbound/login', data={'username': 'x'}, headers={'Accept': '*/*'})
        assert resp.get_json()['error'] == 'CSRF Error'


# --- login / register forms (CSRF-3) -------------------------------------------

class TestLoginForm:
    def test_login_with_the_hidden_token_redirects_to_the_dashboard(self, client, csrf_app,
                                                                    make_user):
        make_user('formuser')
        token = form_token(client.get('/riftbound/login').get_data(as_text=True))
        assert token
        resp = client.post('/riftbound/login', data={
            'username': 'formuser', 'password': 'testpass123', 'csrf_token': token})
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/riftbound/')
        assert client.get('/riftbound/').status_code == 200

    def test_login_without_the_token_is_a_400_and_no_session(self, client, csrf_app, make_user):
        make_user('formuser')
        resp = client.post('/riftbound/login', data={
            'username': 'formuser', 'password': 'testpass123'})
        assert resp.status_code == 400
        assert client.get('/riftbound/').status_code == 302

    def test_register_form_carries_a_token(self, client, csrf_app):
        assert form_token(client.get('/riftbound/register').get_data(as_text=True))

    def test_register_without_the_token_is_a_400(self, client, csrf_app):
        resp = client.post('/riftbound/register', data={
            'username': 'newbie', 'email': 'newbie@test.com', 'password': 'longenough1'})
        assert resp.status_code == 400


# --- CSRF-4 logout --------------------------------------------------------------

class TestLogout:
    def test_post_logout_with_the_token_ends_the_session(self, authenticated_client, csrf_app):
        token = meta_token(authenticated_client, '/riftbound/')
        resp = authenticated_client.post('/riftbound/logout', data={'csrf_token': token})
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/riftbound/login')
        assert authenticated_client.get('/riftbound/').status_code == 302

    def test_post_logout_without_the_token_does_nothing(self, authenticated_client, csrf_app):
        resp = authenticated_client.post('/riftbound/logout')
        assert resp.status_code == 400
        assert authenticated_client.get('/riftbound/').status_code == 200

    def test_get_logout_is_405_and_the_session_still_works(self, authenticated_client, csrf_app):
        assert authenticated_client.get('/riftbound/logout').status_code == 405
        assert authenticated_client.get('/riftbound/').status_code == 200

    def test_get_logout_is_405_even_with_csrf_off(self, authenticated_client):
        assert authenticated_client.get('/riftbound/logout').status_code == 405
        assert authenticated_client.get('/riftbound/').status_code == 200


# --- CSRF-5 kill switch ---------------------------------------------------------

class TestKillSwitch:
    def test_disabled_by_config_accepts_a_tokenless_post(self, authenticated_client, csrf_app):
        csrf_app.config['WTF_CSRF_ENABLED'] = False
        resp = post_json(authenticated_client)
        assert resp.status_code == 200

    def test_the_default_test_app_has_csrf_off(self, authenticated_client):
        assert post_json(authenticated_client).status_code == 200


# --- strict Referer check on HTTPS (D14), also behind the reverse proxy ---------

class TestHttpsReferer:
    HTTPS = {'base_url': 'https://localhost'}

    def https_session(self, client):
        token = meta_token(client, '/riftbound/login', base_url='https://localhost',
                           headers={'Referer': 'https://localhost/riftbound/login'})
        return token

    def test_https_post_without_a_referer_is_rejected(self, authenticated_client, csrf_app):
        token = meta_token(authenticated_client, '/riftbound/', base_url='https://localhost')
        resp = post_json(authenticated_client, token, base_url='https://localhost')
        assert resp.status_code == 400
        assert 'referrer' in resp.get_json()['message'].lower()

    def test_https_post_from_another_origin_is_rejected(self, authenticated_client, csrf_app):
        token = meta_token(authenticated_client, '/riftbound/', base_url='https://localhost')
        resp = post_json(authenticated_client, token, base_url='https://localhost',
                         headers={'X-CSRFToken': token, 'Referer': 'https://evil.example/riftbound/'})
        assert resp.status_code == 400

    def test_https_post_from_the_same_origin_passes(self, authenticated_client, csrf_app):
        token = meta_token(authenticated_client, '/riftbound/', base_url='https://localhost')
        resp = post_json(authenticated_client, token, base_url='https://localhost',
                         headers={'X-CSRFToken': token,
                                  'Referer': 'https://localhost/riftbound/profile'})
        assert resp.status_code == 200

    def test_behind_nginx_the_proxy_headers_make_the_check_pass(self, client, make_user,
                                                                 csrf_app):
        """Plain HTTP to Gunicorn, TLS ended by Nginx: X-Forwarded-Proto makes the request
        secure (ProxyFix) and Host carries the public name, which the Referer must match.
        The whole flow runs through the proxy headers, login form included."""
        make_user('proxied')
        proxy = {'X-Forwarded-Proto': 'https', 'X-Forwarded-For': '203.0.113.7',
                 'Host': 'racmosdev.online'}
        login_page = client.get('/riftbound/login', headers=proxy)
        login = client.post(
            '/riftbound/login', headers={**proxy, 'Referer': 'https://racmosdev.online/riftbound/login'},
            data={'username': 'proxied', 'password': 'testpass123',
                  'csrf_token': form_token(login_page.get_data(as_text=True))})
        assert login.status_code == 302

        token = meta_token(client, '/riftbound/', headers=proxy)
        good = client.post(
            JSON_POST, json={'email': 'changed@test.com'},
            headers={**proxy, 'X-CSRFToken': token,
                     'Referer': 'https://racmosdev.online/riftbound/profile'})
        assert good.status_code == 200
        wrong = client.post(
            JSON_POST, json={'email': 'changed@test.com'},
            headers={**proxy, 'X-CSRFToken': token,
                     'Referer': 'https://other.example/riftbound/profile'})
        assert wrong.status_code == 400
        no_forwarded_proto = client.post(      # sanity: without the proxy header it is plain http
            JSON_POST, json={'email': 'changed@test.com'},
            headers={'Host': 'racmosdev.online', 'X-CSRFToken': token})
        assert no_forwarded_proto.status_code == 200

    def test_plain_http_does_not_check_the_referer(self, authenticated_client, csrf_app):
        token = meta_token(authenticated_client, '/riftbound/')
        assert post_json(authenticated_client, token).status_code == 200
