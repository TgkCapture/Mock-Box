"""RSS feed as JSON (default) or as real RSS 2.0 XML (``?format=xml``)."""

from xml.sax.saxutils import escape

from flask import Blueprint, Response, jsonify, request

from .. import generators
from ..controls import count_arg, now, rng
from ..errors import ApiError

bp = Blueprint("rss_feed", __name__)

CHANNEL = {
    "title": "Sample RSS Feed",
    "link": "https://example.com/rss",
    "description": "This is a mock RSS feed for testing purposes.",
}


def _to_xml(items) -> str:
    def el(tag, value):
        return f"<{tag}>{escape(str(value))}</{tag}>"

    item_xml = "".join(
        "<item>"
        + el("title", item["title"])
        + el("description", item["description"])
        + el("link", item["link"])
        + f'<guid isPermaLink="true">{escape(item["guid"])}</guid>'
        + el("pubDate", item["pubDate"])
        + "</item>"
        for item in items
    )
    channel = "".join(el(k, v) for k, v in CHANNEL.items())
    return f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>{channel}{item_xml}</channel></rss>'


@bp.get("/rss-feed")
def get_rss_feed():
    fmt = request.args.get("format", "json")
    if fmt not in ("json", "xml"):
        raise ApiError(400, "Query parameter 'format' must be 'json' or 'xml'")
    items = generators.rss_items(rng(), now(), count_arg(5))
    if fmt == "xml":
        return Response(_to_xml(items), mimetype="application/rss+xml")
    return jsonify({"channel": {**CHANNEL, "items": items}})
