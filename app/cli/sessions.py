"""`flask sessions ...`: server-side session upkeep (F9-a S13).

`purge` deletes every ended session: revoked, remembered past its `expires_at`, or not
remembered and idle for 12 hours. Active sessions are never touched. The daily job
`sessions_purge` runs the same purge.
"""
import click
from flask.cli import AppGroup

from app.services import sessions

sessions_cli = AppGroup('sessions', help='Server-side session upkeep.')


@sessions_cli.command('purge')
@click.option('--dry-run', is_flag=True, help='Only count the sessions; delete nothing.')
def purge(dry_run):
    """Delete the ended sessions (revoked, expired or idle for 12 hours)."""
    count = sessions.purge(dry_run=dry_run)
    click.echo(f"{'Would purge' if dry_run else 'Purged'} {count} session(s)")
