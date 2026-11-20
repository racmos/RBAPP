"""Card bans: GET /bans (F2-a S8), for signed-in users (D-F2-3).

Bans are changed only with `flask bans` until the F10 admin UI. Each item lists
the catalog printings of the banned name (`[]` for a name banned with --force) and
`active`: false while the ban is upcoming (dated after today, UTC; bans effective date).
"""
from flask import request
from flask_login import login_required

from app.api.responses import ok
from app.api.v1 import api_v1
from app.schemas.validation import validate_query
from app.schemas.validators import BanListQuery
from app.services import bans as bans_service


@api_v1.get('/bans')
@login_required
@validate_query(BanListQuery)
def list_bans():
    """Every ban, or those of `?mode=1v1|2v2` and `?status=active|upcoming|all` (default
    all), ordered by mode and then name."""
    query = request.validated_query
    day = bans_service.today()
    printings = bans_service.printings_by_key()

    def item(ban):
        found = printings.get(bans_service.name_key(ban.name), [])
        return {'name': ban.name, 'mode': ban.mode, 'since': ban.since.isoformat(),
                'reason': ban.reason, 'active': bans_service.in_effect(ban, day),
                'printings': [{'set_id': set_id, 'card_id': card_id}
                              for set_id, card_id in found]}

    return ok({'items': [item(ban) for ban in bans_service.list_bans(
        query.mode, query.status, on=day)]})
