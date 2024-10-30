from flask import Blueprint, jsonify
from datetime import datetime, timedelta
import random

rss_feed_bp = Blueprint('rss_feed', __name__)

@rss_feed_bp.route('/rss-feed', methods=['GET'])
def get_rss_feed():
    feed = {
        "channel": {
            "title": "Sample RSS Feed",
            "link": "http://example.com/rss",
            "description": "This is a mock RSS feed for testing purposes.",
            "items": [
                {
                    "title": f"News Item {i+1}",
                    "description": f"This is the description for news item {i+1}.",
                    "link": f"http://example.com/news/{i+1}",
                    "pubDate": (datetime.now() - timedelta(days=random.randint(1, 30))).strftime('%a, %d %b %Y %H:%M:%S GMT')
                }
                for i in range(5)
            ]
        }
    }
    return jsonify(feed)
