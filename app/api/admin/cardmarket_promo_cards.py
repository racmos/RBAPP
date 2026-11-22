"""Missing promo cards (CM-h): the promo sets, the plan of one set and the creation of its
missing promo cards as copies of their base cards. Logic in `app/services/promo_cards.py`;
the creation is audited in the same transaction (one row per call)."""
from flask import request

from app import db
from app.api.admin import api_admin
from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail, ok
from app.schemas.admin import AdminPromoCardsBody, AdminPromoCardsQuery
from app.schemas.validation import validate_json, validate_query
from app.services import audit as audit_service
from app.services import catalog_admin, promo_cards


def _refused(field, message, params=None):
    detail = {'field': field, 'message': message, 'type': 'value_error',
              'code': DetailCode.INVALID_VALUE.value}
    if params:
        detail['params'] = params
    return fail('Validation Error', message, 400, details=[detail],
                code=ErrorCode.VALIDATION_ERROR)


@api_admin.get('/cardmarket/promo-cards')
@validate_query(AdminPromoCardsQuery)
def promo_cards_list():
    """Without `set`: the promo sets with a mapped expansion. With `set`: its plan."""
    set_id = request.validated_query.set
    if set_id is None:
        return ok(promo_cards.promo_sets())
    try:
        return ok(promo_cards.plan(set_id))
    except promo_cards.SetRefused as refused:
        return _refused('set', refused.message)


@api_admin.post('/cardmarket/promo-cards')
@validate_json(AdminPromoCardsBody)
def promo_cards_create():
    """Create the missing promo cards of the chosen products in one transaction."""
    data = request.validated_data
    try:
        result = promo_cards.create(data.set_id, data.product_ids)
    except promo_cards.SetRefused as refused:
        db.session.rollback()
        return _refused('set_id', refused.message)
    except promo_cards.ProductsRefused as refused:
        db.session.rollback()
        return _refused('product_ids', refused.message,
                        {'unknown': refused.unknown, 'manual': refused.manual})
    except catalog_admin.CardExists as exists:
        db.session.rollback()
        return fail('Conflict', f"Card '{exists}' already exists.", 409,
                    code=ErrorCode.ALREADY_EXISTS, params={'field': 'card_id'})
    audit = result.pop('audit')
    audit_service.record('cardmarket.promo_cards.create', 'set', audit['set_id'], audit)
    db.session.commit()
    return ok(result, 201 if result['created'] else 200)
