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
