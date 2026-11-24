"""Missing printings (CM-m): the card groups with more Cardmarket products than catalog cards
and the creation of their signed printing (`<id>s`, owner answer 2026-11-24). Logic in
`app/services/missing_printings.py`; the creation is audited in the same transaction (one row
per call)."""
from flask import request

from app import db
from app.api.admin import api_admin
from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail, ok
from app.schemas.admin import AdminMissingPrintingsBody, AdminMissingPrintingsQuery
from app.schemas.validation import validate_json, validate_query
from app.services import audit as audit_service
from app.services import catalog_admin, missing_printings


@api_admin.get('/cardmarket/missing-printings')
@validate_query(AdminMissingPrintingsQuery)
def missing_printings_list():
    """Per set, the card groups with more products than free cards and their proposal."""
    return ok(missing_printings.plan())


@api_admin.post('/cardmarket/missing-printings')
@validate_json(AdminMissingPrintingsBody)
def missing_printings_create():
    """Create the chosen proposed cards in one transaction; Auto-match links them later."""
    items = [(one.set_id, one.card_id) for one in request.validated_data.items]
    try:
        result = missing_printings.create(items)
    except missing_printings.ItemsRefused as refused:
        db.session.rollback()
        return fail('Validation Error', refused.message, 400, details=[{
            'field': 'items', 'message': refused.message, 'type': 'value_error',
            'code': DetailCode.INVALID_VALUE.value, 'params': {'unknown': refused.unknown}}],
            code=ErrorCode.VALIDATION_ERROR)
    except catalog_admin.CardExists as exists:
        db.session.rollback()
        return fail('Conflict', f"Card '{exists}' already exists.", 409,
                    code=ErrorCode.ALREADY_EXISTS, params={'field': 'card_id'})
    audit = result.pop('audit')
    audit_service.record('cardmarket.missing_printings.create', 'cardmarket',
                         'missing_printings', audit)
    db.session.commit()
    return ok(result, 201 if result['created'] else 200)
