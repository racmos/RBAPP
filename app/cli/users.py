"""`flask users ...`: account administration from the server shell (ACL-6, D11).

This is the ONLY way to create an admin: no migration, environment variable or
request can. It works while no admin exists (that is how the owner is
bootstrapped: `flask users promote <username>`).

Every command that takes a username exits 1 with a message naming the user
when it does not exist, and changes nothing. `promote`, `demote`, `block` and
`unblock` are idempotent. Passwords are only ever read from a hidden prompt
and never printed; `list` never shows hashes.
"""
import click
from flask.cli import AppGroup

from app import db
from app.models import User
from app.schemas.validators import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from app.utils import clock

users_cli = AppGroup('users', help='Manage user accounts (roles, blocking, passwords).')


def _find_user(username: str) -> User:
    user = User.query.filter_by(username=username).first()
    if user is None:
        raise click.ClickException(f"No such user: '{username}'")
    return user


def _set_flag(username: str, field: str, value: bool, done: str, already: str) -> None:
    """Set a boolean column; report whether anything changed."""
    user = _find_user(username)
    if getattr(user, field) is value:
        click.echo(f"'{username}' {already}")
        return
    setattr(user, field, value)
    db.session.commit()
    click.echo(f"'{username}' {done}")


@users_cli.command('promote')
@click.argument('username')
def promote(username):
    """Make USERNAME an admin."""
    _set_flag(username, 'is_admin', True, 'is now an admin', 'is already an admin')


@users_cli.command('demote')
@click.argument('username')
def demote(username):
    """Remove the admin role from USERNAME."""
    _set_flag(username, 'is_admin', False, 'is no longer an admin', 'is not an admin')


@users_cli.command('block')
@click.argument('username')
def block(username):
    """Block USERNAME: no login, and any live session ends on its next request."""
    _set_flag(username, 'is_blocked', True, 'is now blocked', 'is already blocked')


@users_cli.command('unblock')
@click.argument('username')
def unblock(username):
    """Let a blocked USERNAME log in again."""
    _set_flag(username, 'is_blocked', False, 'is now unblocked', 'is not blocked')


@users_cli.command('set-password')
@click.argument('username')
def set_password(username):
    """Set a new password for USERNAME (hidden prompt, asked twice)."""
    user = _find_user(username)          # before asking for anything
    password = click.prompt('New password', hide_input=True)
    if click.prompt('Repeat the password', hide_input=True) != password:
        raise click.ClickException('The two passwords do not match; nothing was changed.')
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise click.ClickException(
            f'The password must have {PASSWORD_MIN_LENGTH} to {PASSWORD_MAX_LENGTH} characters.')
    user.set_password(password)
    db.session.commit()
    click.echo(f"Password updated for '{username}'")


@users_cli.command('list')
def list_users():
    """List every account with its role and state (never password hashes)."""
    accounts = User.query.order_by(User.username).all()
    if not accounts:
        click.echo('No users.')
        return
    for user in accounts:
        locked = user.locked_until is not None and user.locked_until > clock.utcnow()
        flags = [name for name, on in (('admin', user.is_admin), ('blocked', user.is_blocked),
                                       ('locked', locked)) if on]
        click.echo(f"{user.username}  {user.email}  {','.join(flags)}".rstrip())


@users_cli.command('unlock')
@click.argument('username')
def unlock(username):
    """Clear USERNAME's failed-login count and temporary lock (LOGIN-6)."""
    from app.services.auth import unlock_user
    if not unlock_user(username):
        raise click.ClickException(f"No such user: '{username}'")
    click.echo(f"'{username}' is unlocked")


# Spec names (ACL-6) for the same commands.
users_cli.add_command(promote, 'make-admin')
users_cli.add_command(demote, 'revoke-admin')
