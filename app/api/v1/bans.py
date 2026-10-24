"""Card bans: GET /bans (F2-a S8), for signed-in users (D-F2-3).

Bans are changed only with `flask bans` until the F10 admin UI. Each item lists
the catalog printings of the banned name (`[]` for a name banned with --force).
"""
from flask import request
from flask_login import login_required

from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail, ok
from app.api.v1 import api_v1
from app.schemas.game_domain import GAME_MODES
from app.services import bans as bans_service


@api_v1.get('/bans')
@login_required
def list_bans():
    """Every ban, or those of `?mode=1v1|2v2`, ordered by mode and then name."""
    mode = request.args.get('mode')
    if mode is not None and mode not in GAME_MODES:
        return fail('Validation Error', 'Invalid query parameters', 400,
                    details=[{'field': 'mode', 'message': 'mode must be 1v1 or 2v2',
                              'type': 'literal_error', 'code': str(DetailCode.INVALID_VALUE)}],
                    code=ErrorCode.VALIDATION_ERROR)
    printings = bans_service.printings_by_key()

    def item(ban):
        found = printings.get(bans_service.name_key(ban.name), [])
        return {'name': ban.name, 'mode': ban.mode, 'since': ban.since.isoformat(),
                'reason': ban.reason,
                'printings': [{'set_id': set_id, 'card_id': card_id}
                              for set_id, card_id in found]}

    return ok({'items': [item(ban) for ban in bans_service.list_bans(mode)]})
