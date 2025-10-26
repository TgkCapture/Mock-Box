# app/routes/users.py
from flask import Blueprint, jsonify
from datetime import datetime, timedelta
import random

users_bp = Blueprint('users', __name__)

@users_bp.route('/users', methods=['GET'])
def get_users():
    users = [
        {"id": 1, "name": "Alice", "email": "alice@example.com", "joined_date": str(datetime.now() - timedelta(days=random.randint(1, 1000)))},
        {"id": 2, "name": "Bob", "email": "bob@example.com", "joined_date": str(datetime.now() - timedelta(days=random.randint(1, 1000)))},
        {"id": 3, "name": "Charlie", "email": "charlie@example.com", "joined_date": str(datetime.now() - timedelta(days=random.randint(1, 1000)))},
        {"id": 4, "name": "Diana", "email": "diana@example.com", "joined_date": str(datetime.now() - timedelta(days=random.randint(1, 1000)))}
    ]
    return jsonify(users)