"""Small helpers for tests that deal with CSRF tokens (unit d)."""
import re

META_TOKEN = re.compile(r'<meta\s+name="csrf-token"\s+content="([^"]*)"')
FORM_TOKEN = re.compile(r'<input[^>]*name="csrf_token"[^>]*value="([^"]*)"')


def meta_token(client, path='/riftbound/login', **kwargs):
    """The token a browser would read from `<meta name="csrf-token">` of `path`."""
    html = client.get(path, **kwargs).get_data(as_text=True)
    match = META_TOKEN.search(html)
    assert match and match.group(1), f'no csrf-token meta tag on {path}'
    return match.group(1)


def form_token(html):
    """The hidden `csrf_token` input of a rendered form, or None."""
    match = FORM_TOKEN.search(html)
    return match.group(1) if match else None


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
