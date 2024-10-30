# Mock-Box 
Mock-Box is a versatile mock server built with Flask, designed to provide JSON responses across a variety of test scenarios. With endpoints covering phone numbers, user data, product information, and more, it’s an ideal tool for API developers needing realistic data formats for testing. The server is modular and can be easily expanded to incorporate additional mock data types and response formats as new testing needs arise, making it a flexible solution for diverse API testing workflows.

## Features

1. **Phone Numbers**
   - **Endpoint**: `/api/phone-numbers`
   - **Method**: `GET`
   - **Description**: Provides a list of mock phone numbers for testing.

2. **Error Simulation**
   - **Endpoint**: `/api/error`
   - **Method**: `GET`
   - **Description**: Simulates an error response to test error handling mechanisms.

3. **Dynamic Data**
   - **Endpoint**: `/api/data`
   - **Method**: `GET`
   - **Description**: Returns different types of mock data based on the query parameter `type`. For example, `type=numbers` returns mock phone numbers.

4. **Product Information**
   - **Endpoint**: `/api/products`
   - **Method**: `GET`
   - **Description**: Returns a list of mock products, including `product_id`, `name`, and `price`.

5. **User Data**
   - **Endpoint**: `/api/users`
   - **Method**: `GET`
   - **Description**: Provides mock user data, such as `user_id`, `name`, and `email`.

6. **Order Information**
   - **Endpoint**: `/api/orders`
   - **Method**: `GET`
   - **Description**: Returns a list of mock orders, with details like `order_id`, `user_id`, `product_id`, and `quantity`.

7. **RSS Feed Simulation**
   - **Endpoint**: `/api/rss-feed`
   - **Method**: `GET`
   - **Description**: Simulates an RSS feed structure in JSON format, useful for testing applications that parse RSS feeds.

8. **Credit Lines**
   - **Endpoint**: `/api/credit-lines`
   - **Method**: `GET`
   - **Description**: Provides mock data on credit lines, including `credit_line_id`, `customer_name`, `credit_limit`, `balance`, and `status`.

9. **User Activities**
   - **Endpoint**: `/api/user-activities`
   - **Method**: `GET`
   - **Description**: Returns a list of mock user activities, such as `activity_id`, `user_id`, `activity_type`, and `timestamp`.

## Requirements

- Python 3.x
- Flask

## Installation

1. Clone the repository or download the source code.
   ```bash
   git clone https://github.com/TgkCapture/mock-box.git
   cd mock-box
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure the server port and debug mode in `config.ini`.

4. Run the server:
   ```bash
   python run.py
   ```

The server will start at `http://127.0.0.1:<port>` (replace `<port>` with the port you specified in `config.ini`).