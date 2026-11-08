"""Error responses: never any exception text (M-c S2-S5), JSON or a minimal HTML page.

The failing code is mocked to raise an exception that carries a secret-looking
text. Users get a clear message and a `code`; the text travels only under
`detail`, only for a signed-in admin, and always reaches the log.

Since the Jinja web was retired (PR 3/3) a browser gets one minimal inline page
for every error: status, message and a link back to the app; no stylesheet, no
script, no session cookie. JSON clients keep the envelope (`wants_json`).
"""
import logging

import pytest
from flask import abort
from pydantic import BaseModel, model_validator

from app.schemas.validation import validate_json

SECRET = 'password=hunter2 host=db.internal'
DETAIL = f'RuntimeError: {SECRET}'
BROWSER = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
ACCOUNT = '/riftbound/api/v1/me/account'


def _secret_anywhere(response):
    return SECRET in response.get_data(as_text=True)


# --- @validate_json: the generic `except Exception` branch -----------------------

class _Exploding(BaseModel):
    """A schema whose validator fails with something Pydantic does not wrap."""

    @model_validator(mode='before')
    @classmethod
    def explode(cls, data):
        raise RuntimeError(SECRET)


@pytest.fixture
def probe_app(app):
    """`app` with test-only routes: one behind `@validate_json(_Exploding)`, one that
    raises, one per HTTP error and one unsafe route for the CSRF check.

    Request it BEFORE any logged-in client: routes cannot be added after the
    first request."""
    @app.route('/riftbound/test-probe', methods=['POST'])
    @validate_json(_Exploding)
    def _probe():
        return {'success': True}

    @app.route('/riftbound/test-boom')
    def _boom():
        raise RuntimeError(SECRET)

    @app.route('/riftbound/test-abort/<int:status>')
    def _abort(status):
        abort(status)

    @app.route('/riftbound/test-unsafe', methods=['POST'])
    def _unsafe():
        return 'reached'
    return app


def _probe(client):
    return client.post('/riftbound/test-probe', json={'any': 'thing'})


class TestValidateJsonGenericFailure:
    """S3/S5: 400 "Bad Request", "Invalid request body", `bad_request`; detail for admins."""

    def _assert_clear_400(self, response):
        assert response.status_code == 400
        body = response.get_json()
        assert body['success'] is False
        assert body['error'] == 'Bad Request'
        assert body['message'] == 'Invalid request body'
        assert body['code'] == 'bad_request'
        return body

    def test_a_plain_user_gets_no_detail(self, probe_app, authenticated_client):
        response = _probe(authenticated_client)
        body = self._assert_clear_400(response)
        assert 'detail' not in body
        assert not _secret_anywhere(response)

    def test_an_anonymous_caller_gets_no_detail(self, probe_app, client):
        response = _probe(client)
        assert 'detail' not in self._assert_clear_400(response)
        assert not _secret_anywhere(response)

    def test_the_admin_gets_the_detail(self, probe_app, admin_client):
        body = self._assert_clear_400(_probe(admin_client))
        assert body['detail'] == DETAIL

    def test_the_failure_is_logged(self, probe_app, client, caplog):
        with caplog.at_level(logging.ERROR):
            _probe(client)
        assert any(r.exc_info and SECRET in str(r.exc_info[1]) for r in caplog.records)

    def test_a_body_that_is_not_an_object_on_a_real_endpoint(self, authenticated_client):
        response = authenticated_client.patch(ACCOUNT, json=['x'])
        body = self._assert_clear_400(response)
        assert 'detail' not in body
        assert 'mapping' not in response.get_data(as_text=True)

    def test_malformed_json_on_a_real_endpoint(self, authenticated_client):
        response = authenticated_client.patch(ACCOUNT, data='{"email": ',
                                              content_type='application/json')
        body = self._assert_clear_400(response)
        assert 'detail' not in body
        assert 'decode' not in response.get_data(as_text=True).lower()


class TestValidateJsonUnchangedBranches:
    """PRESERVE: the Pydantic and Content-Type branches keep their F0 bodies."""

    def test_a_pydantic_error_is_still_a_validation_error(self, authenticated_client):
        response = authenticated_client.patch(ACCOUNT, json={'email': 'no-at-sign'})
        assert response.status_code == 400
        body = response.get_json()
        assert body['error'] == 'Validation Error'
        assert body['message'] == 'Invalid request data'
        assert body['code'] == 'validation_error'
        assert body['details'][0]['field'] == 'email'
        assert 'detail' not in body

    def test_a_non_json_body_still_asks_for_json(self, authenticated_client):
        response = authenticated_client.patch(ACCOUNT, data='x', content_type='text/plain')
        assert response.status_code == 400
        assert response.get_json() == {'success': False, 'error': 'Bad Request',
                                       'message': 'Content-Type must be application/json'}


# --- Unhandled exceptions: a 500 without the exception text ------------------------

class TestUnhandledException:
    def test_a_browser_gets_the_500_page_without_the_text(self, probe_app, client, caplog):
        with caplog.at_level(logging.ERROR):
            response = client.get('/riftbound/test-boom', headers={'Accept': BROWSER})
        assert response.status_code == 500
        assert response.mimetype == 'text/html'
        page = response.get_data(as_text=True)
        assert '<h1>500 Internal Server Error</h1>' in page
        assert '<p>An unexpected error occurred</p>' in page
        assert not _secret_anywhere(response)
        assert any(r.exc_info and SECRET in str(r.exc_info[1]) for r in caplog.records)

    def test_a_json_client_gets_the_envelope_without_the_text(self, probe_app, client):
        response = client.get('/riftbound/test-boom', headers={'Accept': 'application/json'})
        assert response.status_code == 500
        assert response.get_json() == {'success': False, 'error': 'Internal Server Error',
                                       'message': 'An unexpected error occurred'}

    def test_even_an_admin_sees_no_text_on_the_page(self, probe_app, admin_client):
        response = admin_client.get('/riftbound/test-boom')
        assert response.status_code == 500
        assert not _secret_anywhere(response)


# --- The inline HTML page -----------------------------------------------------------

def _page(response):
    assert response.mimetype == 'text/html'
    assert response.content_type == 'text/html; charset=utf-8'
    return response.get_data(as_text=True)


class TestHtmlErrorPage:
    @pytest.mark.parametrize('status, title, message', [
        (400, 'Bad Request', 'The browser (or proxy) sent a request that this server could '
                             'not understand.'),
        (401, 'Unauthorized', 'Authentication is required'),
        (403, 'Forbidden', 'You do not have permission to access this resource'),
        (404, 'Not Found', 'The requested resource was not found'),
        (500, 'Internal Server Error', 'An unexpected error occurred'),
    ])
    def test_each_status_gets_its_title_and_message(self, probe_app, client, status, title,
                                                    message):
        response = client.get(f'/riftbound/test-abort/{status}')
        assert response.status_code == status
        page = _page(response)
        assert f'<title>{status} {title} · Rift Manager</title>' in page
        assert f'<h1>{status} {title}</h1>' in page
        assert f'<p>{message}</p>' in page

    def test_an_unknown_path_is_a_404_page(self, client):
        response = client.get('/riftbound/nope')
        assert response.status_code == 404
        assert '<h1>404 Not Found</h1>' in _page(response)

    def test_the_page_links_back_to_the_app_and_loads_nothing(self, client):
        page = _page(client.get('/riftbound/nope', headers={'Accept': BROWSER}))
        assert '<a href="/riftbound/app/" style="color:#00b2cf">Back to the app</a>' in page
        assert page.startswith('<!doctype html>')
        assert '<script' not in page
        assert '<link' not in page
        assert 'src=' not in page

    def test_the_page_never_sets_a_cookie(self, client):
        response = client.get('/riftbound/nope')
        assert 'Set-Cookie' not in response.headers

    def test_a_405_keeps_the_allow_header(self, client):
        response = client.post('/riftbound/')
        assert response.status_code == 405
        assert '<h1>405 Method Not Allowed</h1>' in _page(response)
        assert set(response.headers['Allow'].split(', ')) == {'GET', 'HEAD', 'OPTIONS'}

    def test_the_text_is_escaped(self, app, client):
        from app.errors import html_error_page
        with app.test_request_context('/'):
            response = html_error_page(400, 'Bad <Request>', '<script>alert("x")</script> & co')
        page = response.get_data(as_text=True)
        assert '<script>' not in page
        assert '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;' in page
        assert 'Bad &lt;Request&gt;' in page
        assert '&amp; co' in page

    def test_the_json_negotiation_is_unchanged(self, client):
        response = client.get('/riftbound/nope', headers={'Accept': '*/*'})
        assert response.status_code == 404
        assert response.get_json() == {'success': False, 'error': 'Not Found',
                                       'message': 'The requested resource was not found'}

    def test_the_api_is_json_even_for_a_browser(self, client):
        response = client.get('/riftbound/api/v1/nope', headers={'Accept': BROWSER})
        assert response.status_code == 404
        assert response.get_json()['error'] == 'Not Found'


class TestTooManyRequests:
    def test_a_browser_gets_the_page_with_retry_after(self, probe_app, client):
        response = client.get('/riftbound/test-abort/429')
        assert response.status_code == 429
        assert response.headers['Retry-After'] == '60'
        page = _page(response)
        assert '<h1>429 Too Many Requests</h1>' in page
        assert '<p>Too many requests. Please wait 60 seconds before trying again.</p>' in page

    def test_a_json_client_gets_the_envelope_with_retry_after(self, probe_app, client):
        response = client.get('/riftbound/test-abort/429', headers={'Accept': 'application/json'})
        assert response.status_code == 429
        assert response.headers['Retry-After'] == '60'
        assert response.get_json() == {
            'success': False, 'error': 'Too Many Requests',
            'message': 'Too many requests. Please wait before trying again.',
            'code': 'rate_limited', 'params': {'retry_after': 60}}


class TestCsrfFailure:
    def test_a_browser_form_gets_the_400_page(self, probe_app, csrf_app, client):
        response = client.post('/riftbound/test-unsafe', data={'a': '1'},
                               headers={'Accept': BROWSER})
        assert response.status_code == 400
        page = _page(response)
        assert '<h1>400 Bad Request</h1>' in page
        assert '<p>The CSRF token is missing.</p>' in page
        assert 'reached' not in page

    def test_a_form_without_accept_gets_the_page_too(self, probe_app, csrf_app, client):
        response = client.post('/riftbound/test-unsafe', data={'a': '1'})
        assert response.status_code == 400
        assert '<h1>400 Bad Request</h1>' in _page(response)

    def test_a_json_client_gets_the_csrf_envelope(self, probe_app, csrf_app, client):
        response = client.post('/riftbound/test-unsafe', json={'a': 1})
        assert response.status_code == 400
        assert response.get_json() == {'success': False, 'error': 'CSRF Error',
                                       'message': 'The CSRF token is missing.',
                                       'code': 'csrf_invalid'}
