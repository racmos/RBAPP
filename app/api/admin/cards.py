"""Cards admin API (F13-b S6-S10): list, create, edit, image, delete with audit.

The image upload goes through `app/services/image_upload.py` (F13-h S4, S5, S7, S8).
"""
from flask import request
from werkzeug.datastructures import FileStorage

from app import db
from app.api.admin import api_admin
from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail, ok
from app.models.card import RbCard
from app.schemas.admin import AdminCardCreate, AdminCardPatch, AdminCardQuery
from app.schemas.validation import validate_json, validate_query
from app.services import audit as audit_service
from app.services import catalog_admin, image_upload

CARD_FIELDS = catalog_admin.CARD_FIELDS


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
    try:
        card, = catalog_admin.create_cards([data])
    except catalog_admin.UnknownSet:
        return fail('Validation Error', 'Invalid request data', 400,
                    details=[{'field': 'set_id', 'message': 'unknown set',
                              'type': 'value_error',
                              'code': DetailCode.INVALID_VALUE.value}],
                    code=ErrorCode.VALIDATION_ERROR)
    except catalog_admin.CardExists:
        return fail('Conflict',
                    f"Card '{data.set_id}-{data.card_id}' already exists.", 409,
                    code=ErrorCode.ALREADY_EXISTS, params={'field': 'card_id'})
    audit_service.record('card.create', 'card', f'{card.rbcar_rbset_id}-{card.rbcar_id}',
                         {'name': card.rbcar_name})
    db.session.commit()
    return ok(catalog_admin.card_item(card), 201)


@api_admin.patch('/cards/<set_id>/<card_id>')
@validate_json(AdminCardPatch)
def update_card(set_id, card_id):
    """Edit a card; keys and unknown fields are refused by the schema (S8)."""
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


def file_required():
    """The 400 of an upload without the multipart part `file`."""
    return fail('Validation Error', 'Invalid request data', 400,
                details=[{'field': 'file', 'message': 'file is required',
                          'type': 'missing', 'code': DetailCode.REQUIRED.value}],
                code=ErrorCode.VALIDATION_ERROR)


def image_refused(error: image_upload.ImageRejected):
    """The 400 of a refused image (F13-h S4): one `details[]` item on the field `file`."""
    return fail('Validation Error', 'Invalid request data', 400, details=[error.detail],
                code=ErrorCode.VALIDATION_ERROR)


def read_upload():
    """The bytes of the part `file` (at most the limit + 1, enough to refuse a bigger one),
    or None when the part is missing."""
    file = (request.files or {}).get('file')
    if not isinstance(file, FileStorage):
        return None
    return file.stream.read(image_upload.MAX_FILE_BYTES + 1)


@api_admin.post('/cards/<set_id>/<card_id>/image')
def upload_card_image(set_id, card_id):
    """Replace the card image from multipart field `file` (F13-b S9, F13-h S4-S8): resized
    WebP `<set>_<id>.webp` (`-<n>` when taken); the previous file is kept for the Undo."""
    card = RbCard.query.filter_by(rbcar_rbset_id=set_id, rbcar_id=card_id).one_or_none()
    if card is None:
        return _unknown('Card', set_id, card_id)
    blob = read_upload()
    if blob is None:
        return file_required()
    try:
        stored = image_upload.store_card_image(card, blob)
    except image_upload.ImageRejected as error:
        return image_refused(error)
    try:
        audit_service.record('card.image', 'card', f'{set_id}-{card_id}', stored.audit())
        db.session.commit()
    except BaseException:
        db.session.rollback()
        image_upload.remove_written('card', stored, set_id)
        raise
    image_upload.discard_card_family(card, keep={stored.image, stored.previous})
    item = catalog_admin.card_item(card, has_image=True)
    item.update(stored.payload())
    return ok(item)


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
    return catalog_admin.card_column(field)
