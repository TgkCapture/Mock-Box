# app/routes/user_activities.py
from flask import Blueprint, jsonify
from datetime import datetime, timedelta
import random

user_activities_bp = Blueprint('user_activities', __name__)

@user_activities_bp.route('/user-activities', methods=['GET'])
def get_user_activities():
    activity_types = ["login", "logout", "purchase", "viewed_product", "added_to_cart"]
    activities = [
        {
            "activity_id": i + 1,
            "user_id": random.randint(1, 100),
            "activity_type": random.choice(activity_types),
            "timestamp": (datetime.now() - timedelta(hours=random.randint(1, 72))).isoformat()
        }
        for i in range(10)
    ]
    return jsonify(activities)
