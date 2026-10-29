"""Owned products endpoints (F14-c): GET/POST /me/products, PATCH/DELETE /me/products/<id>."""
from flask import abort, current_app, request
from flask_login import current_user, login_required

from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail
from app.api.v1 import api_v1
from app.schemas.validation import validate_json
from app.schemas.validators import UserProductCreate, UserProductPatch
from app.services import user_products
from app.services.user_products import LineNotFound, QuantityTooHigh, UnknownProduct


def _json(data, status=200):
    """The success envelope with its key order kept (`ProductSummary` order is a contract)."""
    return current_app.response_class(
        current_app.json.dumps({'success': True, 'data': data}, sort_keys=False),
        status=status, mimetype='application/json',
    )


def _invalid(field, message, code, params=None):
    detail = {'field': field, 'message': message, 'type': 'value_error', 'code': code.value}
    if params:
        detail['params'] = params
    return fail('Validation Error', 'Invalid request data', 400, details=[detail],
                code=ErrorCode.VALIDATION_ERROR)


def _guarded(action):
    """Run a write and turn its domain errors into the API's error responses."""
    try:
        return action()
    except UnknownProduct:
        return _invalid('product_id', 'unknown product', DetailCode.INVALID_VALUE)
    except QuantityTooHigh:
        return _invalid('quantity', f'at most {user_products.MAX_QUANTITY} in one line',
                        DetailCode.OUT_OF_RANGE, {'max': user_products.MAX_QUANTITY})
    except LineNotFound:
        abort(404)


@api_v1.get('/me/products')
@login_required
def list_my_products():
    """The caller's product lines and their total (never part of the collection value)."""
    return _json(user_products.list_lines(current_user))


@api_v1.post('/me/products')
@login_required
@validate_json(UserProductCreate)
def create_my_product():
    """Add copies of a product; a line with the same purchase price is merged into."""
    def action():
        line, merged = user_products.add_line(current_user, request.validated_data)
        return _json({'line': line, 'merged': merged}, 201)
    return _guarded(action)


@api_v1.patch('/me/products/<int:line_id>')
@login_required
@validate_json(UserProductPatch)
def update_my_product(line_id):
    """Change the sent fields of one line."""
    return _guarded(lambda: _json(user_products.edit_line(
        current_user, line_id, request.validated_data)))


@api_v1.delete('/me/products/<int:line_id>')
@login_required
def delete_my_product(line_id):
    """Delete one line; the answer can be posted back to undo."""
    return _guarded(lambda: _json({'deleted': user_products.delete_line(current_user, line_id)}))
