"""Tests for neuralmind.config — Configuration management."""

from __future__ import annotations

from pathlib import Path


class TestFindConfigFile:
    """Tests for find_config_file()."""

    def test_returns_none_when_no_config(self, tmp_path, monkeypatch):
        """Returns None when no config file exists."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        from neuralmind.config import find_config_file

        assert find_config_file() is None

    def test_returns_path_when_config_exists(self, tmp_path, monkeypatch):
        """Returns the config path when config.toml exists."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        config_dir = tmp_path / "neuralmind"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text("[local_models]\nenabled = true\n")

        from neuralmind.config import find_config_file

        result = find_config_file()
        assert result is not None
        assert result == config_file

    def test_uses_default_xdg_config_home(self, tmp_path, monkeypatch):
        """Falls back to ~/.config when XDG_CONFIG_HOME is not set."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        # Don't create the file — just verify it doesn't crash
        from neuralmind.config import find_config_file

        result = find_config_file()
        # Will be None unless ~/.config/neuralmind/config.toml exists
        assert result is None or isinstance(result, Path)


class TestLoadConfig:
    """Tests for load_config()."""

    def test_returns_default_when_no_file(self, tmp_path, monkeypatch):
        """Returns DEFAULT_CONFIG when no config file exists."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        from neuralmind.config import DEFAULT_CONFIG, load_config

        config = load_config()
        assert "local_models" in config
        assert "api" in config
        assert config["local_models"]["provider"] == DEFAULT_CONFIG["local_models"]["provider"]

    def test_loads_user_config_when_exists(self, tmp_path, monkeypatch):
        """Merges user config with defaults."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        config_dir = tmp_path / "neuralmind"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('[local_models]\nenabled = true\nmodel = "mistral"\n')

        from neuralmind.config import load_config

        config = load_config()
        assert config["local_models"]["enabled"] is True
        assert config["local_models"]["model"] == "mistral"

    def test_handles_corrupt_config_file(self, tmp_path, monkeypatch, capsys):
        """Returns defaults and warns on corrupt config file."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        config_dir = tmp_path / "neuralmind"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text("not valid toml [[[")

        from neuralmind.config import DEFAULT_CONFIG, load_config

        config = load_config()
        # Should fall back to defaults
        assert config == DEFAULT_CONFIG
        captured = capsys.readouterr()
        assert "Warning" in captured.out

    def test_default_config_structure(self):
        """Validates DEFAULT_CONFIG has expected structure."""
        from neuralmind.config import DEFAULT_CONFIG

        assert "local_models" in DEFAULT_CONFIG
        assert "api" in DEFAULT_CONFIG
        assert "enabled" in DEFAULT_CONFIG["local_models"]
        assert "provider" in DEFAULT_CONFIG["local_models"]
        assert "endpoint" in DEFAULT_CONFIG["local_models"]
        assert "model" in DEFAULT_CONFIG["local_models"]
        assert DEFAULT_CONFIG["local_models"]["enabled"] is False
        assert DEFAULT_CONFIG["local_models"]["provider"] == "ollama"
