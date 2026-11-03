"""Nightly database backup: pg_dump of the `riftbound` schema into ~/backups/rbapp.

Reads DATABASE_URL from the git-ignored .env, never prints it. Keeps the files of
the last KEEP_DAYS days (dumps named riftbound_nightly_*.dump only; the manual
riftbound_pre_*.dump files taken before a migration are never touched).

    venv/bin/python scripts/db_backup.py [--dir DIR] [--keep-days N]

Exit code 0 on success, non-zero when pg_dump fails (systemd records it).
"""
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

PG_DUMP = os.environ.get('PG_DUMP', '/home/linuxbrew/.linuxbrew/opt/libpq/bin/pg_dump')
PREFIX = 'riftbound_nightly_'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--dir', default=str(Path.home() / 'backups' / 'rbapp'))
    parser.add_argument('--keep-days', type=int, default=14)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    url = make_url(dotenv_values(root / '.env')['DATABASE_URL'])
    out_dir = Path(args.dir)
    out_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    out = out_dir / f'{PREFIX}{datetime.now():%Y%m%d_%H%M}.dump'

    env = dict(os.environ, PGPASSWORD=url.password or '')
    result = subprocess.run(
        [PG_DUMP, '-h', url.host, '-p', str(url.port or 5432), '-U', url.username,
         '-d', url.database, '-n', 'riftbound', '-Fc', '-f', str(out)],
        env=env, capture_output=True, text=True)
    if result.returncode != 0:
        out.unlink(missing_ok=True)
        # pg_dump messages do not contain the password; still never echo the URL.
        print(f'pg_dump failed ({result.returncode}): {result.stderr.strip()[:500]}', file=sys.stderr)
        return result.returncode
    out.chmod(0o600)

    cutoff = time.time() - args.keep_days * 86400
    removed = 0
    for old in out_dir.glob(f'{PREFIX}*.dump'):
        if old != out and old.stat().st_mtime < cutoff:
            old.unlink()
            removed += 1
    print(f'backup {out.name} {out.stat().st_size} bytes; removed {removed} older than {args.keep_days} days')
    return 0


if __name__ == '__main__':
    sys.exit(main())
