# app/auth.py
from flask import request, jsonify, current_app
from functools import wraps
import base64
import jwt
import datetime
import secrets
from typing import Optional, Dict, Any, List

class AuthManager:
    def __init__(self, app=None):
        self.app = app
        self.tokens = set()  
        self.admin_api_keys = set() 
        
        if app is not None:
            self.init_app(app)
        
    def init_app(self, app):
        """Initialize with Flask app context"""
        self.app = app
        self.load_admin_keys()
        
    def load_admin_keys(self):
        """Load admin-configured API keys from environment or config"""
        try:
            # Try to get from app config first
            if self.app and hasattr(self.app, 'config'):
                admin_keys_env = self.app.config.get('ADMIN_API_KEYS', '')
                if admin_keys_env:
                    keys = [key.strip() for key in admin_keys_env.split(',') if key.strip()]
                    self.admin_api_keys.update(keys)
            
            # Load from config file
            try:
                from configparser import ConfigParser
                config = ConfigParser()
                config.read('config.ini')
                if config.has_option('auth', 'admin_api_keys'):
                    keys = [key.strip() for key in config.get('auth', 'admin_api_keys').split(',') if key.strip()]
                    self.admin_api_keys.update(keys)
            except Exception as e:
                print(f"Warning: Could not load admin keys from config: {e}")
                
        except Exception as e:
            print(f"Warning: Could not load admin keys: {e}")
    
    def get_secret_key(self):
        """Get secret key from app config"""
        try:
            if self.app and hasattr(self.app, 'config'):
                return self.app.config.get('SECRET_KEY', 'mock-server-secret-key-123')
            
            return current_app.config.get('SECRET_KEY', 'mock-server-secret-key-123')
        except RuntimeError:
        
            return 'mock-server-secret-key-123'
    
    def add_admin_api_key(self, api_key: str):
        """Add an admin API key"""
        self.admin_api_keys.add(api_key)
        self.save_admin_keys()
    
    def remove_admin_api_key(self, api_key: str):
        """Remove an admin API key"""
        self.admin_api_keys.discard(api_key)
        self.save_admin_keys()
    
    def save_admin_keys(self):
        """Save admin keys to config file"""
        try:
            from configparser import ConfigParser
            config = ConfigParser()
            config.read('config.ini')
            if not config.has_section('auth'):
                config.add_section('auth')
            config.set('auth', 'admin_api_keys', ','.join(self.admin_api_keys))
            with open('config.ini', 'w') as configfile:
                config.write(configfile)
        except Exception as e:
            print(f"Error saving admin keys: {e}")
    
    def get_admin_api_keys(self) -> List[str]:
        """Get all admin API keys"""
        return list(self.admin_api_keys)
    
    def verify_api_key(self, api_key: str) -> bool:
        """Verify API key (both generated and admin keys)"""
        return api_key in self.tokens or api_key in self.admin_api_keys
    
    # JWT Token Methods
    def generate_jwt_token(self, payload: Dict[str, Any]) -> str:
        """Generate JWT token"""
        payload.update({
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24),
            'iat': datetime.datetime.utcnow()
        })
        return jwt.encode(payload, self.get_secret_key(), algorithm='HS256')
    
    def verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, self.get_secret_key(), algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    # API Key Methods
    def generate_api_key(self) -> str:
        """Generate random API key"""
        api_key = f"mock_{secrets.token_hex(16)}"
        self.tokens.add(api_key)
        return api_key
    
    # OAuth2 Methods
    def generate_oauth_token(self) -> Dict[str, Any]:
        """Generate OAuth2 style token"""
        token_data = {
            'access_token': f"oauth_{secrets.token_hex(20)}",
            'token_type': 'bearer',
            'expires_in': 3600,
            'refresh_token': f"refresh_{secrets.token_hex(20)}",
            'scope': 'read write'
        }
        self.tokens.add(token_data['access_token'])
        return token_data

# Initialize auth manager (without loading admin keys yet)
auth_manager = AuthManager()

# Authentication decorators
def require_auth(auth_type: str = 'any'):
    """
    Authentication decorator factory
    Supported auth_type: 'jwt', 'api_key', 'basic', 'bearer', 'any'
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip auth for OPTIONS requests (CORS)
            if request.method == 'OPTIONS':
                return f(*args, **kwargs)
            
            auth_header = request.headers.get('Authorization')
            
            if not auth_header:
                return jsonify({'error': 'Authorization header required'}), 401
            
            if auth_type in ['any', 'jwt', 'bearer'] and auth_header.startswith('Bearer '):
                token = auth_header[7:]  # Remove 'Bearer ' prefix
                payload = auth_manager.verify_jwt_token(token)
                if payload:
                    request.user = payload
                    return f(*args, **kwargs)
            
            if auth_type in ['any', 'api_key'] and auth_header.startswith('ApiKey '):
                api_key = auth_header[7:]  # Remove 'ApiKey ' prefix
                if auth_manager.verify_api_key(api_key):
                    return f(*args, **kwargs)
            
            if auth_type in ['any', 'basic'] and auth_header.startswith('Basic '):
                # For Basic auth, we'll accept any credentials in mock server
                try:
                    credentials = base64.b64decode(auth_header[6:]).decode('utf-8')
                    username, password = credentials.split(':', 1)
                    request.user = {'username': username, 'auth_type': 'basic'}
                    return f(*args, **kwargs)
                except:
                    pass
            
            if auth_type in ['any', 'bearer'] and auth_header.startswith('Bearer '):
                # Generic bearer token (non-JWT)
                token = auth_header[7:]
                if auth_manager.verify_api_key(token):
                    return f(*args, **kwargs)
            
            return jsonify({'error': 'Invalid authentication'}), 401
        
        return decorated_function
    return decorator

# No authentication required
def no_auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function