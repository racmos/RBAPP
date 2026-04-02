from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix
import os

db = SQLAlchemy()
login = LoginManager()
login.login_view = 'main.login'

def create_app(config_class=Config):
    # Get the absolute path to the app directory
    app_dir = os.path.dirname(os.path.abspath(__file__))
    
    app = Flask(__name__, 
                static_folder=os.path.join(app_dir, 'static'),
                static_url_path='/riftbound/static')
    app.config.from_object(config_class)

    db.init_app(app)
    login.init_app(app)
    # Asegurar que Flask respete X-Forwarded-* y X-Forwarded-Prefix enviados por NGINX
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=0)

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
