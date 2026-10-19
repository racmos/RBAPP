"""Public service endpoints: GET /health (API-2) and GET /meta/config (API-3)."""
from flask import current_app
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.api.responses import fail, ok
from app.api.v1 import api_v1
from app.services.captcha import get_captcha_provider


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
