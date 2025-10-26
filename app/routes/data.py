# app/routes/data.py
from flask import Blueprint, jsonify, request
from ..utils import generate_mock_phone_numbers

data_bp = Blueprint('data', __name__)

@data_bp.route('/data', methods=['GET'])
def get_data():
    data_type = request.args.get('type', 'default')
    if data_type == 'numbers':
        return jsonify(generate_mock_phone_numbers())
    elif data_type == 'names':
        return jsonify(generate_mock_names())
    else:
        return jsonify({"message": "Unknown data type"}), 400
