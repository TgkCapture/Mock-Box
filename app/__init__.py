# app/__init__.py
from flask import Flask, request
from configparser import ConfigParser
import os

def load_config():
    config = ConfigParser()
    config.read('config.ini')
    
    secret_key = config.get('server', 'secret_key', fallback='default-12345-secret-key')
    
    return {
        'PORT': int(config['server']['port']),
        'DEBUG': config['server'].getboolean('debug'),
        'SECRET_KEY': secret_key
    }

def create_app():
    app = Flask(__name__)
    
    # Load config
    app.config.update(load_config())

    # Initialize auth manager with app context
    from .auth import auth_manager
    auth_manager.init_app(app)
    
    # Register Home Blueprint (root routes)
    from .home import home_bp
    app.register_blueprint(home_bp)
    
    # Register Authentication Blueprint
    from .routes.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api')

    # Register Admin Blueprint
    from .routes.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/api')
    
    # Register API Blueprints
    from .routes.phone_numbers import phone_numbers_bp
    from .routes.errors import errors_bp
    from .routes.data import data_bp
    from .routes.products import products_bp
    from .routes.users import users_bp
    from .routes.orders import orders_bp
    from .routes.rss_feed import rss_feed_bp
    from .routes.credit_lines import credit_lines_bp
    from .routes.user_activities import user_activities_bp

    app.register_blueprint(phone_numbers_bp, url_prefix='/api')
    app.register_blueprint(errors_bp, url_prefix='/api')
    app.register_blueprint(data_bp, url_prefix='/api')
    app.register_blueprint(products_bp, url_prefix='/api')
    app.register_blueprint(users_bp, url_prefix='/api')
    app.register_blueprint(orders_bp, url_prefix='/api')
    app.register_blueprint(rss_feed_bp, url_prefix='/api')
    app.register_blueprint(credit_lines_bp, url_prefix='/api')
    app.register_blueprint(user_activities_bp, url_prefix='/api')
    
    # After request logging
    @app.after_request
    def log_request(response):
        app.logger.info(f'{request.method} {request.path} - {response.status_code}')
        return response

    return app