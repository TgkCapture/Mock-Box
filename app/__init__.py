from flask import Flask, request
from configparser import ConfigParser
import os

def load_config():
    config = ConfigParser()
    config.read('config.ini')
    return {
        'PORT': int(config['server']['port']),
        'DEBUG': config['server'].getboolean('debug')
    }

def create_app():
    app = Flask(__name__)
    
    # Load config
    app.config.update(load_config())
    
    # Register Blueprints
    from .routes.phone_numbers import phone_numbers_bp
    from .routes.errors import errors_bp
    from .routes.data import data_bp
    
    app.register_blueprint(phone_numbers_bp, url_prefix='/api')
    app.register_blueprint(errors_bp, url_prefix='/api')
    app.register_blueprint(data_bp, url_prefix='/api')
    
    # After request logging
    @app.after_request
    def log_request(response):
        app.logger.info(f'{request.method} {request.path} - {response.status_code}')
        return response

    return app