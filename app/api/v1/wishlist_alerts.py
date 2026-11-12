"""Wishlist price alerts endpoints (F4-g-2): the caller's alerts (newest first, unread
filter), the lists that hold an alert's card now, and marking alerts read. Logic in
`app/services/wishlist_alerts.py`; another user's alert is a 404."""
from flask import abort, request
from flask_login import current_user, login_required

from app.api.v1 import api_v1
from app.api.v1.wishlists import _json
from app.schemas.validation import validate_json, validate_query
from app.schemas.validators import WishlistAlertsQuery, WishlistAlertsRead
from app.services import wishlist_alerts


@api_v1.get('/wishlist-alerts')
@login_required
@validate_query(WishlistAlertsQuery)
def list_wishlist_alerts():
    """The caller's alerts, newest first; `meta.unread_count` feeds the unread badge."""
    query = request.validated_query
    found = wishlist_alerts.list_alerts(current_user, unread=query.unread, page=query.page,
                                        per_page=query.per_page)
    return _json({'items': found['items']}, meta=found['meta'])


@api_v1.get('/wishlist-alerts/<int:alert_id>/lists')
@login_required
def wishlist_alert_lists(alert_id):
    """The caller's wishlists that hold the alert's card now, in list order."""
    try:
        return _json({'items': wishlist_alerts.alert_lists(current_user, alert_id)})
    except wishlist_alerts.AlertNotFound:
        abort(404)


@api_v1.post('/wishlist-alerts/read')
@login_required
@validate_json(WishlistAlertsRead)
def read_wishlist_alerts():
    """Mark the sent alerts read, or every unread one when `ids` is absent or empty."""
    return _json({'marked': wishlist_alerts.mark_read(current_user,
                                                      request.validated_data.ids)})
