"""`flask decks ...`: decks v2 maintenance from the server shell (F5-c).

`migrate` copies the legacy `rbdecks` rows into `rbdeckheads` / `rbdeckversions`
(`app/services/deck_migration.py`, F5-R7) and prints, per deck, where every card went.
It is idempotent (a legacy row is copied once) and never modifies `rbdecks`. Take a
`pg_dump` first and review `--dry-run` (docs/knowledge/ops-runbook.md, "Decks v2 migration").
"""
import click
from flask.cli import AppGroup

from app import db
from app.services import deck_migration

decks_cli = AppGroup('decks', help='Decks v2 maintenance (legacy deck migration).')


@decks_cli.command('migrate')
@click.option('--dry-run', is_flag=True, help='Print the routing per deck; change nothing.')
@click.option('--strict', is_flag=True,
              help='Exit 1, changing nothing, when a card line cannot be resolved.')
def migrate(dry_run, strict):
    """Copy the legacy decks (rbdecks) into decks v2."""
    plan = deck_migration.plan_migration()
    for line in deck_migration.report_lines(plan):
        click.echo(line)
    if dry_run:
        click.echo('Dry run: nothing was changed.')
    unresolved = deck_migration.unresolved_count(plan)
    if strict and unresolved:
        db.session.rollback()
        word = 'line' if unresolved == 1 else 'lines'
        click.echo(f'Strict: {unresolved} unresolved {word}; nothing was changed.', err=True)
        raise SystemExit(1)
    if dry_run:
        db.session.rollback()
        return
    try:
        result = deck_migration.apply_plan(plan)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    decks = 'deck' if result['created'] == 1 else 'decks'
    versions = 'version' if result['versions'] == 1 else 'versions'
    click.echo(f"Done: {result['created']} {decks} created, {result['updated']} updated, "
               f"{result['versions']} {versions} copied.")
