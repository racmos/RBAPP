"""Decks v2 endpoints (F5-d): GET/POST /decks, GET/PATCH/DELETE /decks/<id>,
PUT /decks/<id>/content, versions, restore and diff. Only the owner sees a deck (D-F5-9)."""
from flask import abort, current_app, request
from flask_login import current_user, login_required

from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail
from app.api.v1 import api_v1
from app.schemas.validation import validate_json, validate_query
from app.schemas.validators import (DeckContentPut, DeckCreate, DeckDiffQuery, DeckPatch,
                                    DeckVersionCreate)
from app.services import decks
from app.services.decks import (DeckNotFound, DuplicateName, HardLimitExceeded, UnknownCards,
                                VersionNotFound)


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
    except (DeckNotFound, VersionNotFound):
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


@api_v1.get('/decks/<int:deck_id>/diff')
@login_required
@validate_query(DeckDiffQuery)
def diff_deck_versions(deck_id):
    """Per zone, what was added, removed or changed from version `a` to version `b`."""
    query = request.validated_query
    return _guarded(lambda: _json(decks.diff(current_user, deck_id, query.a, query.b)))
