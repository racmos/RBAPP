"""`flask reset ...`: the production data reset (RESET-b).

`production-data` empties the database for production, keeping the Cardmarket load history, the
seeded ban list and the `--keep-user` accounts (classification:
`app/services/data_reset.py::TABLE_POLICY`).
A dry run by default; `--execute` needs `--backup` and `--confirm "RESET <database>"`. Never run it
on real data without the rehearsal and the runbook of
docs/requirements/F12/RESET-production-data-reset.md (sections 10 and 11).
"""
import click
from flask import current_app
from flask.cli import AppGroup

from app.services import data_reset

reset_cli = AppGroup('reset', help='Production data reset (destructive; read the runbook first).')


class _UsageFailure(click.ClickException):
    """`Error: <message>` on stderr, exit 2 (bad input), without the usage text."""
    exit_code = 2


@reset_cli.command('production-data')
@click.option('--keep-user', 'keep_users', multiple=True, required=True, metavar='USERNAME',
              help='Account to keep (repeatable, at least one).')
@click.option('--database', required=True, metavar='NAME',
              help='Name of the database the app is connected to.')
@click.option('--env', 'env', required=True, metavar='VALUE', help='RB_ENV of this process.')
@click.option('--backup', type=click.Path(path_type=str), metavar='PATH',
              help='pg_dump -Fc file of this database, taken in the last 6 hours.')
@click.option('--allow-test-db', is_flag=True,
              help='Allow a database whose name contains "test" (rehearsal).')
@click.option('--execute', is_flag=True, help='Really delete (default: dry run).')
@click.option('--confirm', metavar='PHRASE', help='Exactly "RESET <database>" (with --execute).')
def production_data(keep_users, database, env, backup, allow_test_db, execute, confirm):
    """Empty the database for production (dry run unless --execute)."""
    if execute and confirm is None:
        raise _UsageFailure(f'--execute needs --confirm "RESET {database}".')
    if confirm is not None and not execute:
        raise _UsageFailure('--confirm is only used with --execute.')
    if execute and not backup:
        raise _UsageFailure('--execute needs --backup PATH.')
    try:
        data_reset.check_target(database, env, allow_test_db)
        if execute and confirm != f'RESET {database}':
            raise data_reset.ResetRefused('The confirmation does not match; nothing was changed.')
        revision = data_reset.check_state()
        info = data_reset.check_backup(backup, database) if backup else None
        plan = data_reset.build_plan(keep_users)
    except data_reset.ResetRefused as refusal:
        _end_transaction()
        raise click.ClickException(str(refusal)) from None

    _print_report(database, revision, env, info, plan)
    if not execute:
        _end_transaction()
        click.echo(f'Dry run: nothing was changed. Run again with --execute --confirm '
                   f'"RESET {database}".')
    else:
        try:
            rows, tables, cleared = data_reset.execute(plan, keep_users, database, info.name)
        except data_reset.ResetRefused as refusal:
            raise click.ClickException(str(refusal)) from None
        except Exception as error:
            current_app.logger.exception('flask reset production-data failed')
            raise click.ClickException(f'Reset failed ({type(error).__name__}); rolled back, '
                                       'nothing was changed.') from None
        click.echo(f'Reset done: {rows} rows deleted in {tables} tables, {cleared} expansion '
                   'mappings cleared; kept tables unchanged.')
    if not plan.admin_kept:
        click.echo('No kept user is an admin: create one with flask users create <name> --admin.')


def _end_transaction():
    """The guards and the dry run only read: close their transaction without writing."""
    from app import db
    db.session.rollback()


def _print_report(database, revision, env, info, plan):
    click.echo(f'Database: {database} at {revision}; RB_ENV {env}')
    if info is None:
        click.echo('Backup: not given (needed for --execute)')
    else:
        click.echo(f'Backup: {info.name}, {info.size} bytes, {info.entries} TOC entries, '
                   f'{info.age_hours:.1f} h old')
    names = ', '.join(plan.kept_users) or '-'
    missing = ', '.join(plan.missing_users) or '-'
    click.echo(f'Users: keep {len(plan.kept_users)} ({names}), delete {plan.deleted_users}; '
               f'missing: {missing}')
    for line in plan.tables:
        click.echo(line.text())
