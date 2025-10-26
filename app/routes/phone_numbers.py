# app/routes/phone_numbers.py
from flask import Blueprint, jsonify
from ..utils import generate_mock_phone_numbers

phone_numbers_bp = Blueprint('phone-numbers', __name__)

@phone_numbers_bp.route('/phone-numbers', methods=['GET'])
def get_phone_numbers():
    phone_numbers = generate_mock_phone_numbers()
    return jsonify(phone_numbers)