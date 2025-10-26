# app/routes/auth.py
from flask import Blueprint, request, jsonify
from app.auth import auth_manager, require_auth

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/auth/api-key', methods=['GET'])
def generate_api_key():
    """Generate a new API key"""
    api_key = auth_manager.generate_api_key()
    return jsonify({
        'api_key': api_key,
        'message': 'Use this API key in Authorization header as: ApiKey <key>'
    })

@auth_bp.route('/auth/jwt-token', methods=['POST'])
def generate_jwt_token():
    """Generate JWT token with custom payload"""
    payload = request.get_json() or {}
    default_payload = {
        'user_id': 'mock_user_123',
        'username': 'mock_user',
        'role': 'admin'
    }
    default_payload.update(payload)
    
    token = auth_manager.generate_jwt_token(default_payload)
    return jsonify({
        'access_token': token,
        'token_type': 'bearer',
        'expires_in': 86400
    })

@auth_bp.route('/auth/oauth-token', methods=['POST'])
def generate_oauth_token():
    """Generate OAuth2 style token"""
    token_data = auth_manager.generate_oauth_token()
    return jsonify(token_data)

@auth_bp.route('/auth/verify', methods=['GET'])
@require_auth('any')
def verify_token():
    """Verify any type of token"""
    auth_header = request.headers.get('Authorization', '')
    
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        if hasattr(request, 'user'):  # JWT token
            return jsonify({
                'valid': True,
                'auth_type': 'jwt',
                'user': request.user
            })
        else:  # Generic bearer
            return jsonify({
                'valid': True,
                'auth_type': 'bearer'
            })
    elif auth_header.startswith('ApiKey '):
        return jsonify({
            'valid': True,
            'auth_type': 'api_key'
        })
    elif auth_header.startswith('Basic '):
        return jsonify({
            'valid': True,
            'auth_type': 'basic',
            'user': getattr(request, 'user', {})
        })
    
    return jsonify({'valid': False}), 401

@auth_bp.route('/auth/protected', methods=['GET'])
@require_auth('any')
def protected_route():
    """Example protected route that works with any auth"""
    auth_info = {
        'message': 'Access granted to protected route',
        'auth_type': 'unknown'
    }
    
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        if hasattr(request, 'user'):
            auth_info.update({
                'auth_type': 'jwt',
                'user': request.user
            })
        else:
            auth_info['auth_type'] = 'bearer'
    elif auth_header.startswith('ApiKey '):
        auth_info['auth_type'] = 'api_key'
    elif auth_header.startswith('Basic '):
        auth_info['auth_type'] = 'basic'
        auth_info['user'] = getattr(request, 'user', {})
    
    return jsonify(auth_info)

# Different auth type examples
@auth_bp.route('/auth/jwt-only', methods=['GET'])
@require_auth('jwt')
def jwt_only():
    return jsonify({'message': 'JWT authentication successful', 'user': request.user})

@auth_bp.route('/auth/api-key-only', methods=['GET'])
@require_auth('api_key')
def api_key_only():
    return jsonify({'message': 'API Key authentication successful'})

@auth_bp.route('/auth/basic-only', methods=['GET'])
@require_auth('basic')
def basic_only():
    return jsonify({'message': 'Basic authentication successful', 'user': request.user})