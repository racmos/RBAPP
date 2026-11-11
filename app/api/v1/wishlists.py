"""Wishlists endpoints (F3-f-2): the caller's lists (CRUD, default star, order) and their
lines (add with merge, edit, delete, move or copy), with the owned and price indicators of
each line. Logic in `app/services/wishlists.py`; another user's list or line is a 404."""
from flask import abort, current_app, request
from flask_login import current_user, login_required

from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail
from app.api.v1 import api_v1
from app.schemas.validation import validate_json, validate_query
from app.schemas.validators import (WishlistCreate, WishlistLineCreate, WishlistLinesMove,
                                    WishlistLinesQuery, WishlistLineUpdate, WishlistOrder,
                                    WishlistUpdate)
from app.services import wishlists
from app.services.wishlists import (DefaultList, DefaultRequired, DuplicateLine, DuplicateName,
                                    FoilNotAllowed, InvalidOrder, LineNotFound, ListNotFound,
                                    SameList, UnknownCard, WishlistLimit)

_LIMIT_MESSAGES = {'lists': 'You can have at most {max} wishlists.',
                   'lines': 'A wishlist can hold at most {max} cards.'}


def _json(data, status=200, meta=None):
    """The success envelope with its key order kept (the shapes are contracts)."""
    body = {'success': True, 'data': data}
    if meta is not None:
        body['meta'] = meta
    return current_app.response_class(
        current_app.json.dumps(body, sort_keys=False), status=status,
        mimetype='application/json')


def _invalid(field, message, code=DetailCode.INVALID_VALUE):
    return fail('Validation Error', 'Invalid request data', 400,
                details=[{'field': field, 'message': message, 'type': 'value_error',
                          'code': code.value}],
                code=ErrorCode.VALIDATION_ERROR)


def _guarded(action):
    """Run a call and turn the domain errors of `wishlists` into the API's error responses."""
    try:
        return action()
    except DuplicateName:
        return fail('Conflict', 'A wishlist with that name already exists.', 409,
                    code=ErrorCode.ALREADY_EXISTS)
    except DuplicateLine:
        return fail('Conflict', 'The list already has this card with that foil.', 409,
                    code=ErrorCode.ALREADY_EXISTS)
    except WishlistLimit as exc:
        return fail('Conflict', _LIMIT_MESSAGES[exc.scope].format(max=exc.max), 409,
                    code=ErrorCode.WISHLIST_LIMIT, params={'scope': exc.scope, 'max': exc.max})
    except DefaultList:
        return fail('Conflict', 'The default list cannot be deleted. Star another list first.',
                    409, code=ErrorCode.WISHLIST_DEFAULT)
    except DefaultRequired:
        return _invalid('is_default', 'there must be a default list: star another list instead')
    except InvalidOrder:
        return _invalid('ids', 'send every wishlist id once')
    except SameList:
        return _invalid('to_list_id', 'choose another list')
    except UnknownCard as exc:
        return _invalid(exc.field, 'unknown card')
    except FoilNotAllowed:
        return fail('Bad Request', 'This card has no foil version.', 400,
                    code=ErrorCode.FOIL_NOT_ALLOWED)
    except (ListNotFound, LineNotFound):
        abort(404)


# --- lists ---------------------------------------------------------------------------------

@api_v1.get('/wishlists')
@login_required
def list_wishlists():
    """The caller's lists in order; the first call creates the default list "Wishlist"."""
    return _json({'items': wishlists.list_items(current_user)})


@api_v1.post('/wishlists')
@login_required
@validate_json(WishlistCreate)
def create_wishlist():
    """A new list, last in the caller's order (at most 20)."""
    def action():
        created = wishlists.create_list(current_user, request.validated_data.name)
        return _json(wishlists.list_item(created), 201)
    return _guarded(action)


@api_v1.patch('/wishlists/<int:list_id>')
@login_required
@validate_json(WishlistUpdate)
def update_wishlist(list_id):
    """Rename and/or star a list (`is_default: true`; the previous default is unstarred)."""
    data = request.validated_data
    changes = {name: getattr(data, name) for name in ('name', 'is_default')
               if name in data.model_fields_set}

    def action():
        wishlists.update_list(current_user, list_id, **changes)
        return _json(wishlists.owned_item(current_user, list_id))
    return _guarded(action)


@api_v1.delete('/wishlists/<int:list_id>')
@login_required
def delete_wishlist(list_id):
    """Delete a list that is not the default, with its lines; returns both."""
    def action():
        item, lines = wishlists.delete_list(current_user, list_id)
        return _json({'deleted': item, 'lines': lines})
    return _guarded(action)


@api_v1.put('/wishlists/order')
@login_required
@validate_json(WishlistOrder)
def reorder_wishlists():
    """Set the whole order at once: every list id of the caller, each once."""
    def action():
        wishlists.reorder_lists(current_user, request.validated_data.ids)
        return _json({'items': wishlists.list_items(current_user)})
    return _guarded(action)


# --- lines ---------------------------------------------------------------------------------

@api_v1.get('/wishlists/<int:list_id>/lines')
@login_required
@validate_query(WishlistLinesQuery)
def list_wishlist_lines(list_id):
    """The lines of one list with their indicators, in the order they were added."""
    def action():
        found = wishlists.list_lines(current_user, list_id, request.validated_query.q)
        return _json({'items': found['items']}, meta=found['meta'])
    return _guarded(action)


@api_v1.post('/wishlists/<int:list_id>/lines')
@login_required
@validate_json(WishlistLineCreate)
def create_wishlist_line(list_id):
    """Add a card: 201 with the new line, or 200 when it merged into the same target."""
    data = request.validated_data
    printing = data.set_id is not None

    def action():
        line, merged = wishlists.add_line(
            current_user, list_id, set_id=data.set_id, card_id=data.card_id,
            name=None if printing else data.name, foil=data.foil, qty=data.qty,
            max_price=data.max_price, note=data.note)
        return _json({'line': line, 'merged': merged}, 200 if merged else 201)
    return _guarded(action)


@api_v1.patch('/wishlists/<int:list_id>/lines/<int:line_id>')
@login_required
@validate_json(WishlistLineUpdate)
def update_wishlist_line(list_id, line_id):
    """Change the sent fields of a line; `null` clears the max price or the note."""
    data = request.validated_data
    changes = {name: getattr(data, name) for name in ('qty', 'foil', 'max_price', 'note')
               if name in data.model_fields_set}
    return _guarded(lambda: _json(wishlists.update_line(current_user, list_id, line_id,
                                                        **changes)))


@api_v1.delete('/wishlists/<int:list_id>/lines/<int:line_id>')
@login_required
def delete_wishlist_line(list_id, line_id):
    """Delete a line; the answer can be posted back to undo."""
    return _guarded(lambda: _json({'deleted': wishlists.delete_line(current_user, list_id,
                                                                    line_id)}))


@api_v1.post('/wishlists/<int:list_id>/lines/move')
@login_required
@validate_json(WishlistLinesMove)
def move_wishlist_lines(list_id):
    """Move or copy lines to another list of the caller, all or nothing."""
    data = request.validated_data
    return _guarded(lambda: _json(wishlists.move_lines(
        current_user, list_id, data.line_ids, data.to_list_id, data.mode)))
