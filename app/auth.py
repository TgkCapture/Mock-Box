# app/auth.py
from flask import request, jsonify, current_app
from functools import wraps
import base64
import jwt
import datetime
import secrets
from typing import Optional, Dict, Any

class AuthManager:
    def __init__(self, app=None):
        self.app = app
        self.tokens = set()  
        
    def init_app(self, app):
        """Initialize with Flask app context"""
        self.app = app
        
    def get_secret_key(self):
        """Get secret key from app config"""
        if self.app and hasattr(self.app, 'config'):
            return self.app.config.get('secret_key', 'default-12345-secret-key')
        
        return current_app.config.get('secret_key', 'default-12345-secret-key')
    
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
    
    def verify_api_key(self, api_key: str) -> bool:
        """Verify API key"""
        return api_key in self.tokens
    
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

# Initialize auth manager
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