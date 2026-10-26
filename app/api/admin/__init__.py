"""Admin API: blueprint `api_admin` under /riftbound/api/v1/admin (F13-R1).

Every route is admin-only: `before_request(require_admin)` answers a JSON 401
to anonymous callers and a JSON 403 to plain users, so routes added later
cannot forget the guard. Errors reuse the api_v1 envelope handler. CSRF is
NOT exempt: unsafe requests need `X-CSRFToken`.
"""
from flask import Blueprint

from app.api.v1 import _any_error
from app.security import require_admin

api_admin = Blueprint('api_admin', __name__, url_prefix='/riftbound/api/v1/admin')
api_admin.before_request(require_admin)
api_admin.register_error_handler(Exception, _any_error)

# Import for the side effect of registering the routes on `api_admin`.
from app.api.admin import cards, jobs, overview, riot, sets  # noqa: E402,F401
