import os
from pathlib import Path
from typing import Any

import toml

DEFAULT_CONFIG = {
    'local_models': {
        'enabled': False,
        'provider': 'ollama',
        'endpoint': 'http://localhost:11434',
        'model': 'llama3.1',
        'api_key': None,
        'fallback_to_api': True,
    },
    'api': {
        'provider': 'openrouter',
        'api_key': os.environ.get('OPENROUTER_API_KEY'),
    }
}

def find_config_file() -> Path | None:
    config_home = Path(os.environ.get('XDG_CONFIG_HOME', '~/.config')).expanduser()
    config_path = config_home / 'neuralmind' / 'config.toml'
    if config_path.exists():
        return config_path
    return None

def load_config() -> dict[str, Any]:
    config_file = find_config_file()
    if config_file:
        try:
            user_config = toml.load(config_file)
            config = DEFAULT_CONFIG.copy()
            config.update(user_config)
            return config
        except Exception as e:
            print(f"Warning: Could not load config file {config_file}: {e}")
    return DEFAULT_CONFIG

CONFIG = load_config()
