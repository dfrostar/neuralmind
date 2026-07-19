"""self_hosted.py — Self-hosted mode detection, config, and data-dir initialization.

When NEURALMIND_SELF_HOSTED=true or config.self_hosted.enabled=true, NeuralMind
operates with all data in a local directory (no cloud calls, no telemetry).
This module owns that directory creation and validation.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SelfHostedConfig:
    data_dir: Path
    license_path: Path
    bind_address: str = "127.0.0.1"
    port: int = 8765


NEURALMIND_SELF_HOSTED_ENV = "NEURALMIND_SELF_HOSTED"
NEURALMIND_DATA_DIR_ENV = "NEURALMIND_DATA_DIR"
NEURALMIND_LICENSE_PATH_ENV = "NEURALMIND_LICENSE_PATH"


def is_self_hosted() -> bool:
    """Detect self-hosted mode from environment variable or config file."""
    env_flag = os.environ.get(NEURALMIND_SELF_HOSTED_ENV, "").lower()
    if env_flag in ("1", "true", "yes", "on"):
        return True
    # Check config file
    from .config import load_config
    try:
        cfg = load_config()
        return cfg.self_hosted.enabled
    except Exception:
        return False


def get_data_dir() -> Path:
    """Resolve data dir from env var, then config, then default."""
    env_dir = os.environ.get(NEURALMIND_DATA_DIR_ENV)
    if env_dir:
        return Path(env_dir)
    from .config import load_config
    try:
        cfg = load_config()
        return Path(cfg.self_hosted.data_dir)
    except Exception:
        return Path.home() / ".local" / "share" / "neuralmind"


def init_data_dir(data_dir: Path, mode: int = 0o700) -> dict:
    """Create data directory with secure permissions.

    Returns status dict with {created: bool, path: str, mode: str, error: str}.
    """
    path = Path(data_dir)
    result = {"created": False, "path": str(path), "mode": f"{mode:o}", "error": ""}
    try:
        path.mkdir(parents=True, exist_ok=True)
        # Set mode explicitly (umask can interfere)
        path.chmod(mode)
        result["created"] = True
    except PermissionError as e:
        result["error"] = f"Permission denied creating {path}: {e}"
    except OSError as e:
        result["error"] = f"Cannot create {path}: {e}"
    return result


def check_data_dir_health(data_dir: Path) -> dict:
    """Health check for data dir: exists, writable, correct mode."""
    path = Path(data_dir)
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir() if path.exists() else False,
        "writable": False,
        "mode": None,
        "error": "",
    }
    if not path.exists():
        result["error"] = "does not exist"
        return result
    try:
        st = path.stat()
        result["mode"] = f"{stat.S_IMODE(st.st_mode):o}"
        # Write test
        probe = path / ".nm_self_hosted_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        result["writable"] = True
    except OSError as e:
        result["error"] = str(e)
    return result


def check_license_health(license_path: Path) -> dict:
    """Check license file existence and readability."""
    path = Path(license_path)
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "readable": False,
        "size": None,
        "error": "",
    }
    if not path.exists():
        result["error"] = "license file missing (self-hosted requires license)"
        return result
    try:
        st = path.stat()
        result["size"] = st.st_size
        _ = path.read_text(encoding="utf-8")
        result["readable"] = True
    except OSError as e:
        result["error"] = f"Cannot read: {e}"
    return result


def get_self_hosted_status() -> dict:
    """Aggregate status for `neuralmind team self-hosted status`."""
    data_dir = get_data_dir()
    data_health = check_data_dir_health(data_dir)
    license_path = _resolve_license_path()
    lic_health = check_license_health(license_path)
    return {
        "self_hosted": is_self_hosted(),
        "data_dir": data_health,
        "license": lic_health,
        "ok": data_health.get("writable", False) and lic_health.get("exists", False),
    }


def _resolve_license_path() -> Path:
    env_path = os.environ.get(NEURALMIND_LICENSE_PATH_ENV)
    if env_path:
        return Path(env_path)
    from .config import load_config
    try:
        cfg = load_config()
        return Path(cfg.license_file)
    except Exception:
        return Path.home() / ".config" / "neuralmind" / "license.json"
