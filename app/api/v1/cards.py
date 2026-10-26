"""Catalog list endpoint: GET /cards (F2-c S2-S9)."""
from flask import current_app, request
from flask_login import current_user, login_required

from app.api.v1 import api_v1
from app.schemas.validation import validate_query
from app.schemas.validators import CardListQuery
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
