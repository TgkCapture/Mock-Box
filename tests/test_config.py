import pytest

from mockbox.config import ConfigError, Settings, finalize, load_settings


def write(tmp_path, text):
    path = tmp_path / "config.ini"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_defaults_when_no_config_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = load_settings(env={})
    assert settings.port == 5000
    assert settings.host == "127.0.0.1"
    assert settings.debug is False
    assert settings.admin_api_keys == ()


def test_empty_secret_key_generates_random_one(tmp_path):
    path = write(tmp_path, "[server]\nsecret_key =\n")
    a = load_settings(path, env={})
    b = load_settings(path, env={})
    assert a.secret_key and a.secret_key_generated
    assert a.secret_key != b.secret_key


def test_reads_file_values(tmp_path):
    path = write(
        tmp_path,
        "[server]\nport = 8080\ndebug = yes\nsecret_key = abc\ncors_origins = http://a, http://b\n"
        "[auth]\nadmin_api_keys = k1, k2 ,\n",
    )
    s = load_settings(path, env={})
    assert (s.port, s.debug, s.secret_key) == (8080, True, "abc")
    assert s.cors_origins == ("http://a", "http://b")
    assert s.admin_api_keys == ("k1", "k2")
    assert not s.secret_key_generated


def test_env_overrides_file(tmp_path):
    path = write(tmp_path, "[server]\nport = 8080\n")
    s = load_settings(path, env={"MOCKBOX_PORT": "9090", "MOCKBOX_ADMIN_API_KEYS": "envkey"})
    assert s.port == 9090
    assert s.admin_api_keys == ("envkey",)


def test_config_path_from_env(tmp_path):
    path = write(tmp_path, "[server]\nport = 7000\n")
    assert load_settings(env={"MOCKBOX_CONFIG": path}).port == 7000


def test_missing_explicit_config_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_settings(str(tmp_path / "nope.ini"), env={})


@pytest.mark.parametrize("text", ["[server]\nport = abc\n", "[server]\nport = 70000\n", "[server]\ndebug = maybe\n"])
def test_invalid_values_raise(tmp_path, text):
    with pytest.raises(ConfigError):
        load_settings(write(tmp_path, text), env={})


def test_malformed_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="Could not parse"):
        load_settings(write(tmp_path, "port = 1\n"), env={})


def test_overrides_keep_generated_secret_flag():
    s = finalize(Settings())
    assert s.with_overrides(port=1234).secret_key == s.secret_key
    assert s.with_overrides(port=1234).secret_key_generated
    assert not s.with_overrides(secret_key="explicit").secret_key_generated
