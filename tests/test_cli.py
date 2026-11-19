import sys
import types

import pytest

from mockbox.__main__ import main, serve


def test_cli_runs_with_overrides(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    captured = {}

    def fake_serve(app, host, port, debug):
        captured.update(host=host, port=port, debug=debug, app=app)

    monkeypatch.setattr("mockbox.__main__.serve", fake_serve)
    assert main(["--port", "6001", "--no-debug"]) == 0
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 6001
    assert captured["debug"] is False


def test_cli_reports_config_errors(tmp_path, capsys):
    assert main(["--config", str(tmp_path / "missing.ini")]) == 2
    assert "configuration error" in capsys.readouterr().err


def test_cli_rejects_bad_port(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["--port", "0"]) == 2


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "mockbox" in capsys.readouterr().out


class FakeApp:
    def __init__(self):
        self.ran = None

    def run(self, **kwargs):
        self.ran = kwargs


def test_serve_prefers_waitress(monkeypatch):
    calls = {}
    fake = types.ModuleType("waitress")
    fake.serve = lambda app, **kw: calls.update(kw)
    monkeypatch.setitem(sys.modules, "waitress", fake)
    app = FakeApp()
    serve(app, "127.0.0.1", 5001, debug=False)
    assert calls["port"] == 5001 and app.ran is None


def test_serve_debug_uses_flask(monkeypatch):
    monkeypatch.setitem(sys.modules, "waitress", types.ModuleType("waitress"))
    app = FakeApp()
    serve(app, "127.0.0.1", 5001, debug=True)
    assert app.ran == {"host": "127.0.0.1", "port": 5001, "debug": True}


def test_serve_falls_back_without_waitress(monkeypatch):
    monkeypatch.setitem(sys.modules, "waitress", None)  # makes the import fail
    app = FakeApp()
    serve(app, "127.0.0.1", 5001, debug=False)
    assert app.ran["port"] == 5001
