"""`flask riot ...`: Riot sync maintenance from the server shell (owner feedback
2026-10-29, S17).

`recheck-pending` re-evaluates every pending proposal with the rules the sync
uses today (`app/services/riot_sync.py::gallery_value`) against the stored card,
without the network, and marks the ones that are no longer a change `obsolete`
(never deleted). Take a `pg_dump` first (docs/knowledge/ops-runbook.md).
"""
import click
from flask.cli import AppGroup

from app import db
from app.services import riot_sync

riot_cli = AppGroup('riot', help='Riot sync maintenance (proposed card changes).')


@riot_cli.command('recheck-pending')
@click.option('--dry-run', is_flag=True, help='Count only; change nothing.')
def recheck_pending(dry_run):
    """Mark pending proposals the sync rules no longer produce as obsolete."""
    result = riot_sync.recheck_pending(dry_run=dry_run)
    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    click.echo(f"Checked {result['checked']} pending proposals: {result['obsolete']} obsolete, "
               f"{result['pending']} still pending.")
    for key, count in result['by_set_field'].items():
        click.echo(f'  {key}: {count}')
    if dry_run:
        click.echo('Dry run: nothing was changed.')
