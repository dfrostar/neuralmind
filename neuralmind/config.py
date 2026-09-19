"""config.py — project-level configuration loader for NeuralMind.

Reads user overrides from ``~/.config/neuralmind/config.toml`` (or
``$XDG_CONFIG_HOME/neuralmind/config.toml``) and merges them over the
built-in DEFAULT_CONFIG. Used by the local-Ollama client to resolve the
endpoint/model without env-var juggling.

Example:
    >>> from neuralmind.config import load_config
    >>> cfg = load_config()
    >>> cfg.local_models.endpoint
    'http://localhost:11434'

See Also:
    - ``neuralmind/local_client.py`` — consumer for the local-model section
    - ``docs/compliance/THIRD_PARTY_LLM_DISCLOSURE.md`` — why there's no
      cloud-API fallback section here: NeuralMind doesn't call one

Version:
    0.55.0
"""

import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import toml

logger = logging.getLogger(__name__)


# ── Schema ────────────────────────────────────────────────────────────────


@dataclass
class LocalModelsConfig:
    enabled: bool = False
    provider: str = "ollama"
    endpoint: str = "http://localhost:11434"
    model: str = "llama3.1"
    api_key: str | None = None

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass
class NeuralMindConfig:
    local_models: LocalModelsConfig = field(default_factory=LocalModelsConfig)

    def __getitem__(self, key: str) -> Any:
        """Dict-style backward compat: config['local_models']."""
        try:
            return getattr(self, key)
        except AttributeError as exc:
            raise KeyError(key) from exc

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-style .get() backward compat."""
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: str) -> bool:
        """Dict-style 'in' check: 'local_models' in config."""
        return hasattr(self, key)

    def __iter__(self):
        """Dict-style iteration over keys."""
        return iter(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NeuralMindConfig":
        """Build a config from a raw dict, ignoring unknown keys."""
        local = data.get("local_models", {}) or {}
        return cls(
            local_models=LocalModelsConfig(
                **{k: v for k, v in local.items() if k in LocalModelsConfig.__dataclass_fields__}
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Defaults ──────────────────────────────────────────────────────────────


DEFAULT_CONFIG = NeuralMindConfig()


# ── Loader ────────────────────────────────────────────────────────────────


def find_config_file() -> Path | None:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    config_path = config_home / "neuralmind" / "config.toml"
    if config_path.exists():
        return config_path
    return None


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> NeuralMindConfig:
    """Load and validate user config, falling back on defaults."""
    config_file = find_config_file()
    if not config_file:
        return DEFAULT_CONFIG

    try:
        raw = toml.load(config_file)
    except Exception as exc:
        # Log via logger; also print for backward compat with tests checking stdout
        logger.warning("Could not parse config file %s: %s", config_file, exc)
        print(f"Warning: Could not load config file {config_file}: {exc}")
        return DEFAULT_CONFIG

    if not isinstance(raw, dict):
        logger.warning(
            "Config file %s must be a TOML table, got %s", config_file, type(raw).__name__
        )
        return DEFAULT_CONFIG

    merged = _deep_merge(DEFAULT_CONFIG.to_dict(), raw)
    return NeuralMindConfig.from_dict(merged)


# ── Singleton (lazy) ──────────────────────────────────────────────────────

_CONFIG: NeuralMindConfig | None = None


def get_config() -> NeuralMindConfig:
    """Return the cached config, loading on first access."""
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = load_config()
    return _CONFIG


def reset_config_cache() -> None:
    """Clear cached config (for tests)."""
    global _CONFIG
    _CONFIG = None


# Backward-compatible module-level singleton (lazy)
def __getattr__(name: str) -> Any:
    if name == "CONFIG":
        return get_config()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
