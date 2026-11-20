"""`flask bans ...`: card bans per game mode from the server shell (F2-a S7).

Until the F10 admin UI this is the only way to change bans. `add` and `remove`
are idempotent; `add` checks the name against the catalog (by `name_key`)
unless `--force`. `--mode all` means every mode, in GAME_MODES order.

A ban applies from its `--since` date (UTC calendar date); a later date makes it
upcoming: stored and shown, marked "not yet in effect", but not applied until then.
"""
import click
from flask.cli import AppGroup

from app.models.ban import REASON_MAX_LENGTH
from app.schemas.game_domain import GAME_MODES
from app.services import bans

bans_cli = AppGroup('bans', help='Manage card bans per game mode (1v1, 2v2).')

_MODE_OR_ALL = click.Choice([*GAME_MODES, 'all'])


def _modes(mode: str) -> list[str]:
    return list(GAME_MODES) if mode == 'all' else [mode]


def _upcoming(entry) -> str:
    """`from YYYY-MM-DD, not yet in effect`, or '' when the ban is in effect today."""
    return '' if bans.in_effect(entry) else f'from {entry.since:%Y-%m-%d}, not yet in effect'


@bans_cli.command('list')
@click.option('--mode', type=click.Choice(GAME_MODES), help='Only the bans of one mode.')
def list_bans(mode):
    """List the bans, by mode and then name; upcoming ones are marked."""
    found = bans.list_bans(mode)
    if not found:
        click.echo('No bans.')
        return
    for ban in found:
        line = f'{ban.mode}  {ban.since:%Y-%m-%d}  {ban.name}'
        if ban.reason:
            line += f'  — {ban.reason}'
        if upcoming := _upcoming(ban):
            line += f'  ({upcoming})'
        click.echo(line)


@bans_cli.command('add')
@click.argument('name')
@click.option('--mode', type=_MODE_OR_ALL, required=True, help='1v1, 2v2 or all.')
@click.option('--since', type=click.DateTime(formats=['%Y-%m-%d']),
              help='Date the ban applies from (YYYY-MM-DD, UTC); default today. '
                   'A later date stores the ban as upcoming (not yet in effect).')
@click.option('--reason', help=f'Free text, at most {REASON_MAX_LENGTH} characters.')
@click.option('--force', is_flag=True, help='Ban the name even if no catalog card has it.')
def add(name, mode, since, reason, force):
    """Ban the card NAME (every printing) in a mode."""
    try:
        results = bans.add_ban(name, _modes(mode), since=since.date() if since else None,
                               reason=reason, force=force)
    except bans.UnknownCardName:
        raise click.ClickException(
            f"No card named '{name}' in the catalog (use --force to ban it anyway).")
    except ValueError:
        raise click.ClickException(
            f'The reason must be at most {REASON_MAX_LENGTH} characters.')
    entries = bans.ban_map(include_upcoming=True)[bans.name_key(name)]
    for result_mode, status in results:
        entry = entries[result_mode]
        upcoming = _upcoming(entry)
        if status == 'added':
            when = upcoming or f'since {entry.since:%Y-%m-%d}'
            click.echo(f"Banned '{entry.name}' in {result_mode} {when}.")
        elif status == 'updated':
            click.echo(f"Updated the ban of '{entry.name}' in {result_mode}"
                       + (f': {upcoming}.' if upcoming else '.'))
        else:
            click.echo(f"'{entry.name}' is already banned in {result_mode}"
                       + (f' {upcoming}.' if upcoming else '.'))


@bans_cli.command('remove')
@click.argument('name')
@click.option('--mode', type=_MODE_OR_ALL, required=True, help='1v1, 2v2 or all.')
def remove(name, mode):
    """Lift the ban of the card NAME in a mode."""
    entries = bans.ban_map(include_upcoming=True).get(bans.name_key(name), {})
    for result_mode, status in bans.remove_ban(name, _modes(mode)):
        if status == 'removed':
            click.echo(f"Unbanned '{entries[result_mode].name}' in {result_mode}.")
        else:
            click.echo(f"'{name}' was not banned in {result_mode}.")
