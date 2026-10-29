"""Products admin API (F14-d S2-S4): list, kind/set locks and hidden, image, with audit."""
import os

from flask import request
from flask_login import current_user

from app import db
from app.api.admin import api_admin
from app.api.admin.cards import MAX_IMAGE_BYTES
from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail, ok
from app.models.set import RbSet
from app.schemas.admin import AdminProductPatch, AdminProductQuery
from app.schemas.validation import validate_json, validate_query
from app.services import audit as audit_service
from app.services import catalog_admin, product_list
from app.services.card_images import is_plain_file_name
from app.services.product_images import product_image_path
from app.services.products import apply_admin_patch


def _unknown(product_id):
    return fail('Not Found', f'Product {product_id} not found.', 404)


def _file_error(message, type_, code, params=None):
    detail = {'field': 'file', 'message': message, 'type': type_, 'code': code.value}
    if params:
        detail['params'] = params
    return fail('Validation Error', 'Invalid request data', 400, details=[detail],
                code=ErrorCode.VALIDATION_ERROR)


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
    """Replace the product image from multipart field `file` (S4): `<id>.<ext>`, the
    extension from the magic bytes; the client file name is never used."""
    product = product_list.admin_product(product_id)
    if product is None:
        return _unknown(product_id)
    file = (request.files or {}).get('file')
    if file is None:
        return _file_error('file is required', 'missing', DetailCode.REQUIRED)
    blob = file.read()
    if len(blob) > MAX_IMAGE_BYTES:
        return _file_error('file is too large', 'value_error', DetailCode.OUT_OF_RANGE,
                           {'max': MAX_IMAGE_BYTES})
    ext = catalog_admin.detect_image_ext(blob[:12])
    if ext is None:
        return _file_error('unsupported image type', 'value_error', DetailCode.INVALID_FORMAT)
    filename = f'{product_id}.{ext}'
    dest = product_image_path(filename)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, 'wb') as handle:
        handle.write(blob)
    _remove_previous(product_id, product.rbpdt_image, filename)
    product.rbpdt_image = filename
    audit_service.record('product.image', 'product', str(product_id),
                         {'image': filename, 'bytes': len(blob)})
    db.session.commit()
    return ok(product_list.admin_item_for(product, current_user.id))


def _remove_previous(product_id, old, new):
    """Delete the product's previous `<id>.<other ext>` file; any other name is left alone."""
    if not old or old == new or not is_plain_file_name(old) \
            or os.path.splitext(old)[0] != str(product_id):
        return
    try:
        path = product_image_path(old)
    except ValueError:
        return
    if os.path.isfile(path):
        os.remove(path)
