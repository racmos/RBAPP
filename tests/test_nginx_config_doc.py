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


# --- unit e (5.18): one Flask app serves `/` and `/riftbound/` ------------------

import re


def test_the_landing_is_no_longer_on_port_8001(text):
    assert '8001' not in text


def test_both_locations_are_proxied_to_flask_on_port_8000(text):
    assert re.search(r'location\s+/\s*\{', text)
    assert re.search(r'location\s+/riftbound/\s*\{', text)
    # one upstream, used by both locations
    assert re.search(r'upstream\s+\w+\s*\{\s*server\s+[^;]*:8000;', text)
    assert len(re.findall(r'proxy_pass\s+http://\w+;', text)) == 2


def test_the_server_name_is_the_dev_domain_not_dot_es(text):
    assert 'racmosdev.online' in text
    assert '.es' not in text


def test_no_private_address_or_host_is_committed(text):
    assert not re.search(r'\b(192\.168|10\.\d+|172\.(1[6-9]|2\d|3[01]))\.\d+\.\d+', text)


def test_documents_the_proxy_topology_and_one_hop(text):
    assert 'separate' in text.lower() and 'proxy host' in text.lower()
    assert 'PROXY_FIX_X_FOR' in text and 'exactly one' in text.lower()
    for header in ('Host', 'X-Forwarded-Proto', 'X-Forwarded-For', 'Referer'):
        assert header in text


def test_the_stale_fastapi_comments_are_gone(text):
    assert 'FastAPI' not in text and 'Uvicorn' not in text
