"""
Tests for the GitHub Actions workflow files (CI-1; later units add CI-2..8).

Workflows are parsed with PyYAML; nothing here needs the network.
"""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((ROOT / '.github' / 'workflows').glob('*.yml'))

# CI-1: tests configure themselves; the app's secrets never enter CI.
FORBIDDEN_ENV_NAMES = {'DATABASE_URL', 'SECRET_KEY', 'FLASK_ENV'}
FORBIDDEN_SECRET_REFS = ('secrets.DATABASE_URL', 'secrets.SECRET_KEY')


def _env_blocks(workflow):
    """Yield every `env` mapping: workflow level, job level and step level."""
    if isinstance(workflow.get('env'), dict):
        yield 'workflow', workflow['env']
    for job_name, job in (workflow.get('jobs') or {}).items():
        if isinstance(job.get('env'), dict):
            yield f'job {job_name}', job['env']
        for index, step in enumerate(job.get('steps') or []):
            if isinstance(step.get('env'), dict):
                yield f'job {job_name} step {index}', step['env']


def _load(path):
    return yaml.safe_load(path.read_text())


def test_workflow_files_are_found():
    names = {p.name for p in WORKFLOWS}
    assert {'ci.yml', 'security.yml', 'release.yml'} <= names


@pytest.mark.parametrize('path', WORKFLOWS, ids=lambda p: p.name)
class TestNoApplicationSecretsInCi:
    def test_no_env_block_defines_app_secrets(self, path):
        offenders = [
            (where, name)
            for where, env in _env_blocks(_load(path))
            for name in env
            if name in FORBIDDEN_ENV_NAMES
        ]
        assert offenders == []

    def test_no_reference_to_app_secrets(self, path):
        text = path.read_text()
        for ref in FORBIDDEN_SECRET_REFS:
            assert ref not in text


def test_the_scan_sees_env_blocks_it_is_meant_to_catch():
    # Guard against a vacuous pass: the helper must find env blocks at all
    # three levels, so an offending block could not hide from the scan.
    workflow = yaml.safe_load("""
env: {A: '1'}
jobs:
  j:
    env: {B: '2'}
    steps:
      - run: x
        env: {DATABASE_URL: 'y'}
""")
    found = dict(_env_blocks(workflow))
    assert found == {'workflow': {'A': '1'}, 'job j': {'B': '2'},
                     'job j step 0': {'DATABASE_URL': 'y'}}


# --- migrations-pg job (unit b pulled it forward from unit e; D20, CI-4) -----

import re


def _ci():
    return _load(ROOT / '.github' / 'workflows' / 'ci.yml')


def _pg_job():
    return _ci()['jobs']['migrations-pg']


def _run_text(job):
    return '\n'.join(step['run'] for step in job['steps'] if 'run' in step)


class TestMigrationsPostgresJob:
    def test_job_exists(self):
        assert 'migrations-pg' in _ci()['jobs']

    def test_token_is_read_only(self):
        # least privilege: the workflow-level default is contents: read
        assert _ci()['permissions'] == {'contents': 'read'}
        assert 'permissions' not in _pg_job() or _pg_job()['permissions'] == {'contents': 'read'}

    def test_runs_on_python_3_12(self):
        setups = [s for s in _pg_job()['steps'] if str(s.get('uses', '')).startswith('actions/setup-python')]
        assert [str(s['with']['python-version']) for s in setups] == ['3.12']

    def test_uses_a_postgresql_18_service_that_must_be_healthy_first(self):
        service = _pg_job()['services']['postgres']
        assert service['image'] == 'postgres:18'
        assert '--health-cmd' in service['options']
        assert '5432:5432' in [str(p) for p in service['ports']]

    def test_database_name_contains_test(self):
        # the pg_url fixture refuses any other name (D20)
        text = _run_text(_pg_job())
        urls = re.findall(r"TEST_POSTGRES_URL='?([^\s']+)", text)
        assert urls, 'pytest must receive TEST_POSTGRES_URL'
        for url in urls:
            assert url.startswith('postgresql+psycopg://')
            assert 'test' in url.rsplit('/', 1)[1]
        assert service_db(_pg_job()) in urls[0]

    def test_migration_round_trip_runs_before_the_postgres_tests(self):
        text = _run_text(_pg_job())
        order = [text.index(cmd) for cmd in (
            'flask db upgrade', 'flask db check', 'flask db downgrade base')]
        assert order == sorted(order)
        assert text.rindex('flask db upgrade') > text.index('flask db downgrade base')
        assert text.index('pytest -m postgres') > text.rindex('flask db upgrade')

    def test_database_url_is_defined_inline_not_in_an_env_block(self):
        # CI-1 / R9: no env block may carry DATABASE_URL or SECRET_KEY
        assert 'DATABASE_URL=' in _run_text(_pg_job())
        assert [n for _w, env in _env_blocks(_ci()) for n in env if n in FORBIDDEN_ENV_NAMES] == []

    def test_development_environment_gets_an_ephemeral_secret_key(self):
        # no SECRET_KEY anywhere: RB_ENV=development generates one per process (D2)
        text = _run_text(_pg_job())
        assert 'RB_ENV=development' in text
        assert 'SECRET_KEY' not in text


def service_db(job):
    return job['services']['postgres']['env']['POSTGRES_DB']
