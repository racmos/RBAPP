"""`flask users ...`: account administration from the server shell (ACL-6, D11).

This is the ONLY way to create an admin: no migration, environment variable or
request can. It works while no admin exists (that is how the owner is
bootstrapped: `flask users promote <username>`).

Every command that takes a username exits 1 with a message naming the user
when it does not exist, and changes nothing. `promote`, `demote`, `block` and
`unblock` are idempotent. `block` and `set-password` end every session of the
user (F9-a) and say how many; `reset-2fa` removes the user's two-factor authentication
and ends every session too (F9-d). `create` makes one account through the registration
rules (`register_user`), an admin with `--admin` (RESET-a). Passwords are only ever read
from a hidden prompt (or, for `create` only, the `RB_NEW_PASSWORD` environment variable),
never taken as an argument and never printed; `list` never shows hashes.
"""
import os

import click
from flask.cli import AppGroup
from pydantic import ValidationError

from app import db
from app.models import User
from app.schemas.validators import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH, RegisterRequest
from app.services import sessions
from app.utils import clock

users_cli = AppGroup('users',
                     help='Manage user accounts (creation, roles, blocking, passwords, 2FA).')

# `flask users create` reads the password from here when it is set and not empty (RESET-a).
NEW_PASSWORD_ENV = 'RB_NEW_PASSWORD'


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
    """Block USERNAME: no login, and every session of the user ends (F9-a)."""
    user = _find_user(username)
    if user.is_blocked:
        click.echo(f"'{username}' is already blocked")
        return
    user.is_blocked = True
    ended = sessions.revoke_all(user.id, commit=False)
    db.session.commit()
    click.echo(f"'{username}' is now blocked; {ended} session(s) ended")


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
    ended = sessions.revoke_all(user.id, commit=False)    # every session, in one transaction
    db.session.commit()
    click.echo(f"Password updated for '{username}'; {ended} session(s) ended")


def _first_error(error: ValidationError, skip: tuple = ()) -> str | None:
    """The message of the first validation error whose field is not in `skip`."""
    for item in error.errors():
        if item['loc'][:1] not in skip:
            return item['msg']
    return None


@users_cli.command('create')
@click.argument('username')
@click.option('--email', default=None, help='E-mail address (optional; blank = none).')
@click.option('--admin', is_flag=True, help='Make the new account an admin.')
def create(username, email, admin):
    """Create the account USERNAME (RESET-a).

    The password comes from the RB_NEW_PASSWORD environment variable when it is set
    and not empty, otherwise from a hidden prompt asked twice. The registration rules
    apply (username, e-mail, 8 to 128 characters, nothing taken twice).
    """
    from app.services.auth import DuplicateUserError, register_user
    fields = {'username': username, 'email': email}
    try:                                  # username and e-mail before asking for anything
        RegisterRequest.model_validate(fields)
    except ValidationError as error:
        message = _first_error(error, skip=(('password',),))
        if message:
            raise click.ClickException(message) from None

    password = os.environ.get(NEW_PASSWORD_ENV) or ''
    if not password:
        password = click.prompt('New password', hide_input=True)
        if click.prompt('Repeat the password', hide_input=True) != password:
            raise click.ClickException('The two passwords do not match; nothing was changed.')
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise click.ClickException(
            f'The password must have {PASSWORD_MIN_LENGTH} to {PASSWORD_MAX_LENGTH} characters.')

    try:
        data = RegisterRequest(**fields, password=password)
    except ValidationError as error:      # not expected: every field was checked above
        raise click.ClickException(_first_error(error) or 'Invalid account data.') from None
    try:
        register_user(data, is_admin=admin)
    except DuplicateUserError as error:
        if error.field == 'username':
            raise click.ClickException(f"Username already taken: '{username}'") from None
        raise click.ClickException('E-mail already taken.') from None    # never echoed
    click.echo(f"Created '{username}' (admin)." if admin else f"Created '{username}'.")


@users_cli.command('reset-2fa')
@click.argument('username')
def reset_2fa(username):
    """Remove USERNAME's two-factor authentication and end all their sessions (F9-d)."""
    from app.services import mfa
    user = _find_user(username)
    ended = mfa.reset(user)
    if ended is None:
        click.echo(f"'{username}' has no two-factor authentication")
        return
    click.echo(f"Two-factor authentication removed for '{username}'; {ended} session(s) ended")


@users_cli.command('list')
def list_users():
    """List every account with its role and state (never password hashes); `-` = no e-mail."""
    accounts = User.query.order_by(User.username).all()
    if not accounts:
        click.echo('No users.')
        return
    for user in accounts:
        locked = user.locked_until is not None and user.locked_until > clock.utcnow()
        flags = [name for name, on in (('admin', user.is_admin), ('blocked', user.is_blocked),
                                       ('locked', locked)) if on]
        click.echo(f"{user.username}  {user.email or '-'}  {','.join(flags)}".rstrip())


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
