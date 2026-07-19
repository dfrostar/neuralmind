"""self_hosted.py — Self-hosted mode detection, config, and data-dir initialization.

When NEURALMIND_SELF_HOSTED=true or config.self_hosted.enabled=true, NeuralMind
operates with all data in a local directory (no cloud calls, no telemetry).
This module owns that directory creation and validation.
"""

from __future__ import annotations

import os
import stat
import tempfile
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

# System paths that must never be used as data_dir (path-traversal guard).
# These are directories where writing NeuralMind data could damage the
# system or expose sensitive files. /tmp, /usr, /var are intentionally
# excluded — /var/lib/neuralmind and /tmp/neuralmind are legitimate.
_RESERVED_PATHS = frozenset({
    "/", "/bin", "/boot", "/dev", "/etc", "/lib", "/lib64", "/proc",
    "/root", "/run", "/sbin", "/sys",
})


# Sensitive dot-directories under $HOME that must never be used as data_dir
# (e.g., a crafted config pointing data_dir at ~/.ssh could corrupt keys).
_SENSITIVE_HOME_CHILDREN = frozenset({
    ".ssh", ".gnupg", ".aws", ".kube", ".docker", ".npm", ".pki", ".config",
})


def _is_resolved_path_safe(resolved: Path) -> bool:
    """Return True if resolved path is safe to use as data_dir.

    Rejects absolute paths pointing at system-critical directories,
    sensitive dot-directories under $HOME, and relative paths.
    """
    if not resolved.is_absolute():
        return False
    # Normalize and reject exact matches of reserved paths.
    r = str(resolved)
    if r in _RESERVED_PATHS:
        return False
    # Reject children of reserved paths too (e.g., /etc/neuralmind).
    # Skip the root '/' itself since every absolute path has it as an
    # ancestor; we only want to block children of specific reserved dirs.
    for parent in resolved.parents:
        if str(parent) == resolved.root:  # skip bare "/"
            continue
        if str(parent) in _RESERVED_PATHS:
            return False
    # Reject sensitive dot-directories under $HOME.
    home = Path.home()
    try:
        rel = resolved.relative_to(home)
        parts = rel.parts
        if parts and parts[0] in _SENSITIVE_HOME_CHILDREN:
            return False
    except ValueError:
        pass  # not under home, no home-based check needed
    return True


def _validate_path(path: Path, label: str) -> None:
    """Validate that a user-supplied path is safe.

    Raises ValueError with descriptive message if validation fails.
    """
    resolved = path.expanduser().resolve()
    if not _is_resolved_path_safe(resolved):
        raise ValueError(
            f"{label} resolves to disallowed path {resolved!s}. "
            f"Must be absolute and outside system directories."
        )


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

    Returns status dict with {created: bool, path: str, mode: str, error: str,
    mode_changed: bool}.

    Uses a bounded umask around mkdir to minimize the TOCTOU window where
    the directory exists with looser-than-intended permissions.
    """
    path = Path(data_dir)
    result = {
        "created": False,
        "path": str(path),
        "mode": f"{mode:o}",
        "error": "",
        "mode_changed": False,
    }
    try:
        # Validate before doing any filesystem operations.
        _validate_path(path, "data_dir")

        # Constrain umask so newly created dirs/parents inherit tight
        # permissions atomically. Without this, mkdir creates with
        # (mode & ~umask) and a window exists where the dir is more
        # open than `mode` until chmod runs.
        old_umask = os.umask(~mode & 0o777)
        try:
            path.mkdir(parents=True, exist_ok=True)
        finally:
            os.umask(old_umask)

        # Record pre-chmod mode to surface permission reductions.
        if path.exists():
            before = stat.S_IMODE(path.stat().st_mode)
            if before != mode:
                result["mode_changed"] = True

        # Enforce mode explicitly whether the dir is new or pre-existing.
        path.chmod(mode)
        result["created"] = True
    except PermissionError as e:
        result["error"] = f"Permission denied creating {path}: {e}"
    except OSError as e:
        result["error"] = f"Cannot create {path}: {e}"
    except ValueError as e:
        result["error"] = str(e)
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
        # Write test using tempfile.mkstemp: atomic, symlink-safe, and
        # guaranteed cleanup in finally block.
        fd = None
        probe_path = None
        try:
            fd, probe_path = tempfile.mkstemp(
                prefix=".nm_self_hosted_probe_",
                dir=str(path),
            )
            os.write(fd, b"ok")
            os.close(fd)
            fd = None
            result["writable"] = True
        finally:
            if probe_path is not None:
                try:
                    os.unlink(probe_path)
                except OSError:
                    pass
            elif fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
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
