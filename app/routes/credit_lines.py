from flask import Blueprint, jsonify
import random

credit_lines_bp = Blueprint('credit_lines', __name__)

@credit_lines_bp.route('/credit-lines', methods=['GET'])
def get_credit_lines():
    credit_lines = [
        {
            "credit_line_id": i + 1,
            "customer_name": f"Customer {i+1}",
            "credit_limit": round(random.uniform(1000, 10000), 2),
            "balance": round(random.uniform(0, 10000), 2),
            "status": random.choice(["active", "inactive", "overdue"])
        }
        for i in range(5)
    ]
    return jsonify(credit_lines)
