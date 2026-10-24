"""One clock (M-c, S6): `app/` reads time only through `app.utils.clock`.

`datetime.utcnow` is deprecated and cannot be frozen by `frozen_clock`; call
sites use `clock.utcnow()` and column defaults `lambda: clock.utcnow()`.
"""
import re
from pathlib import Path

from app import db
from tests.migration_helpers import drift, upgrade

APP_DIR = Path(__file__).resolve().parent.parent / 'app'
FORBIDDEN = re.compile(r'\bdatetime\.utcnow\b')


def test_no_datetime_utcnow_under_app():
    offenders = [
        f'{path.relative_to(APP_DIR.parent)}:{number}: {line.strip()}'
        for path in sorted(APP_DIR.rglob('*.py'))
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1)
        if FORBIDDEN.search(line)
    ]
    assert offenders == []


def test_column_defaults_follow_the_frozen_clock(app, make_user, frozen_clock):
    user = make_user('clockuser')
    db.session.refresh(user)
    assert user.created_at == frozen_clock()


def test_the_migrated_schema_has_no_drift(migration_app):
    upgrade()
    assert drift() == []
