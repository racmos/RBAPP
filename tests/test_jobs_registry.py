"""F4-a S2: job kind registry and the `heartbeat` kind."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.jobs import registry
from app.jobs.registry import JobKind
from app.models.job import JOB_KINDS

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def isolated_registry(monkeypatch):
    """The registry as the app built it, restored after the test."""
    monkeypatch.setattr(registry, '_KINDS', dict(registry._KINDS))


def _noop(params):
    return {}


def test_register_get_and_sorted_names(isolated_registry):
    zeta = JobKind('zeta', _noop, 5)
    alpha = JobKind('alpha', _noop, 10)
    registry.register(zeta)
    registry.register(alpha)
    assert registry.get('zeta') is zeta
    assert registry.get('alpha').timeout_seconds == 10
    assert registry.names() == ['alpha', 'daily_prices', 'heartbeat', 'zeta']


def test_a_name_registered_twice_raises_and_keeps_the_first(isolated_registry):
    first = JobKind('twice', _noop, 5)
    registry.register(first)
    with pytest.raises(ValueError, match="'twice'"):
        registry.register(JobKind('twice', _noop, 99))
    assert registry.get('twice') is first
    assert registry.names().count('twice') == 1


def test_unknown_name_is_none():
    assert registry.get('nope') is None


def test_every_registered_kind_is_allowed_by_the_kind_check(app):
    assert set(registry.names()) <= set(JOB_KINDS)


def test_heartbeat_kind(app, frozen_clock):
    kind = registry.get('heartbeat')
    assert kind.name == 'heartbeat'
    assert kind.timeout_seconds == 60
    assert kind.handler({}) == {'ok': True, 'at': '2030-01-01T12:00:00+00:00'}


def test_daily_prices_kind(app):
    kind = registry.get('daily_prices')
    assert kind.name == 'daily_prices'
    assert kind.timeout_seconds == 1800
    assert 'daily_prices' in JOB_KINDS


def test_kinds_are_registered_on_app_creation():
    code = (
        "import sys\n"
        "from app import create_app\n"
        "assert 'app.jobs' not in sys.modules\n"
        "create_app(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',"
        " SECRET_KEY='test-secret-key')\n"
        "from app.jobs import registry\n"
        "print(registry.names())\n"
    )
    env = {**os.environ, 'RB_ENV': 'testing'}
    done = subprocess.run([sys.executable, '-c', code], cwd=REPO, env=env,
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "['daily_prices', 'heartbeat']"
