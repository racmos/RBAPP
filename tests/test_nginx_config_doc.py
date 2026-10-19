"""docs/nginx_config documents the Nginx layer of the login rate limit (LOGIN-7).

The scenario is [MANUAL] (applying and bursting a real Nginx); this pins what the
document has to keep saying.
"""
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parent.parent / 'docs' / 'nginx_config'


@pytest.fixture(scope='module')
def text():
    return DOC.read_text(encoding='utf-8')


def test_has_a_limit_req_zone_and_applies_it(text):
    assert 'limit_req_zone' in text
    assert 'limit_req zone=rb_auth' in text
    assert 'limit_req_status 429' in text


@pytest.mark.parametrize('path', ['/riftbound/(login|register)', '/riftbound/api/v1/auth/'])
def test_covers_the_login_register_and_api_auth_urls(text, path):
    assert path in text


def test_says_the_in_app_limiter_is_per_gunicorn_worker(text):
    assert 'PER GUNICORN' in text.upper() and 'worker' in text


def test_only_posts_are_keyed(text):
    assert 'POST:' in text


def test_keeps_the_headers_csrf_and_proxyfix_need(text):
    for header in ('proxy_set_header Host $host', 'proxy_set_header X-Forwarded-Proto $scheme',
                   'proxy_set_header X-Forwarded-For'):
        assert header in text
    assert 'Referer' in text
