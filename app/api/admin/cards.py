"""Cards admin API (F13-b S6-S10): list, create, edit, image, delete with audit."""
import os

from flask import request

from app import db
from app.api.admin import api_admin
from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail, ok
from app.models.card import RbCard
from app.models.set import RbSet
from app.schemas.admin import AdminCardCreate, AdminCardPatch, AdminCardQuery
from app.schemas.validation import validate_json, validate_query
from app.services import audit as audit_service
from app.services import catalog_admin
from app.services.card_images import card_image_path

MAX_IMAGE_BYTES = 2_097_152

CARD_FIELDS = ('name', 'domain', 'type', 'tags', 'energy', 'power', 'might',
               'ability', 'rarity', 'artist', 'image', 'image_url')


def _unknown(what, set_id, card_id=None):
    target = f'{set_id}-{card_id}' if card_id else set_id
    return fail('Not Found', f'{what} {target!r} not found.', 404)


@api_admin.get('/cards')
@validate_query(AdminCardQuery)
def list_cards():
    """Filtered, sorted, paginated cards with `meta` (S6)."""
    params = request.validated_query
    items, total = catalog_admin.list_cards(params)
    pages = max((total + params.per_page - 1) // params.per_page, 1)
    return ok({'items': items,
               'meta': {'page': params.page, 'per_page': params.per_page,
                        'total': total, 'pages': pages}})


@api_admin.post('/cards')
@validate_json(AdminCardCreate)
def create_card():
    """Create a card; the set must exist (S7)."""
    data = request.validated_data
    if RbSet.query.get(data.set_id) is None:
        return fail('Validation Error', 'Invalid request data', 400,
                    details=[{'field': 'set_id', 'message': 'unknown set',
                              'type': 'value_error',
                              'code': DetailCode.INVALID_VALUE.value}],
                    code=ErrorCode.VALIDATION_ERROR)
    if RbCard.query.filter_by(rbcar_rbset_id=data.set_id,
                              rbcar_id=data.card_id).one_or_none() is not None:
        return fail('Conflict',
                    f"Card '{data.set_id}-{data.card_id}' already exists.", 409,
                    code=ErrorCode.ALREADY_EXISTS, params={'field': 'card_id'})
    card = RbCard(rbcar_rbset_id=data.set_id, rbcar_id=data.card_id)
    for field in CARD_FIELDS:
        setattr(card, _column(field), getattr(data, field))
    db.session.add(card)
    db.session.flush()
    audit_service.record('card.create', 'card', f'{card.rbcar_rbset_id}-{card.rbcar_id}',
                         {'name': card.rbcar_name})
    db.session.commit()
    return ok(catalog_admin.card_item(card), 201)


@api_admin.patch('/cards/<set_id>/<card_id>')
@validate_json(AdminCardPatch)
def update_card(set_id, card_id):
    """Edit a card; keys and `rbcar_banned` are refused by the schema (S8)."""
    card = RbCard.query.filter_by(rbcar_rbset_id=set_id, rbcar_id=card_id).one_or_none()
    if card is None:
        return _unknown('Card', set_id, card_id)
    data = request.validated_data
    changes = {}
    for field in CARD_FIELDS:
        new = getattr(data, field)
        if new is not None and new != getattr(card, _column(field)):
            changes[field] = [getattr(card, _column(field)), new]
            setattr(card, _column(field), new)
    if changes:
        audit_service.record('card.update', 'card', f'{set_id}-{card_id}', changes)
    db.session.commit()
    return ok(catalog_admin.card_item(card))


@api_admin.post('/cards/<set_id>/<card_id>/image')
def upload_card_image(set_id, card_id):
    """Replace the card image from multipart field `file` (S9)."""
    card = RbCard.query.filter_by(rbcar_rbset_id=set_id, rbcar_id=card_id).one_or_none()
    if card is None:
        return _unknown('Card', set_id, card_id)
    file = (request.files or {}).get('file')
    if file is None:
        return fail('Validation Error', 'Invalid request data', 400,
                    details=[{'field': 'file', 'message': 'file is required',
                              'type': 'missing', 'code': DetailCode.REQUIRED.value}],
                    code=ErrorCode.VALIDATION_ERROR)
    blob = file.read()
    if len(blob) > MAX_IMAGE_BYTES:
        return fail('Validation Error', 'Invalid request data', 400,
                    details=[{'field': 'file', 'message': 'file is too large',
                              'type': 'value_error',
                              'code': DetailCode.OUT_OF_RANGE.value,
                              'params': {'max': MAX_IMAGE_BYTES}}],
                    code=ErrorCode.VALIDATION_ERROR)
    ext = catalog_admin.detect_image_ext(blob[:12])
    if ext is None:
        return fail('Validation Error', 'Invalid request data', 400,
                    details=[{'field': 'file', 'message': 'unsupported image type',
                              'type': 'value_error',
                              'code': DetailCode.INVALID_FORMAT.value}],
                    code=ErrorCode.VALIDATION_ERROR)
    filename = f'{catalog_admin.image_stem(card)}.{ext}'
    dest = card_image_path(filename, card.rbcar_rbset_id)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, 'wb') as handle:
        handle.write(blob)
    card.image = filename
    audit_service.record('card.image', 'card', f'{set_id}-{card_id}',
                         {'image': filename, 'bytes': len(blob)})
    db.session.commit()
    return ok(catalog_admin.card_item(card))


@api_admin.delete('/cards/<set_id>/<card_id>')
def delete_card(set_id, card_id):
    """Delete a card only when nothing references it (S10); the image file stays."""
    card = RbCard.query.filter_by(rbcar_rbset_id=set_id, rbcar_id=card_id).one_or_none()
    if card is None:
        return _unknown('Card', set_id, card_id)
    lines, decks = catalog_admin.card_use_count(set_id, card_id)
    if lines or decks:
        return fail('Conflict',
                    f"Card '{set_id}-{card_id}' is used and cannot be deleted.", 409,
                    code=ErrorCode.CARD_IN_USE,
                    params={'collection_lines': lines, 'decks': decks})
    db.session.delete(card)
    audit_service.record('card.delete', 'card', f'{set_id}-{card_id}')
    db.session.commit()
    return ok({'deleted': f'{set_id}-{card_id}'})


def _column(field: str) -> str:
    """Admin field name to the `RbCard` column for the shared card attributes."""
    return {'name': 'rbcar_name', 'domain': 'rbcar_domain', 'type': 'rbcar_type',
            'tags': 'rbcar_tags', 'energy': 'rbcar_energy', 'power': 'rbcar_power',
            'might': 'rbcar_might', 'ability': 'rbcar_ability',
            'rarity': 'rbcar_rarity', 'artist': 'rbcar_artist'}.get(field, field)
