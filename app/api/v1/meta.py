"""Public service endpoints: GET /health (API-2), GET /meta/config (API-3),
GET /meta/game (F2-b: game metadata for the catalog UI)."""
from datetime import date

from flask import current_app
from sqlalchemy import func, text
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.api.responses import fail, ok
from app.api.v1 import api_v1
from app.schemas.game_domain import (CARD_TYPES, CONDITIONS, DOMAINS, GAME_MODES, LANGUAGES,
                                     RARITIES, SUPERTYPES)
from app.services.captcha import get_captcha_provider
from app.services.catalog import parse_domains, set_order, type_facets


@api_v1.get('/health')
def health():
    """200 after a `SELECT 1`; 503 when the database does not answer.

    The failure is logged, never returned: the body must not leak connection
    strings or driver messages.
    """
    try:
        db.session.execute(text('SELECT 1'))
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Health check: the database did not answer')
        return fail('Service Unavailable', 'The service is temporarily unavailable', 503)
    return ok({'status': 'ok', 'db': 'ok', 'version': current_app.config['APP_VERSION']})


@api_v1.get('/meta/config')
def meta_config():
    """What a client needs before it can show the register form. No secrets."""
    provider = get_captcha_provider().name
    return ok({
        'env': current_app.config['RB_ENV'],
        'registration_open': True,
        'captcha': {
            'provider': provider,
            'required_for': ['register'] if provider != 'none' else [],
        },
        'csrf': {'header': 'X-CSRFToken'},
    })


def _extra_known(values, known):
    """Tuple values first, then the other distinct non-empty values, sorted."""
    seen = {value.lower() for value in known}
    extra = sorted({value for value in values if value and value.lower() not in seen},
                   key=str.lower)
    return list(known) + extra


def _distinct(column):
    return [value for (value,) in db.session.query(column).distinct().all() if value]


@api_v1.get('/meta/game')
def meta_game():
    """Game metadata for the catalog UI (F2-b S9): enums, sets, price freshness."""
    from app.models.card import RbCard
    from app.models.cardmarket import RbcmPrice
    from app.models.set import RbSet

    # Base values only (owner feedback S18): "Champion Unit" is type Unit and supertype
    # Champion, "Body Chaos" is Body and Chaos, a bare "Token" is supertype Token.
    types, supertypes = set(), set()
    for raw in _distinct(RbCard.rbcar_type):
        card_type, words = type_facets(raw)
        if card_type:
            types.add(card_type)
        supertypes.update(words)
    domains = {domain for raw in _distinct(RbCard.rbcar_domain)
               for domain in parse_domains(raw)}

    sets = db.session.query(RbSet).all()
    order = set_order(sets)
    counts = dict(db.session.query(RbCard.rbcar_rbset_id, func.count())
                  .group_by(RbCard.rbcar_rbset_id).all())
    ordered_sets = sorted(sets, key=lambda row: (order[row.rbset_id], row.rbset_id))

    latest = db.session.query(func.max(RbcmPrice.rbprc_date)).scalar()
    body = ok({
        'modes': list(GAME_MODES),
        'domains': _extra_known(domains, DOMAINS),
        'types': _extra_known(types, CARD_TYPES),
        'supertypes': _extra_known(supertypes, SUPERTYPES),
        'rarities': _extra_known(_distinct(RbCard.rbcar_rarity), RARITIES),
        'sets': [{'id': row.rbset_id, 'name': row.rbset_name,
                  'released_on': row.rbset_outdat.isoformat() if row.rbset_outdat else None,
                  'card_count': counts.get(row.rbset_id, 0)}
                 for row in ordered_sets],
        'price': {'provider': 'cardmarket', 'currency': 'EUR',
                  'updated_on': date(int(latest[0:4]), int(latest[4:6]),
                                     int(latest[6:8])).isoformat() if latest else None},
        'rules': {},
        'conditions': list(CONDITIONS),
        'languages': list(LANGUAGES),
    })
    body.headers['Cache-Control'] = 'no-cache'
    return body
