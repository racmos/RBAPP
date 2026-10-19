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
