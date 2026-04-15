from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix
import os

db = SQLAlchemy()
login = LoginManager()
login.login_view = 'auth.login'

def create_app(config_class=Config, **test_config):
    # Get the absolute path to the app directory
    app_dir = os.path.dirname(os.path.abspath(__file__))
    
    app = Flask(__name__, 
                static_folder=os.path.join(app_dir, 'static'),
                static_url_path='/riftbound/static')
    app.config.from_object(config_class)
    
    # Apply test configuration overrides before initializing extensions
    if test_config:
        app.config.update(test_config)

    # Fix engine options and schema for SQLite (used in tests)
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if db_uri.startswith('sqlite'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
        # SQLite does not support schemas — patch all model __table_args__
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        import sqlite3

        @event.listens_for(Engine, 'connect')
        def set_sqlite_pragma(dbapi_conn, connection_record):
            if isinstance(dbapi_conn, sqlite3.Connection):
                cursor = dbapi_conn.cursor()
                # Check if already attached before attaching
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
    login.init_app(app)
    # Asegurar que Flask respete X-Forwarded-* y X-Forwarded-Prefix enviados por NGINX
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=0)

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

    return app
