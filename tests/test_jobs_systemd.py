"""F4-a S5/S6: systemd templates under docs/systemd/ and the runbook section.

The templates hold placeholders only: the same user, working directory and
environment file as docs/riftbound.service, and no host values."""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SYSTEMD = REPO / 'docs' / 'systemd'
F4B_NOTE = '# Install with F4-b (the daily_prices kind does not exist before it)'
IPV4 = re.compile(r'\b\d{1,3}(?:\.\d{1,3}){3}\b')


def _directives(path):
    """`Key=value` lines of a unit file (comments skipped); repeated keys keep the last."""
    found = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith(('#', ';', '[')) and '=' in line:
            key, _, value = line.partition('=')
            found[key] = value
    return found


APP = _directives(REPO / 'docs' / 'riftbound.service')
VENV_FLASK = APP['WorkingDirectory'] + '/venv/bin/flask'

UNITS = ['riftbound-jobs.service', 'riftbound-jobs.timer', 'riftbound-daily.service',
         'riftbound-daily.timer', 'riftbound-daily-retry.service',
         'riftbound-daily-retry.timer']


def test_exactly_the_six_templates_exist():
    assert sorted(p.name for p in SYSTEMD.iterdir()) == sorted(UNITS)


@pytest.mark.parametrize('name', [u for u in UNITS if u.endswith('.service')])
def test_services_run_oneshot_like_the_app_service(name):
    unit = _directives(SYSTEMD / name)
    assert unit['Type'] == 'oneshot'
    for key in ('User', 'Group', 'WorkingDirectory', 'EnvironmentFile'):
        assert unit[key] == APP[key], key


def test_jobs_service_runs_the_runner_under_flock():
    unit = _directives(SYSTEMD / 'riftbound-jobs.service')
    assert unit['ExecStart'] == (
        f'/usr/bin/flock -n /run/riftbound/jobs.lock {VENV_FLASK} jobs run-pending')
    assert unit['RuntimeDirectory'] == 'riftbound'


def test_jobs_timer_every_minute():
    unit = _directives(SYSTEMD / 'riftbound-jobs.timer')
    assert unit['OnCalendar'] == '*-*-* *:*:00'
    assert unit['Persistent'] == 'false'
    assert unit['Unit'] == 'riftbound-jobs.service'
    assert unit['WantedBy'] == 'timers.target'


def test_daily_units():
    service = SYSTEMD / 'riftbound-daily.service'
    assert _directives(service)['ExecStart'] == f'{VENV_FLASK} jobs enqueue daily_prices'
    timer = _directives(SYSTEMD / 'riftbound-daily.timer')
    assert timer['OnCalendar'] == '*-*-* 06:30:00 Europe/Madrid'
    assert timer['Unit'] == 'riftbound-daily.service'


def test_retry_units_leave_the_command_to_f4b():
    assert 'ExecStart' not in _directives(SYSTEMD / 'riftbound-daily-retry.service')
    timer = _directives(SYSTEMD / 'riftbound-daily-retry.timer')
    assert timer['OnCalendar'] == '*-*-* 08:00:00 Europe/Madrid'
    assert timer['Unit'] == 'riftbound-daily-retry.service'


@pytest.mark.parametrize('name', [u for u in UNITS if 'daily' in u])
def test_daily_and_retry_units_wait_for_f4b(name):
    assert F4B_NOTE in (SYSTEMD / name).read_text(encoding='utf-8')


@pytest.mark.parametrize('name', UNITS)
def test_no_host_values(name):
    text = (SYSTEMD / name).read_text(encoding='utf-8')
    assert not IPV4.search(text)
    assert 'http' not in text


def test_runbook_scheduled_jobs_section():
    runbook = (REPO / 'docs' / 'knowledge' / 'ops-runbook.md').read_text(encoding='utf-8')
    section = runbook.split('## Scheduled jobs', 1)[1].split('\n## ', 1)[0]
    for needle in ('docs/systemd/', 'systemctl daemon-reload',
                   'systemctl enable --now riftbound-jobs.timer',
                   'flask jobs enqueue heartbeat', 'flask jobs list',
                   'journalctl -u riftbound-jobs.service', 'flask jobs run-pending',
                   'systemctl disable --now riftbound-jobs.timer', 'F4-b',
                   'flask db upgrade', 'flask db check'):
        assert needle in section, needle
