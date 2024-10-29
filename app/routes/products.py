from flask import Blueprint, jsonify
import random

products_bp = Blueprint('products', __name__)

@products_bp.route('/products', methods=['GET'])
def get_products():
    products = [
        {"id": 1, "name": "Laptop", "price": round(random.uniform(500, 1500), 2), "in_stock": True},
        {"id": 2, "name": "Smartphone", "price": round(random.uniform(200, 800), 2), "in_stock": False},
        {"id": 3, "name": "Headphones", "price": round(random.uniform(50, 300), 2), "in_stock": True},
        {"id": 4, "name": "Monitor", "price": round(random.uniform(100, 400), 2), "in_stock": True},
        {"id": 5, "name": "Keyboard", "price": round(random.uniform(20, 100), 2), "in_stock": False}
    ]
    return jsonify(products)