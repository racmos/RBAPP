"""Small helpers for tests that deal with CSRF tokens and cookies (unit d).

The CSRF token comes from GET /auth/session (`tests.conftest.api_csrf_token`): the
Jinja pages that carried it in a meta tag or a form field are gone.
"""


def token_payload(token):
    """The session secret inside a signed CSRF token. Flask-WTF signs it with a
    timestamp, so two renders a second apart differ as strings but carry the
    same payload."""
    return token.rsplit('.', 2)[0]
