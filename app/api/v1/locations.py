"""Storage locations endpoints (F16-b): the locations (CRUD, order, lock, suggested code) and
where the copies of one collection line are (GET/PUT /collection/<id>/locations, move)."""
from flask import abort, current_app, request
from flask_login import current_user, login_required

from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail
from app.api.v1 import api_v1
from app.schemas.validation import validate_json, validate_query
from app.schemas.validators import (LineLocationsMove, LineLocationsPut, LocationCodeQuery,
                                    LocationCreate, LocationOrder, LocationPatch)
from app.services import locations
from app.services.locations import (DuplicateCode, InvalidCode, InvalidDescription,
                                    InvalidOrder, LineNotFound, LocationLocked,
                                    LocationNotFound, LocationOverQuantity, NotEnoughCopies)


def _json(data, status=200, meta=None):
    """The success envelope with its key order kept (the item order is part of the shape)."""
    body = {'success': True, 'data': data}
    if meta is not None:
        body['meta'] = meta
    return current_app.response_class(
        current_app.json.dumps(body, sort_keys=False), status=status,
        mimetype='application/json')


def _invalid(field, message, code):
    return fail('Validation Error', 'Invalid request data', 400,
                details=[{'field': field, 'message': message, 'type': 'value_error',
                          'code': code.value}],
                code=ErrorCode.VALIDATION_ERROR)


def _over_quantity(max_qty, requested):
    return fail('Conflict', f'Too many copies: at most {max_qty} can be placed '
                f'(requested: {requested}).', 409, code=ErrorCode.LOCATION_OVER_QUANTITY,
                params={'max': max_qty, 'requested': requested})


def _guarded(action):
    """Run a call and turn the domain errors of `locations` into the API's error responses."""
    try:
        return action()
    except DuplicateCode:
        return fail('Conflict', 'A location with that code already exists.', 409,
                    code=ErrorCode.ALREADY_EXISTS)
    except InvalidCode:
        return _invalid('code', 'use 1-32 letters, digits and -', DetailCode.INVALID_FORMAT)
    except InvalidDescription:
        return _invalid('description', 'at most 200 characters', DetailCode.TOO_LONG)
    except InvalidOrder:
        return _invalid('ids', 'send every location id once', DetailCode.INVALID_VALUE)
    except LocationLocked:
        return fail('Conflict', 'This location is locked. Unlock it first.', 409,
                    code=ErrorCode.LOCATION_LOCKED)
    except LocationOverQuantity as exc:
        return _over_quantity(exc.available, exc.requested)
    except NotEnoughCopies as exc:
        return fail('Conflict', f'Not enough copies (available: {exc.available}).', 409,
                    code=ErrorCode.INSUFFICIENT_QUANTITY, params={'available': exc.available})
    except (LocationNotFound, LineNotFound):
        abort(404)


# --- locations -----------------------------------------------------------------------------

@api_v1.get('/locations')
@login_required
def list_locations():
    """The caller's locations in their order, and the copies that are in none."""
    return _json({'items': locations.location_items(current_user)},
                 meta={'unassigned_copies': locations.unassigned_total(current_user)})


@api_v1.post('/locations')
@login_required
@validate_json(LocationCreate)
def create_location():
    """A new location, last in the caller's order."""
    data = request.validated_data
    return _guarded(lambda: _json(locations.location_item(
        locations.create_location(current_user, data.code, data.description)), 201))


@api_v1.get('/locations/next-code')
@login_required
@validate_query(LocationCodeQuery)
def suggest_location_code():
    """The suggested code `B001-F001-P0001` after `after` or the caller's newest one."""
    query = request.validated_query
    return _json({'code': locations.suggest_next_code(current_user, query.after, query.bump)})


@api_v1.patch('/locations/<int:location_id>')
@login_required
@validate_json(LocationPatch)
def update_location(location_id):
    """Change the sent fields; a locked location can be renamed (only its quantities are
    read-only)."""
    data = request.validated_data
    sent = data.model_fields_set

    def action():
        changes = {name: getattr(data, name) for name in ('code', 'description') if name in sent}
        if changes or 'locked' not in sent:
            locations.update_location(current_user, location_id, **changes)
        if 'locked' in sent:
            locations.set_locked(current_user, location_id, data.locked)
        return _json(locations.owned_item(current_user, location_id))
    return _guarded(action)


@api_v1.delete('/locations/<int:location_id>')
@login_required
def delete_location(location_id):
    """Delete a location; its copies become unassigned. A locked deck location stays."""
    def action():
        item = locations.owned_item(current_user, location_id)
        locations.delete_location(current_user, location_id)
        return _json({'deleted': item})
    return _guarded(action)


@api_v1.put('/locations/order')
@login_required
@validate_json(LocationOrder)
def reorder_locations():
    """Set the whole order at once: every location id of the caller, each once."""
    def action():
        locations.reorder_locations(current_user, request.validated_data.ids)
        return _json({'items': locations.location_items(current_user)})
    return _guarded(action)


# --- copies of a line ----------------------------------------------------------------------

def _line_locations(line_id):
    found = locations.line_locations(current_user, line_id)
    found['total'] = found['unassigned'] + sum(row['qty'] for row in found['locations'])
    return _json(found)


@api_v1.get('/collection/<int:line_id>/locations')
@login_required
def get_line_locations(line_id):
    """Where the copies of one line are, in the caller's order, and how many are in none."""
    return _guarded(lambda: _line_locations(line_id))


@api_v1.put('/collection/<int:line_id>/locations')
@login_required
@validate_json(LineLocationsPut)
def put_line_locations(line_id):
    """Replace the line's assignment, all or nothing."""
    assignments = {row.location_id: row.qty for row in request.validated_data.assignments}

    def action():
        locations.set_line_locations(current_user, line_id, assignments)
        return _line_locations(line_id)
    return _guarded(action)


@api_v1.post('/collection/<int:line_id>/locations/move')
@login_required
@validate_json(LineLocationsMove)
def move_line_locations(line_id):
    """Move copies of a line between two locations; `null` is unassigned."""
    data = request.validated_data

    def action():
        if data.from_location_id is None:
            locations.assign_copies(current_user, line_id, data.to_location_id, data.qty)
        else:
            locations.move_copies(current_user, line_id, data.from_location_id,
                                  data.to_location_id, data.qty)
        return _line_locations(line_id)
    return _guarded(action)
