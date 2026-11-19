import pytest

from mockbox.__main__ import main


def test_cli_runs_with_overrides(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    captured = {}

    def fake_run(self, host, port, debug):
        captured.update(host=host, port=port, debug=debug, app=self)

    monkeypatch.setattr("flask.Flask.run", fake_run)
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
