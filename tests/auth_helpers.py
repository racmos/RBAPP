"""Small helpers for tests that deal with CSRF tokens and cookies (unit d).

The CSRF token comes from GET /auth/session (`tests.conftest.api_csrf_token`): the
Jinja pages that carried it in a meta tag or a form field are gone.
"""


def token_payload(token):
    """The session secret inside a signed CSRF token. Flask-WTF signs it with a
    timestamp, so two renders a second apart differ as strings but carry the
    same payload."""
    return token.rsplit('.', 2)[0]


HTTPS = 'https://localhost'


class Browser:
    """A test client that sends every request to `base_url` (HTTPS by default:
    Secure cookies are only stored and sent that way)."""

    def __init__(self, app, base_url=HTTPS):
        self.client = app.test_client()
        self.base_url = base_url

    def get(self, path, **kwargs):
        return self.client.get(path, base_url=self.base_url, **kwargs)

    def post(self, path, **kwargs):
        return self.client.post(path, base_url=self.base_url, **kwargs)

    def has_cookie(self, name):
        return self.client.get_cookie(name) is not None

    def drop_cookie(self, name):
        self.client.delete_cookie(name)


def api_login(browser, username='remuser', password='Passw0rd!x', **extra):
    """POST /api/v1/auth/login through `browser`; `extra` adds body fields such as `remember=True`."""
    body = {'username': username, 'password': password, **extra}
    return browser.post('/riftbound/api/v1/auth/login', json=body)
