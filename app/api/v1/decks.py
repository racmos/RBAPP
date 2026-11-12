"""Decks v2 endpoints (F5-d): GET/POST /decks, GET/PATCH/DELETE /decks/<id>,
PUT /decks/<id>/content, versions, restore and diff; duplicate; text import and export (F5-e);
share link and the public read-only deck (F5-g); the deck against the collection and "missing
to wishlist" (F5-f). Only the owner sees a deck (D-F5-9), except through its share link."""
from flask import abort, current_app, request
from flask_login import current_user, login_required
from werkzeug.exceptions import NotFound

from app import limiter
from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail
from app.api.v1 import api_v1
from app.errors import http_error_response
from app.schemas.validation import validate_json, validate_query
from app.schemas.validators import (DeckContentPut, DeckCreate, DeckDiffQuery, DeckDuplicate,
                                    DeckExportQuery, DeckImport, DeckImportPreview,
                                    DeckMissingToWishlist, DeckPatch, DeckVersionCreate)
from app.services import deck_share, deck_vs_collection, decks
from app.services.decks import (DeckNotFound, DuplicateName, FormatUnknown, HardLimitExceeded,
                                UnknownCards, VersionNotFound)
from app.services.wishlists import ListNotFound

PUBLIC_DECK_RATE_LIMIT = '60 per minute'


def _json(data, status=200):
    """The success envelope with its key order kept (the item order is part of the shape)."""
    return current_app.response_class(
        current_app.json.dumps({'success': True, 'data': data}, sort_keys=False),
        status=status, mimetype='application/json')


def _limit_message(violation):
    name = f' ("{violation["name"]}")' if 'name' in violation else ''
    return f'{violation["rule"]} (max {violation["max"]}){name}'


def _guarded(action):
    """Run a call and turn the domain errors of `decks` into the API's error responses."""
    try:
        return action()
    except DuplicateName:
        return fail('Conflict', 'You already have a deck with that name.', 409,
                    code=ErrorCode.ALREADY_EXISTS)
    except UnknownCards as exc:
        return fail('Validation Error', 'Invalid request data', 400,
                    details=[{'field': field, 'message': f'unknown card {set_id}-{card_id}',
                              'type': 'value_error', 'code': DetailCode.INVALID_VALUE.value}
                             for field, set_id, card_id in exc.args[0]],
                    code=ErrorCode.VALIDATION_ERROR)
    except HardLimitExceeded as exc:
        violations = exc.args[0]
        return fail('Validation Error', 'The deck goes over a limit: '
                    + '; '.join(_limit_message(v) for v in violations) + '.', 400,
                    code=ErrorCode.DECK_LIMIT_EXCEEDED, params=violations[0])
    except FormatUnknown:
        return fail('Bad Request', 'The deck format is not recognised. Use the text format.',
                    400, code=ErrorCode.IMPORT_FORMAT_UNKNOWN)
    except (DeckNotFound, VersionNotFound, ListNotFound):
        abort(404)


@api_v1.get('/decks')
@login_required
def list_decks():
    """The caller's decks, newest change first, with legality per mode and value."""
    return _json({'items': decks.list_decks(current_user)})


@api_v1.post('/decks')
@login_required
@validate_json(DeckCreate)
def create_deck():
    """A new private deck with an empty version 1."""
    data = request.validated_data
    return _guarded(lambda: _json(decks.create_deck(current_user, data.name, data.mode), 201))


@api_v1.get('/decks/<int:deck_id>')
@login_required
def get_deck(deck_id):
    """One deck: current content, its cards and the legality in both modes."""
    return _guarded(lambda: _json(decks.get_deck(current_user, deck_id)))


@api_v1.patch('/decks/<int:deck_id>')
@login_required
@validate_json(DeckPatch)
def update_deck(deck_id):
    """Change the sent fields (name, mode, visibility)."""
    data = request.validated_data
    changes = {name: getattr(data, name) for name in data.model_fields_set}
    return _guarded(lambda: _json(decks.update_deck(current_user, deck_id, changes)))


@api_v1.delete('/decks/<int:deck_id>')
@login_required
def delete_deck(deck_id):
    """Delete a deck and all its versions; answers with the deleted head."""
    return _guarded(lambda: _json({'deleted': decks.delete_deck(current_user, deck_id)}))


def _duplicate(deck_id, name=None):
    return _guarded(lambda: _json(decks.duplicate_deck(current_user, deck_id, name), 201))


@validate_json(DeckDuplicate)
def _duplicate_named(deck_id):
    return _duplicate(deck_id, request.validated_data.name)


@api_v1.post('/decks/<int:deck_id>/duplicate')
@login_required
def duplicate_deck(deck_id):
    """A new private deck with the current content and mode of this one (its own version 1).
    The body is optional: none means the default `<name> (copy)` name."""
    if not request.get_data():
        return _duplicate(deck_id)
    return _duplicate_named(deck_id)


@api_v1.put('/decks/<int:deck_id>/content')
@login_required
@validate_json(DeckContentPut)
def put_deck_content(deck_id):
    """Save the current version (autosave); hard limits are refused, soft rules are issues."""
    content = request.validated_data.content.model_dump()
    return _guarded(lambda: _json(decks.save_content(current_user, deck_id, content)))


@api_v1.get('/decks/<int:deck_id>/versions')
@login_required
def list_deck_versions(deck_id):
    """The deck's versions, newest first."""
    return _guarded(lambda: _json({'items': decks.list_versions(current_user, deck_id)}))


@api_v1.post('/decks/<int:deck_id>/versions')
@login_required
@validate_json(DeckVersionCreate)
def create_deck_version(deck_id):
    """Snapshot the current content as a new version, which becomes the current one."""
    note = request.validated_data.note
    return _guarded(lambda: _json(decks.snapshot(current_user, deck_id, note), 201))


@api_v1.get('/decks/<int:deck_id>/versions/<int:seq>')
@login_required
def get_deck_version(deck_id, seq):
    """One version with its cards and legality."""
    return _guarded(lambda: _json(decks.get_version(current_user, deck_id, seq)))


@api_v1.post('/decks/<int:deck_id>/versions/<int:seq>/restore')
@login_required
def restore_deck_version(deck_id, seq):
    """Copy version `seq` into a new version, which becomes the current one."""
    return _guarded(lambda: _json(decks.restore(current_user, deck_id, seq), 201))


@api_v1.post('/decks/import/preview')
@login_required
@validate_json(DeckImportPreview)
def preview_deck_import():
    """What a deck text would load (content, legality, per-line warnings); stores nothing."""
    data = request.validated_data
    return _guarded(lambda: _json(decks.import_preview(current_user, data.text, data.format)))


@api_v1.post('/decks/import')
@login_required
@validate_json(DeckImport)
def import_deck():
    """A new deck from a text; it loads even with warnings (hard limits included)."""
    data = request.validated_data
    return _guarded(lambda: _json(decks.import_deck(current_user, data.text, data.format,
                                                    data.name, data.mode), 201))


@api_v1.get('/decks/<int:deck_id>/export')
@login_required
@validate_query(DeckExportQuery)
def export_deck(deck_id):
    """The current version as a text file in the common deck format."""
    fmt = request.validated_query.format

    def download():
        filename, text = decks.export_text(current_user, deck_id, fmt)
        return current_app.response_class(
            text, mimetype='text/plain', headers={
                'Content-Disposition': f'attachment; filename="{filename}"'})
    return _guarded(download)


@api_v1.post('/decks/<int:deck_id>/share')
@login_required
def share_deck(deck_id):
    """The deck's read-only link `{slug, url}`; the same one while it is not revoked."""
    return _guarded(lambda: _json(deck_share.share(current_user, deck_id)))


@api_v1.delete('/decks/<int:deck_id>/share')
@login_required
def unshare_deck(deck_id):
    """Revoke the deck's link: its URL answers 404 from now on."""
    return _guarded(lambda: _json({'share': deck_share.unshare(current_user, deck_id)}))


@api_v1.get('/public/decks/<slug>')
@limiter.limit(PUBLIC_DECK_RATE_LIMIT)
def public_deck(slug):
    """The read-only deck behind a share link (P, no session). Never cached: a revoked link
    must stop answering at once. Unknown, revoked and malformed slugs get the same 404."""
    try:
        response = _json(deck_share.public_deck(slug))
    except DeckNotFound:
        response = http_error_response(NotFound())
    response.headers['Cache-Control'] = 'no-store'
    return response


@api_v1.get('/decks/<int:deck_id>/diff')
@login_required
@validate_query(DeckDiffQuery)
def diff_deck_versions(deck_id):
    """Per zone, what was added, removed or changed from version `a` to version `b`."""
    query = request.validated_query
    return _guarded(lambda: _json(decks.diff(current_user, deck_id, query.a, query.b)))


@api_v1.get('/decks/<int:deck_id>/vs-collection')
@login_required
def deck_vs_collection_view(deck_id):
    """The current version against the caller's collection: the missing copies per card name,
    the cost to complete it and the value already owned (F5-f)."""
    return _guarded(lambda: _json(deck_vs_collection.vs_collection(current_user, deck_id)))


def _missing_to_wishlist(deck_id, wishlist_id=None):
    return _guarded(lambda: _json(deck_vs_collection.missing_to_wishlist(
        current_user, deck_id, wishlist_id)))


@validate_json(DeckMissingToWishlist)
def _missing_to_chosen_wishlist(deck_id):
    return _missing_to_wishlist(deck_id, request.validated_data.wishlist_id)


@api_v1.post('/decks/<int:deck_id>/missing-to-wishlist')
@login_required
def missing_to_wishlist(deck_id):
    """Put the missing copies of the deck in a wishlist (`{wishlist_id?}`; none = the default
    list): one line per missing name raised to its missing count (F5-f)."""
    if not request.get_data():
        return _missing_to_wishlist(deck_id)
    return _missing_to_chosen_wishlist(deck_id)
