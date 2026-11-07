"""Cardmarket expansions (CM-d): the list, map an expansion to a set of ours (creating the
set, as `POST /admin/sets` does, in the same transaction) and unmap it. Logic in
`app/services/cardmarket_expansions.py`; every write is audited in the same transaction."""
from flask import request
from pydantic import ValidationError

from app import db
from app.api.admin import api_admin
from app.api.admin.sets import add_set
from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail, ok
from app.models.set import RbSet
from app.schemas.admin import AdminExpansionMapBody, AdminExpansionsQuery, AdminSetCreate
from app.schemas.validation import detail_code, validate_json, validate_query
from app.services import audit as audit_service
from app.services import catalog_admin
from app.services import cardmarket_expansions as expansions

TARGET = 'cardmarket_expansion'


def _not_found(expansion_id):
    return fail('Not Found', f'Cardmarket expansion {expansion_id} not found.', 404)


def _validation(details):
    return fail('Validation Error', 'Invalid request data', 400, details=details,
                code=ErrorCode.VALIDATION_ERROR)


def _set_errors(error: ValidationError) -> list[dict]:
    """The `AdminSetCreate` errors of a new set, named after the body (`id` is `set_id`)."""
    details = []
    for item in error.errors():
        loc = [str(part) for part in item['loc']]
        field = 'set_id' if loc == ['id'] else '.'.join(['create_set', *loc])
        code, params = detail_code(item)
        detail = {'field': field, 'message': item['msg'], 'type': item['type'], 'code': code}
        if params:
            detail['params'] = params
        details.append(detail)
    return details


@api_admin.get('/cardmarket/expansions')
@validate_query(AdminExpansionsQuery)
def list_expansions():
    """Every Cardmarket expansion, unmapped first, and the sets they can be mapped to."""
    return ok(expansions.list_expansions(request.validated_query.unmapped))


@api_admin.put('/cardmarket/expansions/<int:expansion_id>')
@validate_json(AdminExpansionMapBody)
def map_expansion(expansion_id):
    """Map (or re-map) an expansion to a set; `create_set` creates the set first."""
    data = request.validated_data
    try:
        expansion = expansions.get(expansion_id)
    except expansions.NotFound:
        return _not_found(expansion_id)
    new_set = None
    if data.create_set is not None:
        try:
            new_set = AdminSetCreate(id=data.set_id, **data.create_set.model_dump())
        except ValidationError as error:
            return _validation(_set_errors(error))
        if db.session.get(RbSet, new_set.id) is not None:
            return fail('Conflict', f"Set '{new_set.id}' already exists.", 409,
                        code=ErrorCode.ALREADY_EXISTS, params={'field': 'set_id'})
        set_id = new_set.id
    else:
        set_id = data.set_id
        if db.session.get(RbSet, set_id) is None:
            return _validation([{'field': 'set_id', 'message': 'unknown set',
                                 'type': 'value_error',
                                 'code': DetailCode.INVALID_VALUE.value}])
    try:
        created = None
        if new_set is not None:
            created = catalog_admin.set_item(add_set(new_set), 0)
        previous = expansions.map_to(expansion, set_id)
        if previous != set_id:
            audit_service.record('cardmarket.expansion.map', TARGET, str(expansion_id),
                                 {'name': expansion.rbexp_name, 'set_id': set_id,
                                  'previous': previous})
        item = expansions.expansion_item(expansion_id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return ok({'expansion': item, 'previous': previous, 'created_set': created})


@api_admin.delete('/cardmarket/expansions/<int:expansion_id>/mapping')
def unmap_expansion(expansion_id):
    """Unmap; the previous set id comes back so the client can undo."""
    try:
        expansion, previous = expansions.unmap(expansion_id)
    except expansions.NotFound:
        return _not_found(expansion_id)
    except expansions.NotMapped:
        return fail('Not Found', f'Cardmarket expansion {expansion_id} is not mapped.', 404)
    audit_service.record('cardmarket.expansion.unmap', TARGET, str(expansion_id),
                         {'name': expansion.rbexp_name, 'previous': previous})
    item = expansions.expansion_item(expansion_id)
    db.session.commit()
    return ok({'expansion': item, 'previous': previous})
