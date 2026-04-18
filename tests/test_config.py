"""Tests for neuralmind.config."""

from pathlib import Path


def test_find_config_file_returns_path_when_present(tmp_path, monkeypatch):
    from neuralmind import config

    config_home = tmp_path / ".config"
    config_file = config_home / "neuralmind" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("[api]\nprovider = 'openrouter'\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    found = config.find_config_file()

    assert found == config_file


def test_find_config_file_returns_none_when_missing(tmp_path, monkeypatch):
    from neuralmind import config

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "missing-config-home"))

    assert config.find_config_file() is None


def test_load_config_merges_user_values(monkeypatch):
    from neuralmind import config

    fake_path = Path("/tmp/fake-config.toml")
    monkeypatch.setattr(config, "find_config_file", lambda: fake_path)
    monkeypatch.setattr(
        config.toml,
        "load",
        lambda _path: {
            "api": {"provider": "custom-provider", "api_key": "secret-key"},
            "custom_section": {"enabled": True},
        },
    )

    merged = config.load_config()

    assert merged["api"]["provider"] == "custom-provider"
    assert merged["api"]["api_key"] == "secret-key"
    assert merged["local_models"] == config.DEFAULT_CONFIG["local_models"]
    assert merged["custom_section"]["enabled"] is True


def test_load_config_returns_default_and_warns_on_parse_error(monkeypatch, capsys):
    from neuralmind import config

    fake_path = Path("/tmp/fake-config.toml")
    monkeypatch.setattr(config, "find_config_file", lambda: fake_path)

    def _raise(_path):
        raise ValueError("bad toml")

    monkeypatch.setattr(config.toml, "load", _raise)

    loaded = config.load_config()
    captured = capsys.readouterr()

    assert loaded is config.DEFAULT_CONFIG
    assert "Could not load config file" in captured.out
