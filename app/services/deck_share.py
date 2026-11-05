"""Share links of decks and the public read-only deck (F5-g, D-F5-4).

A share link is the head's `rbdkh_share_slug`: 22 url-safe random characters
(`secrets.token_urlsafe(16)`, 128 bits), unique. Sharing a shared deck gives the same slug;
revoking clears it, so the old URL is a 404 at once, and sharing again draws a new one.
Neither changes the deck's `updated_at` (the content did not change).

The public deck shows the name, mode, visibility, content, cards, legality (both modes, bans
of the moment), value and `updated_at`; the owner's username only when the deck is public.
It never shows the deck or user ids, the email, versions, notes, the creation date, the share
slug, the owner's copies (`owned_total` is null) or the workbench: the content, cards, counts,
value and legality are those of the deck without its workbench.
"""
import re
import secrets

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import RbDeckHead, User
from app.services import decks
from app.services.decks import DeckNotFound

SLUG_BYTES = 16
SLUG_RE = re.compile(r'[A-Za-z0-9_-]{22}')
ATTEMPTS = 5


class SlugUnavailable(Exception):
    """No free slug after ATTEMPTS draws (never expected with 128 random bits)."""


def _taken(slug):
    return db.session.execute(sa.select(RbDeckHead.rbdkh_id).where(
        RbDeckHead.rbdkh_share_slug == slug)).first() is not None


def share(user, deck_id):
    """`{slug, url}` of the deck's link, created when it has none (a taken slug is drawn
    again; so is one lost to a concurrent request)."""
    for _ in range(ATTEMPTS):
        head = decks._head(user, deck_id, lock=True)
        if head.rbdkh_share_slug:
            return decks.share_item(head.rbdkh_share_slug)
        slug = secrets.token_urlsafe(SLUG_BYTES)
        if _taken(slug):
            continue
        head.rbdkh_share_slug = slug
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            continue
        return decks.share_item(slug)
    raise SlugUnavailable(deck_id)


def unshare(user, deck_id):
    """Revoke the deck's link (nothing to do when it has none); returns the new `share`."""
    head = decks._head(user, deck_id, lock=True)
    if head.rbdkh_share_slug is not None:
        head.rbdkh_share_slug = None
        db.session.commit()
    return None


def public_deck(slug):
    """The read-only deck behind `slug`; `DeckNotFound` for an unknown, revoked or malformed
    slug alike. Statements: head + owner, current version, cards, sets, bans, prices (2)."""
    if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
        raise DeckNotFound(slug)
    row = db.session.execute(
        sa.select(RbDeckHead, User.username)
        .join(User, User.id == RbDeckHead.rbdkh_user_id)
        .where(RbDeckHead.rbdkh_share_slug == slug)).first()
    if row is None:
        raise DeckNotFound(slug)
    head, username = row
    version = decks._current(head)
    content = decks.normal_content(version.rbdkv_content if version else None)
    content['workbench'] = []
    cat = decks._Catalog(None)
    cat.load([content])
    analysis = decks._analysis(content, cat)
    del content['workbench']
    del analysis['counts']['workbench']
    out = {'name': head.rbdkh_name, 'mode': head.rbdkh_mode,
           'visibility': head.rbdkh_visibility,
           'owner': {'username': username} if head.rbdkh_visibility == 'public' else None,
           'updated_at': decks._iso(head.rbdkh_updated_at), 'content': content,
           'cards': cat.cards(ref for _z, _f, ref, _q in decks._refs(content))}
    out.update(analysis)
    return out
