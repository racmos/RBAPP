"""Catalog endpoints: GET /cards (F2-c), GET /cards/<set>/<id> (F2-d)."""
from flask import abort, current_app, request
from flask_login import current_user, login_required

from app.api.v1 import api_v1
from app.schemas.validation import validate_query
from app.schemas.validators import CardListQuery, CardPricesQuery
from app.services import card_detail
from app.services.card_list import search_cards


@api_v1.get('/cards')
@login_required
@validate_query(CardListQuery)
def list_cards():
    """Paginated card catalog with filters, facets and sorting."""
    result = search_cards(request.validated_query, current_user.username)
    body = {'success': True, 'data': {'items': result['items']}, 'meta': result['meta']}
    return current_app.response_class(
        current_app.json.dumps(body, sort_keys=False),
        mimetype='application/json',
    )


@api_v1.get('/cards/<set_id>/<card_id>')
@login_required
def get_card(set_id, card_id):
    """One card with printings, related cards, prices and user data."""
    detail = card_detail.get_card_detail(set_id, card_id, current_user.username)
    if detail is None:
        abort(404)
    body = {'success': True, 'data': detail}
    return current_app.response_class(
        current_app.json.dumps(body, sort_keys=False),
        mimetype='application/json',
    )


@api_v1.get('/cards/<set_id>/<card_id>/prices')
@login_required
@validate_query(CardPricesQuery)
def get_card_prices(set_id, card_id):
    """Daily price history of one card for a range."""
    result = card_detail.get_card_prices(set_id, card_id,
                                          request.validated_query.range)
    if result is None:
        abort(404)
    return {'success': True, 'data': result}
