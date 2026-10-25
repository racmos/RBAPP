"""Sets admin API (F13-b S2-S5): list, create, edit, delete with audit."""
from flask import request

from app import db
from app.api.admin import api_admin
from app.api.error_codes import ErrorCode
from app.api.responses import fail, ok
from app.models.set import RbSet
from app.schemas.admin import AdminSetCreate, AdminSetPatch
from app.schemas.validation import validate_json
from app.services import audit as audit_service
from app.services import catalog_admin


@api_admin.get('/sets')
def list_sets():
    """Every set with counts (S2)."""
    return ok(catalog_admin.list_sets())


@api_admin.post('/sets')
@validate_json(AdminSetCreate)
def create_set():
    """Create a set; the id is upper-cased by the schema (S3)."""
    data = request.validated_data
    if RbSet.query.get(data.id) is not None:
        return fail('Conflict', f"Set '{data.id}' already exists.", 409,
                    code=ErrorCode.ALREADY_EXISTS, params={'field': 'id'})
    rs = RbSet(rbset_id=data.id, rbset_name=data.name,
               rbset_ncard=data.declared_count, rbset_outdat=data.release_date)
    db.session.add(rs)
    db.session.flush()
    audit_service.record('set.create', 'set', rs.rbset_id,
                         {'name': rs.rbset_name,
                          'release_date': rs.rbset_outdat.isoformat()})
    db.session.commit()
    return ok(catalog_admin.set_item(rs, 0), 201)


@api_admin.patch('/sets/<set_id>')
@validate_json(AdminSetPatch)
def update_set(set_id):
    """Edit a set; an explicit null release date is refused (S4)."""
    rs = RbSet.query.get(set_id)
    if rs is None:
        return fail('Not Found', f"Set '{set_id}' not found.", 404)
    data = request.validated_data
    raw = request.get_json(silent=True) or {}
    if 'release_date' in raw and raw['release_date'] is None:
        return fail('Validation Error', 'Invalid request data', 400,
                    details=[{'field': 'release_date',
                              'message': 'release_date is required',
                              'type': 'missing',
                              'code': 'required'}],
                    code=ErrorCode.VALIDATION_ERROR)
    cards = catalog_admin.set_card_count(set_id)
    if data.id is not None and data.id != set_id:
        if cards:
            return fail('Conflict',
                        f"Set '{set_id}' has {cards} cards; its code cannot be changed.", 409,
                        code=ErrorCode.SET_IN_USE, params={'cards': cards})
        if RbSet.query.get(data.id) is not None:
            return fail('Conflict', f"Set '{data.id}' already exists.", 409,
                        code=ErrorCode.ALREADY_EXISTS, params={'field': 'id'})
    changes = catalog_admin.apply_set_patch(rs, data)
    if data.id is not None and data.id != set_id:
        rs.rbset_id = data.id
        changes = {'id': [set_id, data.id], **changes}
    if changes:
        audit_service.record('set.update', 'set', rs.rbset_id, changes)
    db.session.commit()
    return ok(catalog_admin.set_item(rs, catalog_admin.set_card_count(rs.rbset_id)))


@api_admin.delete('/sets/<set_id>')
def delete_set(set_id):
    """Delete a set only when it has no cards (S5)."""
    rs = RbSet.query.get(set_id)
    if rs is None:
        return fail('Not Found', f"Set '{set_id}' not found.", 404)
    cards = catalog_admin.set_card_count(set_id)
    if cards:
        return fail('Conflict',
                    f"Set '{set_id}' has {cards} cards; it cannot be deleted.", 409,
                    code=ErrorCode.SET_IN_USE, params={'cards': cards})
    db.session.delete(rs)
    audit_service.record('set.delete', 'set', set_id)
    db.session.commit()
    return ok({'deleted': set_id})
