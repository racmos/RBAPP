"""Products admin API (F14-d S2-S4): list, kind/set locks and hidden, image, with audit.

The image upload goes through `app/services/image_upload.py` (F13-h S4, S5, S7, S8).
"""
from flask import request
from flask_login import current_user

from app import db
from app.api.admin import api_admin
from app.api.admin.cards import file_required, image_refused, read_upload
from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail, ok
from app.models.set import RbSet
from app.schemas.admin import AdminProductPatch, AdminProductQuery
from app.schemas.validation import validate_json, validate_query
from app.services import audit as audit_service
from app.services import image_upload, product_list
from app.services.products import apply_admin_patch


def _unknown(product_id):
    return fail('Not Found', f'Product {product_id} not found.', 404)


@api_admin.get('/products')
@validate_query(AdminProductQuery)
def list_products():
    """Filtered, sorted, paginated non-singles with `meta` (S2); hidden ones included."""
    params = request.validated_query
    items, total = product_list.list_admin_products(params, current_user.id)
    pages = max((total + params.per_page - 1) // params.per_page, 1)
    return ok({'items': items,
               'meta': {'page': params.page, 'per_page': params.per_page,
                        'total': total, 'pages': pages}})


@api_admin.patch('/products/<int:product_id>')
@validate_json(AdminProductPatch)
def update_product(product_id):
    """Hide, or set / unlock the kind and the set (S3); the refresh respects the locks."""
    product = product_list.admin_product(product_id)
    if product is None:
        return _unknown(product_id)
    data = request.validated_data
    fields = {name: getattr(data, name) for name in data.model_fields_set}
    set_id = fields.get('set_id')
    if set_id is not None and set_id != 'auto' and db.session.get(RbSet, set_id) is None:
        return fail('Validation Error', 'Invalid request data', 400,
                    details=[{'field': 'set_id', 'message': 'unknown set',
                              'type': 'value_error',
                              'code': DetailCode.INVALID_VALUE.value}],
                    code=ErrorCode.VALIDATION_ERROR)
    changes = apply_admin_patch(product, fields)
    if changes:
        audit_service.record('product.update', 'product', str(product_id), changes)
    db.session.commit()
    return ok(product_list.admin_item_for(product, current_user.id))


@api_admin.post('/products/<int:product_id>/image')
def upload_product_image(product_id):
    """Replace the product image from multipart field `file` (F14-d S4, F13-h S4-S8): resized
    WebP `<id>.webp` (`<id>-<n>.webp` when taken); the client file name is never used and the
    previous file is kept for the Undo."""
    product = product_list.admin_product(product_id)
    if product is None:
        return _unknown(product_id)
    blob = read_upload()
    if blob is None:
        return file_required()
    try:
        stored = image_upload.store_product_image(product, blob)
    except image_upload.ImageRejected as error:
        return image_refused(error)
    try:
        audit_service.record('product.image', 'product', str(product_id), stored.audit())
        db.session.commit()
    except BaseException:
        db.session.rollback()
        image_upload.remove_written('product', stored)
        raise
    image_upload.discard_product_family(product, keep={stored.image, stored.previous})
    item = product_list.admin_item_for(product, current_user.id)
    item.update(stored.payload())
    return ok(item)
