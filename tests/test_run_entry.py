"""
Tests for the local entry points (SESS-2, R8).

`run.py` is executed as `__main__` with `Flask.run` patched, so nothing binds a
socket. Every test starts from a clean environment (see `clean_env`).
"""
import runpy
from pathlib import Path

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parent.parent
RUN_PY = str(ROOT / 'run.py')
WSGI_PY = str(ROOT / 'wsgi.py')

SQLITE_URL = 'sqlite:///:memory:'
PROD_KEY = 'p' * 48


@pytest.fixture
def flask_run(clean_env):
    """Development environment on SQLite with `Flask.run` recording its kwargs."""
    clean_env.setenv('RB_ENV', 'development')
    clean_env.setenv('DATABASE_URL', SQLITE_URL)
    calls = []

    def fake_run(self, host=None, port=None, debug=None, load_dotenv=True, **options):
        calls.append({'host': host, 'port': port, 'debug': debug})

    clean_env.setattr(Flask, 'run', fake_run)
    return calls


def _run_main():
    runpy.run_path(RUN_PY, run_name='__main__')


class TestRunPy:
    def test_defaults_are_debug_off_and_loopback(self, flask_run):
        _run_main()
        assert flask_run == [{'host': '127.0.0.1', 'port': 5000, 'debug': False}]

    def test_flask_debug_opts_in(self, flask_run, clean_env):
        clean_env.setenv('FLASK_DEBUG', '1')
        _run_main()
        assert flask_run[0]['debug'] is True
        assert flask_run[0]['host'] == '127.0.0.1'      # debug alone does not widen the bind

    def test_flask_debug_zero_stays_off(self, flask_run, clean_env):
        clean_env.setenv('FLASK_DEBUG', '0')
        _run_main()
        assert flask_run[0]['debug'] is False

    def test_rb_host_and_port_are_honored(self, flask_run, clean_env):
        clean_env.setenv('RB_HOST', '0.0.0.0')
        clean_env.setenv('RB_PORT', '5123')
        _run_main()
        assert flask_run[0]['host'] == '0.0.0.0'
        assert flask_run[0]['port'] == 5123
        assert flask_run[0]['debug'] is False           # a wider bind never turns debug on

    def test_importing_the_module_does_not_start_the_server(self, flask_run):
        # gunicorn imports `run:app`; only `python run.py` may call app.run.
        namespace = runpy.run_path(RUN_PY, run_name='run')
        assert flask_run == []
        assert isinstance(namespace['app'], Flask)

    def test_production_without_debug_runs_with_debug_off(self, flask_run, clean_env):
        clean_env.setenv('RB_ENV', 'production')
        clean_env.setenv('SECRET_KEY', PROD_KEY)
        _run_main()
        assert flask_run[0]['debug'] is False

    def test_production_never_runs_with_debug(self, flask_run, clean_env):
        clean_env.setenv('RB_ENV', 'production')
        clean_env.setenv('SECRET_KEY', PROD_KEY)
        clean_env.setenv('FLASK_DEBUG', '1')
        with pytest.raises(RuntimeError, match='DEBUG'):
            _run_main()
        assert flask_run == []                          # the server never started


class TestWsgi:
    def test_app_is_an_alias_of_application(self, clean_env):
        # R8: gunicorn may use `wsgi:application` or `wsgi:app`; same object.
        clean_env.setenv('RB_ENV', 'development')
        clean_env.setenv('DATABASE_URL', SQLITE_URL)
        namespace = runpy.run_path(WSGI_PY)
        assert isinstance(namespace['application'], Flask)
        assert namespace['app'] is namespace['application']
