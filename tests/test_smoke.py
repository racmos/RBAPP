"""Startup smoke tests (M-a): the app factory and the WSGI entry point build a working app.

Together with `tests/test_authz_matrix.py` these are the only guards kept by the test
reset of 2026-10-22; see the test policy in AGENTS.md -> Testing.
"""
import runpy
from pathlib import Path

from flask import Flask

WSGI_PY = str(Path(__file__).resolve().parent.parent / 'wsgi.py')


def test_the_app_starts_and_reports_healthy(app, client):
    resp = client.get('/riftbound/api/v1/health')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['success'] is True
    assert body['data']['status'] == 'ok'
    assert body['data']['db'] == 'ok'


def test_the_wsgi_entry_point_builds_the_app(clean_env):
    clean_env.setenv('RB_ENV', 'development')
    clean_env.setenv('DATABASE_URL', 'sqlite:///:memory:')
    namespace = runpy.run_path(WSGI_PY)
    assert isinstance(namespace['application'], Flask)
    assert namespace['app'] is namespace['application']
