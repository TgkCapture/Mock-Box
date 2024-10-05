from flask import Flask, jsonify, request
import random
import configparser
import os

app = Flask(__name__)

config = configparser.ConfigParser()
config.read('config.ini')

@app.route('/api/phone-numbers', methods=['GET'])
def get_phone_numbers():
    phone_numbers = generate_mock_phone_numbers()
    return jsonify(phone_numbers)

def generate_mock_phone_numbers(count=50):
    phone_numbers = []
    for _ in range(count):
        number = "+26588" + "".join([str(random.randint(0, 9)) for _ in range(7)])
        phone_numbers.append(number)
    return phone_numbers

@app.route('/api/error', methods=['GET'])
def error_simulation():
    return jsonify({"error": "Simulated error"}), 500

@app.route('/api/data', methods=['GET'])
def get_data():
    data_type = request.args.get('type', 'default')
    if data_type == 'numbers':
        return jsonify(generate_mock_phone_numbers())
    else:
        return jsonify({"message": "Unknown data type"}), 400

@app.after_request
def log_request(response):
    app.logger.info(f'{request.method} {request.path} - {response.status_code}')
    return response

if __name__ == '__main__':
    port = int(config['server']['port'])
    debug_mode = config['server'].getboolean('debug')
    
    app.run(port=port, debug=debug_mode)
