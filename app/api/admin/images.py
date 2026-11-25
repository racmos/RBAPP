"""Images admin API (F13-h S1, S3, S7): counters of the Images screen, Undo of an upload and
the deletion of the previous file once the Undo expired.

The uploads themselves are `POST /admin/cards/<set>/<id>/image` and
`POST /admin/products/<id>/image`; the logic lives in `app/services/image_upload.py`.
"""
from flask import request
from flask_login import current_user

from app import db
from app.api.admin import api_admin
from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail, ok
from app.models.card import RbCard
from app.schemas.admin import (AdminImageFinalizeBody, AdminImagesSummaryQuery,
                               AdminImageUndoBody)
from app.schemas.validation import validate_json, validate_query
from app.services import audit as audit_service
from app.services import catalog_admin, image_upload, product_list
from app.services.card_images import cards_with_files, is_plain_file_name


def _invalid(field, message, code=DetailCode.INVALID_VALUE):
    return fail('Validation Error', 'Invalid request data', 400,
                details=[{'field': field, 'message': message, 'type': 'value_error',
                          'code': code.value}],
                code=ErrorCode.VALIDATION_ERROR)


@api_admin.get('/images/summary')
@validate_query(AdminImagesSummaryQuery)
def images_summary():
    """`{cards: {missing, total}, products: {missing, total}}` (S1)."""
    return ok(image_upload.summary())


@api_admin.post('/images/finalize')
@validate_json(AdminImageFinalizeBody)
def images_finalize():
    """Delete the previous file of an upload once its Undo expired (S7): only a regular file
    inside the images root that no row names. `{deleted}`."""
    data = request.validated_data
    if not is_plain_file_name(data.image):
        return _invalid('image', 'the image must be a plain file name',
                        DetailCode.INVALID_FORMAT)
    return ok({'deleted': image_upload.discard(data.type, data.image, data.set_id)})


@api_admin.post('/images/undo')
@validate_json(AdminImageUndoBody)
def images_undo():
    """Give a card or product its previous image back (S3); the replaced file is deleted when
    no row names it. 409 when the image changed meanwhile. Returns the item."""
    data = request.validated_data
    for field in ('image', 'previous'):
        value = getattr(data, field)
        if value is not None and not is_plain_file_name(value):
            return _invalid(field, 'the image must be a plain file name',
                            DetailCode.INVALID_FORMAT)
    if data.type == 'card':
        if not data.set_id or not data.card_id:
            return _invalid('card_id', 'set_id and card_id are required', DetailCode.REQUIRED)
        item = RbCard.query.filter_by(rbcar_rbset_id=data.set_id,
                                      rbcar_id=data.card_id).one_or_none()
        target = f'{data.set_id}-{data.card_id}'
        missing = fail('Not Found', f'Card {target!r} not found.', 404)
    else:
        if data.product_id is None:
            return _invalid('product_id', 'product_id is required', DetailCode.REQUIRED)
        item = product_list.admin_product(data.product_id)
        target = str(data.product_id)
        missing = fail('Not Found', f'Product {data.product_id} not found.', 404)
    if item is None:
        return missing
    try:
        replaced = image_upload.undo(item, data.type, data.image, data.previous)
    except image_upload.UndoStale:
        return fail('Conflict', 'The image changed meanwhile; reload the list.', 409)
    audit_service.record(f'{data.type}.image_undo', data.type, target,
                         {'image': data.previous or None, 'replaced': replaced})
    db.session.commit()
    if data.type == 'card':
        image_upload.discard('card', replaced, item.rbcar_rbset_id)
        has_image, = cards_with_files([(item.image, item.rbcar_rbset_id)])
        return ok(catalog_admin.card_item(item, has_image))
    image_upload.discard('product', replaced)
    return ok(product_list.admin_item_for(item, current_user.id))
