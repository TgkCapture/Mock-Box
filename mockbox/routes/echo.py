"""Echo: returns exactly what the client sent, for debugging requests."""

from flask import Blueprint, jsonify, request

from ..inspector import body_preview

bp = Blueprint("echo", __name__)

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


@bp.route("/echo", methods=METHODS)
@bp.route("/echo/<path:subpath>", methods=METHODS)
def echo(subpath: str = ""):
    raw = request.get_data(cache=True)
    json_body = request.get_json(silent=True) if request.is_json else None
    files = [
        {"field": field, "filename": f.filename, "content_type": f.content_type, "size": len(f.read())}
        for field, f in request.files.items(multi=True)
    ]
    return jsonify({
        "method": request.method,
        "path": request.path,
        "query": request.args.to_dict(flat=False),
        "headers": dict(request.headers),
        "content_type": request.content_type,
        "json": json_body,
        "form": request.form.to_dict(flat=False) if request.form else None,
        "files": files or None,
        "body": None if (json_body is not None or request.form or files) else body_preview(raw),
        "client": request.remote_addr,
    })
