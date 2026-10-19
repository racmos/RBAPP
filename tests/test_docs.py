"""AGENTS.md and README.md match the repository (CI-8, unit e).

The prose is reviewed by a person ([MANUAL], task 5.20); this pins what a
machine can check, so the docs cannot drift silently: stated versions equal the
pins in requirements.txt, every path in the structure tree exists, every table
and every environment variable is mentioned.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / 'AGENTS.md'
README = ROOT / 'README.md'


@pytest.fixture(scope='module')
def agents():
    return AGENTS.read_text(encoding='utf-8')


@pytest.fixture(scope='module')
def readme():
    return README.read_text(encoding='utf-8')


def pinned(package):
    """Version pinned for `package` in requirements.txt."""
    text = (ROOT / 'requirements.txt').read_text()
    match = re.search(rf'^{re.escape(package)}==([\w.]+)', text, re.MULTILINE | re.IGNORECASE)
    assert match, f'{package} is not pinned in requirements.txt'
    return match.group(1)


# --- AGENTS.md -----------------------------------------------------------------

class TestAgentsVersions:
    @pytest.mark.parametrize('version', ['3.1.0', '2.0.36', '2.10.5', '8.3.4'])
    def test_states_the_required_versions(self, agents, version):
        assert version in agents

    @pytest.mark.parametrize('package', [
        'Flask', 'SQLAlchemy', 'Flask-SQLAlchemy', 'pydantic', 'Flask-Login', 'Flask-Migrate',
        'alembic', 'Flask-WTF', 'Flask-Limiter', 'altcha', 'pytest', 'gunicorn',
    ])
    def test_every_stack_version_equals_the_pin(self, agents, package):
        assert pinned(package) in agents

    def test_python_version_is_the_one_ci_uses(self, agents):
        assert (ROOT / '.python-version').read_text().strip() == '3.12'
        assert 'Python 3.12' in agents

    def test_does_not_list_skills_that_do_not_exist(self, agents):
        assert 'fastapi-pro' not in agents
        assert not (ROOT / '.agent').exists()
        assert '.agent/skills' not in agents


def tree_paths(markdown):
    """Paths listed in the first fenced tree under '## Project Structure'.

    The first line of the block is the root (not returned); every other line is
    `<4 columns of indent per level><name> [# comment]`.
    """
    block = markdown.split('## Project Structure', 1)[1].split('```')[1]
    lines = [line for line in block.splitlines() if line.strip()]
    stack, paths = [], []
    for line in lines[1:]:
        match = re.match(r'^([│ ├└─]*)(\S+)', line)
        depth = len(match.group(1)) // 4
        assert depth >= 1, f'cannot place {line!r} in the tree'
        stack = stack[:depth - 1] + [match.group(2).rstrip('/')]
        paths.append('/'.join(stack))
    return paths


class TestAgentsStructure:
    def test_the_tree_lists_real_paths(self, agents):
        paths = tree_paths(agents)
        assert len(paths) > 40
        missing = [p for p in paths if '*' not in p and not (ROOT / p).exists()]
        assert missing == []

    @pytest.mark.parametrize('path', [
        'app/api', 'app/services', 'app/routes/landing.py', 'app/cli', 'app/security.py',
        'migrations/versions', '.github/workflows', 'openspec', 'app/static/js/csrf.js',
        'docs/migrations.md', 'wsgi.py',
    ])
    def test_the_tree_mentions(self, agents, path):
        assert path in tree_paths(agents)

    def test_every_table_is_named(self, agents, app):
        from app import db
        tables = sorted(t.name for t in db.metadata.tables.values())
        assert len(tables) >= 15
        missing = [name for name in tables if name not in agents]
        assert missing == []

    def test_the_cardmarket_prefix_is_explained(self, agents):
        assert 'rbcm_' in agents

    def test_every_blueprint_is_named(self, agents, app):
        for name in app.blueprints:
            if name == 'static':
                continue
            assert name in agents or f'{name}_bp' in agents, name


class TestAgentsRules:
    @pytest.mark.parametrize('needle', [
        'is_admin', '@admin_required', 'X-CSRFToken', 'csrf_token', '@validate_json',
        '/riftbound/api/v1', '"success"', 'flask db migrate', 'flask db upgrade',
        'flask db check', 'flask users promote', 'RB_ENV', 'Strict TDD',
        'gunicorn', 'run:app', 'rbcaptcha_used',
    ])
    def test_documents(self, agents, needle):
        assert needle in agents

    def test_production_command_uses_three_workers_and_run_app(self, agents):
        match = re.search(r'gunicorn[^\n`]*', agents)
        assert match
        command = match.group(0)
        assert re.search(r'(--workers|-w)[ =]3\b', command)
        assert 'run:app' in command
        # the unit file really runs that
        service = (ROOT / 'docs' / 'riftbound.service').read_text()
        assert '--workers 3' in service and 'run:app' in service

    def test_does_not_claim_four_workers(self, agents):
        assert not re.search(r'(--workers|-w)[ =]4\b', agents)

    def test_no_secret_or_private_address(self, agents):
        assert not re.search(r'\b(192\.168|10\.\d+|172\.(1[6-9]|2\d|3[01]))\.\d+\.\d+', agents)
        assert 'you-will-never-guess' not in agents


# --- README.md -------------------------------------------------------------------

class TestReadme:
    @pytest.mark.parametrize('heading', [
        'Setup', 'Environment variables', 'Running', 'Tests', 'Database migrations',
        'Admin CLI', 'Deployment',
    ])
    def test_has_the_section(self, readme, heading):
        assert re.search(rf'^#+ .*{heading}', readme, re.MULTILINE | re.IGNORECASE)

    @pytest.mark.parametrize('command', [
        'pip install -r requirements.txt', 'cp .env.example .env', 'flask db upgrade',
        'flask db check', 'flask users promote', 'flask users unlock', 'python run.py',
        'pytest', 'pytest -m postgres', 'TEST_POSTGRES_URL', 'gunicorn', 'run:app',
        'docs/riftbound.service', 'docs/nginx_config', 'docs/migrations.md',
    ])
    def test_documents(self, readme, command):
        assert command in readme

    def test_every_environment_variable_of_env_example_is_described(self, readme):
        text = (ROOT / '.env.example').read_text()
        names = sorted(set(re.findall(r'^#?\s*([A-Z][A-Z0-9_]{2,})=', text, re.MULTILINE)))
        assert len(names) > 20
        missing = [name for name in names if name not in readme]
        assert missing == []

    def test_states_the_python_version(self, readme):
        assert 'Python 3.12' in readme

    def test_no_secret_or_private_address(self, readme):
        assert not re.search(r'\b(192\.168|10\.\d+|172\.(1[6-9]|2\d|3[01]))\.\d+\.\d+', readme)
        assert 'you-will-never-guess' not in readme
