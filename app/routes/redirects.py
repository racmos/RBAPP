"""The old Jinja URLs after the retirement of the Jinja web (PR 3/3).

`/`, `/riftbound` and the bookmarks of the old pages answer a 302 to the matching
screen of the React app at /riftbound/app/. 302 and not 301: browsers would cache
a 301 for ever, and the landing page returns at `/` in F8.

    /, /riftbound, /riftbound/         -> /riftbound/app/
    /riftbound/login                   -> /riftbound/app/login (keeps a safe `next`)
    /riftbound/register                -> /riftbound/app/register
    /riftbound/card                    -> /riftbound/app/cards
    /riftbound/collection              -> /riftbound/app/collection
    /riftbound/deck, /deck/view/<any>  -> /riftbound/app/decks
    /riftbound/profile                 -> /riftbound/app/account/profile
    /riftbound/price                   -> /riftbound/app/admin/cardmarket
    /riftbound/set                     -> /riftbound/app/  (the Sets page was dropped)

The routes are public, GET (and HEAD) only, and never touch `session` or
`current_user`, so no response carries a `Set-Cookie`.
"""
import re
from urllib.parse import quote, unquote

from flask import Blueprint, redirect, request

redirects_bp = Blueprint('legacy_redirects', __name__)

APP_ROOT = '/riftbound/app/'
APP_LOGIN = '/riftbound/app/login'

# Same checks as the app's `auth/safeNext.ts`: only paths under /riftbound/, and
# no form of the value (raw, decoded once, decoded twice) may be usable for an
# open redirect.
NEXT_PREFIX = '/riftbound/'
_CONTROL = re.compile(r'[\x00-\x1f\x7f]')
_SCHEME = re.compile(r'^[a-z][a-z0-9+.-]*:', re.IGNORECASE)
_MAX_DECODES = 2

# old path -> (endpoint name, target)
_PAGES = {
    '/riftbound/register': ('register', '/riftbound/app/register'),
    '/riftbound/card': ('cards', '/riftbound/app/cards'),
    '/riftbound/collection': ('collection', '/riftbound/app/collection'),
    '/riftbound/deck': ('decks', '/riftbound/app/decks'),
    '/riftbound/deck/view/<path:_deck>': ('deck_view', '/riftbound/app/decks'),
    '/riftbound/profile': ('profile', '/riftbound/app/account/profile'),
    '/riftbound/price': ('price', '/riftbound/app/admin/cardmarket'),
    '/riftbound/set': ('sets', APP_ROOT),
}


def _hostile(value: str) -> bool:
    if _CONTROL.search(value) or '\\' in value:
        return True
    if value.startswith('//') or _SCHEME.match(value):
        return True
    return '..' in re.split(r'[?#]', value, maxsplit=1)[0].split('/')


def safe_next(value):
    """`value` unchanged when it is a same-origin path under /riftbound/, else None."""
    if not value or not value.startswith(NEXT_PREFIX):
        return None
    forms = [value]
    for _ in range(_MAX_DECODES):
        forms.append(unquote(forms[-1]))
    return None if any(_hostile(form) for form in forms) else value


def login_location(next_path=None) -> str:
    """The app's login screen, with `next` when it is safe."""
    target = safe_next(next_path)
    return f'{APP_LOGIN}?next={quote(target, safe="")}' if target else APP_LOGIN


def _to(target):
    def view(**_kwargs):
        return redirect(target, code=302)
    return view


@redirects_bp.get('/', endpoint='root')
@redirects_bp.get('/riftbound', endpoint='product')
@redirects_bp.get('/riftbound/', endpoint='product_slash')
def home():
    return redirect(APP_ROOT, code=302)


@redirects_bp.get('/riftbound/login')
def login():
    return redirect(login_location(request.args.get('next')), code=302)


for _path, (_name, _target) in _PAGES.items():
    redirects_bp.add_url_rule(_path, endpoint=_name, view_func=_to(_target), methods=['GET'])
