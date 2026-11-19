import re

from mockbox.auth import SCHEMES

UNDOCUMENTED = {"/", "/docs", "/openapi.json", "/static/<path:filename>"}


def _routes(app):
    for rule in app.url_map.iter_rules():
        if rule.rule in UNDOCUMENTED:
            continue
        path = re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", rule.rule)
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            yield path, method.lower(), rule.endpoint


def test_every_route_is_documented(app, client):
    spec = client.get("/openapi.json").get_json()
    routes = set((p, m) for p, m, _ in _routes(app))
    documented = {(p, m) for p, ops in spec["paths"].items() for m in ops}
    assert routes - documented == set(), "routes missing from mockbox/openapi.py"
    assert documented - routes == set(), "documented routes that do not exist"


def test_documented_security_matches_decorators(app, client):
    spec = client.get("/openapi.json").get_json()
    scheme_names = {"BearerAuth": {"jwt", "bearer"}, "ApiKeyAuth": {"api_key"}, "BasicAuth": {"basic"}}
    for path, method, endpoint in _routes(app):
        view = app.view_functions[endpoint]
        documented = spec["paths"][path][method]["security"]
        schemes = getattr(view, "auth_schemes", None)
        if schemes is None:
            # Either public, or admin (ApiKeyAuth only).
            assert documented in ([], [{"ApiKeyAuth": []}]), path
            continue
        covered = set().union(*(scheme_names[next(iter(req))] for req in documented))
        assert set(schemes) <= covered | {"bearer"}, path
        assert set(schemes) & covered, path
        if set(schemes) == set(SCHEMES):
            assert len(documented) == 3, path
