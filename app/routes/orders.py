from flask import Blueprint, jsonify
from datetime import datetime, timedelta
import random

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/orders', methods=['GET'])
def get_orders():
    orders = [
        {
            "order_id": 1001,
            "product": "Laptop",
            "quantity": random.randint(1, 5),
            "total_price": round(random.uniform(500, 2000), 2),
            "order_date": str(datetime.now() - timedelta(days=random.randint(1, 365)))
        },
        {
            "order_id": 1002,
            "product": "Smartphone",
            "quantity": random.randint(1, 3),
            "total_price": round(random.uniform(300, 1000), 2),
            "order_date": str(datetime.now() - timedelta(days=random.randint(1, 365)))
        },
        {
            "order_id": 1003,
            "product": "Headphones",
            "quantity": random.randint(1, 10),
            "total_price": round(random.uniform(30, 500), 2),
            "order_date": str(datetime.now() - timedelta(days=random.randint(1, 365)))
        }
    ]
    return jsonify(orders)
