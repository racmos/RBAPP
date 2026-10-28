"""Collection endpoints: GET /collection (F3-b)."""
from flask import current_app, request
from flask_login import current_user, login_required

from app.api.v1 import api_v1
from app.schemas.validation import validate_query
from app.schemas.validators import CollectionListQuery
from app.services.collection_read import list_collection


@api_v1.get('/collection')
@login_required
@validate_query(CollectionListQuery)
def list_collection_groups():
    """The user's collection as groups (one per printing and foil) with totals and facets."""
    result = list_collection(request.validated_query, current_user)
    body = {'success': True, 'data': {'items': result['items']}, 'meta': result['meta']}
    return current_app.response_class(
        current_app.json.dumps(body, sort_keys=False),
        mimetype='application/json',
    )
