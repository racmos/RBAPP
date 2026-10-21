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


# --- unit e: CI-2 .. CI-7 -------------------------------------------------------

def _security():
    return _load(ROOT / '.github' / 'workflows' / 'security.yml')


def _release():
    return _load(ROOT / '.github' / 'workflows' / 'release.yml')


def _triggers(workflow):
    # PyYAML (YAML 1.1) reads the key `on` as the boolean True.
    return workflow['on'] if 'on' in workflow else workflow[True]


def _steps_using(job, action):
    return [s for s in job['steps'] if str(s.get('uses', '')).startswith(action)]


def _all_jobs(workflow):
    return workflow['jobs'].items()


# CI-2 -------------------------------------------------------------------------

class TestPinnedTooling:
    @pytest.mark.parametrize('path', WORKFLOWS, ids=lambda p: p.name)
    def test_every_python_version_is_3_12(self, path):
        versions = [
            step['with']['python-version']
            for _name, job in _all_jobs(_load(path))
            for step in _steps_using(job, 'actions/setup-python')
        ]
        # ci.yml has two Python jobs, security.yml one, release.yml none
        assert versions == ['3.12'] * len(versions)
        if path.name == 'ci.yml':
            assert len(versions) == 2
        if path.name == 'security.yml':
            assert len(versions) == 1

    def test_python_version_file_says_3_12(self):
        assert (ROOT / '.python-version').read_text().strip() == '3.12'

    def test_bandit_is_pinned_to_an_exact_version(self):
        text = '\n'.join(s['run'] for _n, job in _all_jobs(_security())
                         for s in job['steps'] if 'run' in s)
        installs = re.findall(r'pip install\s+(bandit\S*)', text)
        assert installs, 'security.yml must install bandit'
        for spec in installs:
            assert re.fullmatch(r'bandit==\d+(\.\d+)+', spec), spec

    def test_security_scan_still_runs_bandit_on_the_app(self):
        text = '\n'.join(s['run'] for _n, job in _all_jobs(_security())
                         for s in job['steps'] if 'run' in s)
        assert 'bandit -r app/' in text


# CI-3 -------------------------------------------------------------------------

class TestTestJob:
    def test_runs_on_push_to_main_and_pull_requests_to_main(self):
        triggers = _triggers(_ci())
        assert triggers['push']['branches'] == ['main']
        assert triggers['pull_request']['branches'] == ['main']

    def test_installs_requirements_and_runs_pytest_with_coverage(self):
        job = _ci()['jobs']['test']
        text = _run_text(job)
        assert 'pip install -r requirements.txt' in text
        assert re.search(r'\bpytest\b.*--cov', text)

    def test_uses_python_3_12_with_the_pip_cache(self):
        setup = _steps_using(_ci()['jobs']['test'], 'actions/setup-python')
        assert [(s['with']['python-version'], s['with'].get('cache')) for s in setup] == [('3.12', 'pip')]

    def test_uploads_the_coverage_report_as_an_artifact(self):
        uploads = _steps_using(_ci()['jobs']['test'], 'actions/upload-artifact')
        assert len(uploads) == 1
        # the file that pytest-cov writes is the one that gets uploaded
        assert uploads[0]['with']['path'] == 'coverage.xml'
        assert '--cov-report=xml' in _run_text(_ci()['jobs']['test'])

    def test_a_failing_test_fails_the_job(self):
        # no step may swallow the test result
        for step in _ci()['jobs']['test']['steps']:
            assert step.get('continue-on-error') in (None, False)
            assert '|| true' not in step.get('run', '')


# CI-4 shape --------------------------------------------------------------------

class TestMigrationsJobShape:
    def test_has_a_postgres_service_and_the_four_commands(self):
        job = _pg_job()
        assert 'postgres' in job['services']
        text = _run_text(job)
        for command in ('flask db upgrade', 'flask db check', 'flask db downgrade',
                        'pytest -m postgres'):
            assert command in text

    def test_no_step_swallows_a_failure(self):
        for step in _pg_job()['steps']:
            assert step.get('continue-on-error') in (None, False)
            assert '|| true' not in step.get('run', '')

    def test_the_round_trip_stops_at_the_first_failure(self):
        # `set -e` (via pipefail) so a failing `flask db check` fails the step
        step = next(s for s in _pg_job()['steps'] if 'flask db upgrade' in s.get('run', ''))
        assert 'set -euo pipefail' in step['run']


# CI-5 -------------------------------------------------------------------------

SELF_DESTROY_BUILD = 'npx vite build --outDir "$RUNNER_TEMP/self-destroy-dist" --emptyOutDir'
SELF_DESTROY_CHECK = 'node scripts/check-dist.mjs --self-destroy "$RUNNER_TEMP/self-destroy-dist"'


class TestFrontendJob:
    """CI-5 after unit a (R9): `frontend/package.json` exists, so no step is guarded."""

    @staticmethod
    def _steps():
        return _ci()['jobs']['frontend']['steps']

    def test_exists_and_the_frontend_project_is_in_the_repository(self):
        assert 'frontend' in _ci()['jobs']
        assert (ROOT / 'frontend' / 'package.json').is_file()
        assert (ROOT / 'frontend' / 'package-lock.json').is_file()

    def test_no_step_is_skipped_by_a_hashfiles_guard(self):
        job = _ci()['jobs']['frontend']
        assert 'hashFiles' not in str(job.get('if', ''))
        for step in self._steps():
            assert 'hashFiles' not in str(step.get('if', '')), step.get('name')
            assert 'if' not in step, step.get('name')

    def test_steps_run_in_the_documented_order(self):
        steps = self._steps()
        shape = [
            (str(step['uses']).split('@')[0], None) if 'uses' in step else (None, step['run'])
            for step in steps
        ]
        assert shape == [
            ('actions/checkout', None),
            ('actions/setup-node', None),
            (None, 'npm ci'),
            (None, 'npm run lint'),
            (None, 'npm run typecheck'),
            (None, 'npx vitest run'),
            (None, 'npm run build'),
            (None, 'npm run check:dist'),
            (None, SELF_DESTROY_BUILD),
            (None, SELF_DESTROY_CHECK),
            ('actions/upload-artifact', None),
        ]

    def test_the_manifest_check_runs_after_the_build_and_before_the_upload(self):
        """CI-5 'Manifest check': check-dist verifies manifest, icons and worker of the real build."""
        runs = [step.get('run') for step in self._steps()]
        uses = [str(step.get('uses', '')).split('@')[0] for step in self._steps()]
        check = runs.index('npm run check:dist')
        assert runs.index('npm run build') < check < uses.index('actions/upload-artifact')

    def test_the_self_destroying_build_goes_outside_the_uploaded_artifact(self):
        """PWA-5 / task 6.14: the rollback worker is built and checked on every run, never shipped."""
        steps = self._steps()
        (build,) = [s for s in steps if s.get('run') == SELF_DESTROY_BUILD]
        (check,) = [s for s in steps if s.get('run') == SELF_DESTROY_CHECK]
        assert build['env'] == {'VITE_PWA_SELF_DESTROY': 'true'}
        assert '--outDir "$RUNNER_TEMP/self-destroy-dist"' in build['run']
        assert '--emptyOutDir' in build['run']
        assert '--self-destroy "$RUNNER_TEMP/self-destroy-dist"' in check['run']
        for step in (build, check):
            assert 'frontend/dist' not in step['run']
            assert 'if' not in step

    def test_node_version_comes_from_nvmrc_with_the_npm_cache_of_the_lockfile(self):
        setup = _steps_using(_ci()['jobs']['frontend'], 'actions/setup-node')
        assert [s['with'] for s in setup] == [{
            'node-version-file': '.nvmrc',
            'cache': 'npm',
            'cache-dependency-path': 'frontend/package-lock.json',
        }]
        assert (ROOT / '.nvmrc').read_text().strip()

    def test_the_commands_run_inside_the_frontend_directory(self):
        job = _ci()['jobs']['frontend']
        assert job['defaults']['run']['working-directory'] == 'frontend'

    def test_the_dist_is_uploaded_as_the_frontend_dist_artifact(self):
        uploads = _steps_using(_ci()['jobs']['frontend'], 'actions/upload-artifact')
        assert len(uploads) == 1
        assert uploads[0]['uses'] == 'actions/upload-artifact@v4'
        assert uploads[0]['with'] == {
            'name': 'frontend-dist',
            'path': 'frontend/dist',
            'if-no-files-found': 'error',
            'retention-days': 7,
        }

    def test_the_workflow_still_grants_only_read_access(self):
        assert _ci()['permissions'] == {'contents': 'read'}
        assert 'permissions' not in _ci()['jobs']['frontend']

    def test_nvmrc_is_a_pinned_major_version(self):
        assert re.fullmatch(r'v?\d+(\.\d+){0,2}', (ROOT / '.nvmrc').read_text().strip())

    def test_no_step_swallows_a_failure(self):
        for step in self._steps():
            assert step.get('continue-on-error') in (None, False)
            assert '|| true' not in step.get('run', '')


# CI-6 -------------------------------------------------------------------------

class TestLeastPrivilege:
    @pytest.mark.parametrize('path', WORKFLOWS, ids=lambda p: p.name)
    def test_every_workflow_declares_permissions(self, path):
        assert 'permissions' in _load(path)

    @pytest.mark.parametrize('name', ['ci.yml', 'security.yml'])
    def test_ci_and_security_only_read(self, name):
        workflow = _load(ROOT / '.github' / 'workflows' / name)
        assert workflow['permissions'] == {'contents': 'read'}
        for job_name, job in _all_jobs(workflow):
            assert 'permissions' not in job or job['permissions'] == {'contents': 'read'}, job_name

    def test_only_the_release_job_can_write(self):
        release = _release()
        assert release['permissions'] == {'contents': 'read'}
        assert release['jobs']['release']['permissions'] == {'contents': 'write'}

    @pytest.mark.parametrize('path', WORKFLOWS, ids=lambda p: p.name)
    def test_nothing_else_asks_for_write(self, path):
        workflow = _load(path)
        writers = [name for name, job in _all_jobs(workflow)
                   if 'write' in str(job.get('permissions', ''))]
        assert writers == (['release'] if path.name == 'release.yml' else [])


# CI-7 -------------------------------------------------------------------------

class TestRepositoryHygiene:
    @pytest.mark.parametrize('name', ['package.json', 'package-lock.json', 'diagnose.py',
                                      'docs/riftbound-landing.service'])
    def test_obsolete_file_is_gone(self, name):
        assert not (ROOT / name).exists()

    @pytest.mark.parametrize('entry', ['node_modules/', 'frontend/dist/', '.vite/'])
    def test_gitignore_has_the_frontend_entries(self, entry):
        lines = [line.strip() for line in (ROOT / '.gitignore').read_text().splitlines()]
        assert entry in lines


# CI-9 -------------------------------------------------------------------------

class TestFrontendHygiene:
    def test_dist_is_ignored_by_git(self):
        import subprocess
        # a file inside, so the answer does not depend on `frontend/dist` existing (clean checkout)
        result = subprocess.run(['git', 'check-ignore', '-q', 'frontend/dist/index.html'], cwd=ROOT)
        assert result.returncode == 0

    def test_node_modules_and_the_vite_cache_are_ignored_too(self):
        import subprocess
        for path in ('frontend/node_modules/react/index.js', 'frontend/.vite/deps/x.js'):
            assert subprocess.run(['git', 'check-ignore', '-q', path], cwd=ROOT).returncode == 0, path

    def test_the_lockfile_is_not_ignored(self):
        import subprocess
        lock = 'frontend/package-lock.json'
        assert (ROOT / lock).is_file()
        assert subprocess.run(['git', 'check-ignore', '-q', lock], cwd=ROOT).returncode == 1
