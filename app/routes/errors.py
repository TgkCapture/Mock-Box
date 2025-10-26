# app/routes/errors.py
from flask import Blueprint, jsonify

errors_bp = Blueprint('errors', __name__)

@errors_bp.route('/error', methods=['GET'])
def error_simulation():
    return jsonify({"error": "Simulated error"}), 500
