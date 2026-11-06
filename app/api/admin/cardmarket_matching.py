"""Cardmarket matching workbench (CM-b): unmatched products, candidates, link / unlink /
relink, the links browser, the ignore list, auto-match preview / apply and the review
list. Logic in `app/services/cardmarket_matching.py`; every write is audited in the
same transaction."""
from flask import request

from app import db
from app.api.admin import api_admin
from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail, ok
from app.schemas.admin import (AdminAutoMatchApplyBody, AdminCandidatesQuery, AdminIgnoreBody,
                               AdminLinkBody, AdminLinksQuery, AdminRelinkBody,
                               AdminReviewQuery, AdminUnignoreQuery, AdminUnmatchedQuery)
from app.schemas.validation import validate_json, validate_query
from app.services import audit as audit_service
from app.services import cardmarket_matching as matching

TARGET = 'cardmarket_product'
PRODUCT_LINK = ('products are linked by Cardmarket id: products_refresh creates the '
                'product of each non-single; a missing product is created from the item')


def _invalid(field, message):
    return fail('Validation Error', 'Invalid request data', 400,
                details=[{'field': field, 'message': message, 'type': 'value_error',
                          'code': DetailCode.INVALID_VALUE.value}],
                code=ErrorCode.VALIDATION_ERROR)


def _target(data):
    """`(set_id, card_id)` of a link body, or the 400 response."""
    if data.kind == 'product':
        return None, _invalid('kind', PRODUCT_LINK)
    if data.card is None:
        return None, fail('Validation Error', 'Invalid request data', 400,
                          details=[{'field': 'card', 'message': 'card is required',
                                    'type': 'missing', 'code': DetailCode.REQUIRED.value}],
                          code=ErrorCode.VALIDATION_ERROR)
    return (data.card.set_id, data.card.card_id), None


def _conflict(error):
    return fail('Conflict', error.message, 409, code=ErrorCode.ALREADY_EXISTS,
                params=error.params)


def _no_link(id_product):
    return fail('Not Found', f'Cardmarket product {id_product} has no link.', 404)


def _slot(set_id, card_id, foil):
    return {'set_id': set_id, 'card_id': card_id, 'foil': foil}


def _pages(total, per_page):
    return max((total + per_page - 1) // per_page, 1)


@api_admin.get('/cardmarket/unmatched')
@validate_query(AdminUnmatchedQuery)
def list_unmatched():
    """Unmatched products of the latest load with up to three suggestions."""
    params = request.validated_query
    items, total, date = matching.list_unmatched(params)
    return ok({'items': items,
               'meta': {'page': params.page, 'per_page': params.per_page, 'total': total,
                        'pages': _pages(total, params.per_page), 'date': date}})


@api_admin.get('/cardmarket/unmatched/<int:id_product>/candidates')
@validate_query(AdminCandidatesQuery)
def unmatched_candidates(id_product):
    """Cards (and products for a non-single) a Cardmarket product can be linked to."""
    found = matching.candidates(id_product, request.validated_query.q)
    if found is None:
        return fail('Not Found', f'Cardmarket product {id_product} not found.', 404)
    return ok(found)


@api_admin.get('/cardmarket/links')
@validate_query(AdminLinksQuery)
def list_links():
    """The links browser; `conflicts=true` keeps the slots held by several products."""
    params = request.validated_query
    items, total, conflict_slots = matching.list_links(params)
    return ok({'items': items,
               'meta': {'page': params.page, 'per_page': params.per_page, 'total': total,
                        'pages': _pages(total, params.per_page),
                        'conflict_slots': conflict_slots}})


@api_admin.post('/cardmarket/links')
@validate_json(AdminLinkBody)
def create_link():
    """Link a Cardmarket product to a card slot; 409 when linked or the slot is taken."""
    data = request.validated_data
    target, error = _target(data)
    if error:
        return error
    set_id, card_id = target
    try:
        link = matching.link(data.id_product, set_id, card_id, data.foil)
    except matching.NotFound:
        return fail('Not Found', f'Cardmarket product {data.id_product} not found.', 404)
    except matching.UnknownCard:
        return _invalid('card', 'unknown card')
    except matching.LinkConflict as conflict:
        return _conflict(conflict)
    audit_service.record('cardmarket.link', TARGET, str(data.id_product),
                         _slot(set_id, card_id, data.foil))
    db.session.commit()
    return ok(matching.link_item(link), 201)


@api_admin.put('/cardmarket/links/<int:id_product>')
@validate_json(AdminRelinkBody)
def relink(id_product):
    """Move a link to another card slot in one transaction: all or nothing."""
    data = request.validated_data
    target, error = _target(data)
    if error:
        return error
    set_id, card_id = target
    try:
        previous, link = matching.relink(id_product, set_id, card_id, data.foil)
        audit_service.record('cardmarket.relink', TARGET, str(id_product), {
            'from': _slot(previous['set_id'], previous['card_id'], previous['foil']),
            'to': _slot(set_id, card_id, data.foil)})
        item = matching.link_item(link)
        db.session.commit()
    except matching.NotFound:
        db.session.rollback()
        return _no_link(id_product)
    except matching.UnknownCard:
        db.session.rollback()
        return _invalid('card', 'unknown card')
    except matching.LinkConflict as conflict:
        db.session.rollback()
        return _conflict(conflict)
    except Exception:
        db.session.rollback()
        raise
    return ok({'link': item, 'previous': previous})


@api_admin.delete('/cardmarket/links/<int:id_product>')
def delete_link(id_product):
    """Unlink; the removed link comes back so the client can undo."""
    try:
        removed = matching.unlink(id_product)
    except matching.NotFound:
        return _no_link(id_product)
    details = _slot(removed['set_id'], removed['card_id'], removed['foil'])
    details['match_type'] = removed['match_type']
    audit_service.record('cardmarket.unlink', TARGET, str(id_product), details)
    db.session.commit()
    return ok({'link': removed})


@api_admin.get('/cardmarket/ignored')
def list_ignored():
    """The ignore list, newest first."""
    return ok({'items': matching.list_ignored()})


@api_admin.post('/cardmarket/ignored')
@validate_json(AdminIgnoreBody)
def add_ignored():
    """Ignore `(id, name)`; idempotent (200 when it was already there)."""
    data = request.validated_data
    item, created = matching.ignore(data.id_product, data.name)
    if created:
        audit_service.record('cardmarket.ignore', TARGET, str(data.id_product),
                             {'name': data.name})
    db.session.commit()
    return ok({'item': item, 'created': created}, 201 if created else 200)


@api_admin.delete('/cardmarket/ignored/<int:id_product>')
@validate_query(AdminUnignoreQuery)
def restore_ignored(id_product):
    """Restore one ignored name (`?name=`) or every name of the id."""
    removed = matching.unignore(id_product, request.validated_query.name)
    if not removed:
        db.session.rollback()
        return fail('Not Found', f'Cardmarket product {id_product} is not ignored.', 404)
    audit_service.record('cardmarket.unignore', TARGET, str(id_product),
                         {'names': [row['name'] for row in removed]})
    db.session.commit()
    return ok({'removed': removed})


@api_admin.post('/cardmarket/auto-match/preview')
def auto_match_preview():
    """Clear and doubtful cases of the latest load; writes nothing."""
    return ok(matching.preview())


@api_admin.post('/cardmarket/auto-match/apply')
@validate_json(AdminAutoMatchApplyBody)
def auto_match_apply():
    """Link the clear cases (at most `max_groups`), synchronously."""
    max_groups = request.validated_data.max_groups
    result = matching.apply(max_groups)
    if result['date'] is not None:
        audit_service.record('cardmarket.auto_match', 'cardmarket',
                             result['date'], {'linked': result['linked'],
                                              'clear': result['clear'],
                                              'doubtful': result['doubtful'],
                                              'max_groups': max_groups})
    db.session.commit()
    return ok(result)


@api_admin.get('/cardmarket/review')
@validate_query(AdminReviewQuery)
def review_list():
    """The doubtful cases of the latest load, computed now."""
    items, meta = matching.review(request.validated_query)
    return ok({'items': items, 'meta': meta})
