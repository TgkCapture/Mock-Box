# app/routes/phone_numbers.py
from flask import Blueprint, jsonify, request
from ..utils import generate_mock_phone_numbers
from ..auth import require_auth, no_auth_required

phone_numbers_bp = Blueprint('phone-numbers', __name__)

# Public endpoint - no authentication required
@phone_numbers_bp.route('/phone-numbers/public', methods=['GET'])
@no_auth_required
def get_phone_numbers_public():
    """Public endpoint - no authentication required"""
    phone_numbers = generate_mock_phone_numbers()
    return jsonify({
        'phone_numbers': phone_numbers,
        'auth_required': False,
        'message': 'Public access - no authentication required'
    })

# Protected endpoint - requires any authentication
@phone_numbers_bp.route('/phone-numbers', methods=['GET'])
@require_auth('any')
def get_phone_numbers_protected():
    """Protected endpoint - requires authentication"""
    phone_numbers = generate_mock_phone_numbers()
    
    auth_context = get_auth_context()
    
    return jsonify({
        'phone_numbers': phone_numbers,
        'auth_required': True,
        'auth_context': auth_context
    })

# Specific auth type endpoints
@phone_numbers_bp.route('/phone-numbers/jwt', methods=['GET'])
@require_auth('jwt')
def get_phone_numbers_jwt():
    phone_numbers = generate_mock_phone_numbers()
    return jsonify({
        'phone_numbers': phone_numbers,
        'auth_type': 'jwt',
        'user': getattr(request, 'user', {})
    })

@phone_numbers_bp.route('/phone-numbers/api-key', methods=['GET'])
@require_auth('api_key')
def get_phone_numbers_api_key():
    phone_numbers = generate_mock_phone_numbers()
    return jsonify({
        'phone_numbers': phone_numbers,
        'auth_type': 'api_key'
    })

def get_auth_context():
    """Extract authentication context from request"""
    auth_header = request.headers.get('Authorization', '')
    
    if auth_header.startswith('Bearer '):
        from ..auth import auth_manager
        token = auth_header[7:]
        payload = auth_manager.verify_jwt_token(token)
        if payload:
            return {'type': 'jwt', 'user': payload}
        else:
            return {'type': 'bearer'}
    elif auth_header.startswith('ApiKey '):
        return {'type': 'api_key'}
    elif auth_header.startswith('Basic '):
        return {'type': 'basic', 'user': getattr(request, 'user', {})}
    
    return {'type': 'unknown'}