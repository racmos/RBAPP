"""Product endpoints (F14-b): GET /products, /products/<id> and /products/<id>/prices.

F14-c: answers are per caller (`owned_qty`, the `owned` filter, their hidden products and
the detail `lines`)."""
from flask import abort, current_app, request
from flask_login import current_user, login_required

from app.api.v1 import api_v1
from app.schemas.validation import validate_query
from app.schemas.validators import ProductListQuery, ProductPricesQuery
from app.services import product_list


def _json(body):
    """The body with its key order kept (`ProductSummary` order is part of the contract)."""
    return current_app.response_class(
        current_app.json.dumps(body, sort_keys=False),
        mimetype='application/json',
    )


@api_v1.get('/products')
@login_required
@validate_query(ProductListQuery)
def list_products():
    """Paginated sealed products with filters, facets and sorting."""
    result = product_list.list_products(request.validated_query, current_user.id)
    return _json({'success': True, 'data': {'items': result['items']}, 'meta': result['meta']})


@api_v1.get('/products/<int:product_id>')
@login_required
def get_product(product_id):
    """One product with its latest price columns."""
    detail = product_list.get_product(product_id, current_user.id)
    if detail is None:
        abort(404)
    return _json({'success': True, 'data': detail})


@api_v1.get('/products/<int:product_id>/prices')
@login_required
@validate_query(ProductPricesQuery)
def get_product_prices(product_id):
    """Daily price history of one product for a range."""
    result = product_list.get_product_prices(product_id, request.validated_query.range,
                                             current_user.id)
    if result is None:
        abort(404)
    return _json({'success': True, 'data': result})
