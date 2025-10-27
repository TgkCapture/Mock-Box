# app/routes/admin.py
from flask import Blueprint, request, jsonify
from ..auth import auth_manager, require_auth
import secrets

admin_bp = Blueprint('admin', __name__)

# Admin endpoints - protected with special admin auth
@admin_bp.route('/admin/api-keys', methods=['GET'])
@require_auth('any')
def get_admin_api_keys():
    """Get all admin-configured API keys"""
    return jsonify({
        'admin_api_keys': auth_manager.get_admin_api_keys(),
        'total': len(auth_manager.get_admin_api_keys())
    })

@admin_bp.route('/admin/api-keys', methods=['POST'])
@require_auth('any')
def create_admin_api_key():
    """Create a new admin API key"""
    data = request.get_json() or {}
    
    if 'api_key' in data:
        api_key = data['api_key']
    else:
        api_key = f"admin_{secrets.token_hex(16)}"
    
    prefix = data.get('prefix', 'admin')
    if prefix and not api_key.startswith(prefix):
        api_key = f"{prefix}_{secrets.token_hex(16)}"
    
    auth_manager.add_admin_api_key(api_key)
    
    return jsonify({
        'message': 'Admin API key created successfully',
        'api_key': api_key,
        'usage': 'Use in Authorization header as: ApiKey <key>'
    })

@admin_bp.route('/admin/api-keys/<api_key>', methods=['DELETE'])
@require_auth('any')
def delete_admin_api_key(api_key):
    """Delete an admin API key"""
    auth_manager.remove_admin_api_key(api_key)
    return jsonify({
        'message': 'Admin API key deleted successfully',
        'deleted_key': api_key
    })

@admin_bp.route('/admin/generated-tokens', methods=['GET'])
@require_auth('any')
def get_generated_tokens():
    """Get all dynamically generated tokens"""
    return jsonify({
        'generated_tokens': list(auth_manager.tokens),
        'total': len(auth_manager.tokens)
    })

@admin_bp.route('/admin/clear-tokens', methods=['POST'])
@require_auth('any')
def clear_generated_tokens():
    """Clear all dynamically generated tokens"""
    count = len(auth_manager.tokens)
    auth_manager.tokens.clear()
    return jsonify({
        'message': f'Cleared {count} generated tokens',
        'cleared_count': count
    })