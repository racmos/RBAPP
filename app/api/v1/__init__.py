"""API v1: blueprint `api_v1` under /riftbound/api/v1 (API-1).

CSRF is NOT exempt here: unsafe requests need `X-CSRFToken`, obtained from
GET /auth/session. Landing partials live at /api/* (another blueprint), so the
two never collide.
"""
from flask import Blueprint

from app.errors import http_error_response, unexpected_error_response
from werkzeug.exceptions import HTTPException

api_v1 = Blueprint('api_v1', __name__, url_prefix='/riftbound/api/v1')


@api_v1.errorhandler(Exception)
def _any_error(error):
    """Whatever goes wrong inside this blueprint answers with the envelope.

    HTTP errors keep their status; anything else is a generic 500 that is
    logged but never shown (no stack trace, no exception text).
    """
    if isinstance(error, HTTPException):
        return http_error_response(error)
    return unexpected_error_response(error)


# Import for the side effect of registering the routes on `api_v1`.
from app.api.v1 import auth, bans, cards, collection, me, meta, products  # noqa: E402,F401
