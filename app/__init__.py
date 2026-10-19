from flask import Flask
from dotenv import dotenv_values, load_dotenv
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
import os

from app.db_schema import MIGRATE_OPTIONS
from config import engine_options, load_settings, resolve_env, validate_settings

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
# CSRF for every unsafe method, no exemptions (CSRF-1, D14).
csrf = CSRFProtect()
# Per-IP limits (LOGIN-7, D15). get_remote_address reads request.remote_addr,
# which ProxyFix already rewrote from X-Forwarded-For.
limiter = Limiter(get_remote_address)

_APP_DIR = os.path.dirname(os.path.abspath(__file__))

# `<repo>/.env`. Module-level so tests can point it at a temporary file.
DOTENV_PATH = os.path.join(os.path.dirname(_APP_DIR), '.env')

# Alembic environment (`flask db ...`). Absolute so it works from any CWD.
MIGRATIONS_DIR = os.path.join(os.path.dirname(_APP_DIR), 'migrations')


def _maybe_load_dotenv():
    """Load `.env` into os.environ only when the effective environment is
    development (CFG-4, D1). Real environment variables always win
    (override=False).

    When RB_ENV is unset the file may declare `RB_ENV=development` itself
    (R15); the file is read for that one key without touching os.environ, and
    applied only if it says development. An explicit RB_ENV=production or
    testing never reads the file.
    """
    declared = (os.environ.get('RB_ENV') or '').strip()
    if not declared:
        declared = (dotenv_values(DOTENV_PATH).get('RB_ENV') or '').strip()
    if declared.lower() == 'development':
        load_dotenv(DOTENV_PATH, override=False)


def _init_limiter(app):
    """Wire Flask-Limiter into `app` and honour RATELIMIT_ENABLED.

    Flask-Limiter registers its request hooks only when it is enabled at
    `init_app` time. Here the hooks are always wired and the switch is read per
    request (`limiter.enabled`), so a test fixture can turn the limiter on for
    an existing app, exactly like CSRFProtect's WTF_CSRF_ENABLED. The limiter is
    a process-wide singleton: the last app created decides, which is fine for
    one app per process and for one test at a time.
    """
    enabled = bool(app.config.get('RATELIMIT_ENABLED', True))
    app.config['RATELIMIT_ENABLED'] = True          # init_app returns early otherwise
    limiter.init_app(app)
    app.config['RATELIMIT_ENABLED'] = enabled
    limiter.enabled = enabled


def create_app(**overrides):
    """Application factory.

    Flow (D1, D2): load `.env` if development -> resolve RB_ENV -> read the
    environment -> apply `overrides` (tests) -> compute engine options from the
    FINAL database URI -> validate. Validation runs last so overrides count.
    """
    _maybe_load_dotenv()
    env = resolve_env(os.environ)

    app = Flask(__name__,
                static_folder=os.path.join(_APP_DIR, 'static'),
                static_url_path='/riftbound/static')
    app.config.update(load_settings(env, os.environ))

    # Apply test configuration overrides before initializing extensions
    app.config.update(overrides)
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options(
        app.config.get('SQLALCHEMY_DATABASE_URI'))
    validate_settings(app.config, env)

    # Schema handling for SQLite (used in tests)
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI') or ''
    if db_uri.startswith('sqlite'):
        # SQLite does not support schemas — patch all model __table_args__
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        import sqlite3

        import re

        def _regexp_replace(value, pattern, replacement, flags=''):
            """SQLite shim for PostgreSQL regexp_replace(value, pattern, replacement, flags)."""
            if value is None:
                return None
            re_flags = 0
            if 'g' in (flags or ''):
                return re.sub(pattern, replacement, str(value), flags=re_flags)
            return re.sub(pattern, replacement, str(value), count=1, flags=re_flags)

        @event.listens_for(Engine, 'connect')
        def set_sqlite_pragma(dbapi_conn, connection_record):
            if isinstance(dbapi_conn, sqlite3.Connection):
                # Register regexp_replace as a custom SQLite function
                dbapi_conn.create_function('regexp_replace', 4, _regexp_replace)
                dbapi_conn.create_function('regexp_replace', 3, _regexp_replace)
                cursor = dbapi_conn.cursor()
                # Attach riftbound schema if not already attached
                cursor.execute("PRAGMA database_list")
                attached = {row[1] for row in cursor.fetchall()}
                if 'riftbound' not in attached:
                    cursor.execute('ATTACH DATABASE ":memory:" AS riftbound')
                cursor.close()
    
    # Make min/max available in all templates
    from builtins import min as _min, max as _max
    app.jinja_env.globals['min'] = _min
    app.jinja_env.globals['max'] = _max
    
    db.init_app(app)
    migrate.init_app(app, db, directory=MIGRATIONS_DIR, **MIGRATE_OPTIONS)
    from app.cli import register_cli
    register_cli(app)
    login.init_app(app)
    csrf.init_app(app)
    _init_limiter(app)
    # Asegurar que Flask respete X-Forwarded-* y X-Forwarded-Prefix enviados por NGINX
    # El número de saltos de confianza viene de PROXY_FIX_X_FOR/PROTO/HOST (CFG-7).
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=app.config['PROXY_FIX_X_FOR'],
        x_proto=app.config['PROXY_FIX_X_PROTO'],
        x_host=app.config['PROXY_FIX_X_HOST'],
        x_prefix=0,
    )

    # Landing page (root /)
    from app.routes.landing import landing_bp
    app.register_blueprint(landing_bp)

    from app.routes.routes import main_bp
    app.register_blueprint(main_bp)
    
    # Register auth blueprint
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)
    
    # Register domain blueprints
    from app.routes.domains import (
        sets_bp,
        cards_bp,
        collection_bp,
        deck_bp,
        price_bp,
        profile_bp,
    )
    app.register_blueprint(sets_bp)
    app.register_blueprint(cards_bp)
    app.register_blueprint(collection_bp)
    app.register_blueprint(deck_bp)
    app.register_blueprint(price_bp)
    app.register_blueprint(profile_bp)

    # Single-page app (/riftbound/app/), served from FRONTEND_DIST
    from app.routes.spa import spa_bp
    app.register_blueprint(spa_bp)

    # JSON API v1 (/riftbound/api/v1)
    from app.api.v1 import api_v1
    app.register_blueprint(api_v1)

    from app.models import User
    @login.user_loader
    def load_user(id):
        return User.query.get(int(id))
    
    # Custom Jinja filter for pagination
    @app.template_filter('first_val')
    def first_val(value):
        """Convert multi-value dict to single values for URL building"""
        if isinstance(value, dict):
            return {k: v[0] if isinstance(v, list) and len(v) > 0 else v 
                    for k, v in value.items()}
        return value
    
    # Register error handlers
    from app.errors import register_error_handlers
    register_error_handlers(app)

    @login.unauthorized_handler
    def unauthorized():
        """Not logged in (API-8, D18): JSON 401 for JSON clients, else the usual
        flash and redirect to the login page (with `next`)."""
        from flask import flash, redirect, request
        from flask_login.utils import login_url
        from app.api.error_codes import ErrorCode
        from app.errors import json_error, wants_json
        if wants_json():
            return json_error('Unauthorized', 'Authentication is required', 401,
                              code=ErrorCode.UNAUTHENTICATED)
        flash(login.login_message, login.login_message_category)
        return redirect(login_url(login.login_view, request.url))

    return app
