"""security_config.py — the enforcement settings under ``security:``.

``neuralmind-backend.yaml`` already carries ``security.roles`` and
``security.rate_limit`` (read by ``mcp_security``). This module reads the
settings that change what NeuralMind *refuses*:

``identity``
    ``declared`` (default) trusts the ``actor`` and ``role`` an MCP tool call
    declares. ``os`` takes the actor from the OS account the server runs as
    (see ``identity.py``) and the role from ``users``.
``users``
    OS account name -> role, used when ``identity: os``.
``default_role``
    Role for an OS account missing from ``users``. Unset means such an
    account is refused.
``require_encrypted_storage``
    When true, NeuralMind refuses to build, query, serve MCP tools or run
    hooks for a project whose volume it can't verify as encrypted (see
    ``storage_guard.py``).

The general config loader treats a file that doesn't parse as empty, which is
right for backend tuning and wrong for a security policy: a YAML typo would
silently switch enforcement off. So when the file fails to parse and its text
names one of these settings, this module fails closed instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .backend_manager import backend_config_path, read_backend_config_file

IDENTITY_DECLARED = "declared"
IDENTITY_OS = "os"
# Not a mode a user can choose: an unparseable or contradictory identity
# setting, which the MCP server answers by refusing every call.
IDENTITY_INVALID = "invalid"

_ENFORCEMENT_KEYS = ("identity", "require_encrypted_storage")
_FALSE_WORDS = {"false", "no", "off", "0", ""}


@dataclass(frozen=True)
class SecuritySettings:
    identity: str = IDENTITY_DECLARED
    users: dict[str, str] = field(default_factory=dict)
    default_role: str | None = None
    require_encrypted_storage: bool = False
    config_path: Path | None = None
    # Why the settings were forced to their strictest values, if they were.
    problem: str | None = None


def load_security_settings(project_path: str | Path) -> SecuritySettings:
    path = backend_config_path(project_path)
    if path is None:
        return SecuritySettings()
    try:
        config = read_backend_config_file(path)
    except Exception as exc:
        if _mentions_enforcement(path):
            return SecuritySettings(
                identity=IDENTITY_INVALID,
                require_encrypted_storage=True,
                config_path=path,
                problem=f"{path.name} does not parse ({exc}); refusing rather than ignoring its security settings",
            )
        return SecuritySettings(config_path=path)

    security = config.get("security") or {}
    if not isinstance(security, dict):
        return SecuritySettings(
            identity=IDENTITY_INVALID,
            require_encrypted_storage=True,
            config_path=path,
            problem="`security` must be a mapping",
        )
    return _parse(security, path)


def _parse(security: dict[str, Any], path: Path) -> SecuritySettings:
    require = _truthy(security.get("require_encrypted_storage", False))
    raw_identity = security.get("identity", IDENTITY_DECLARED)
    identity = str(raw_identity).strip().lower() if raw_identity is not None else ""
    users_raw = security.get("users", {}) or {}
    default_role = security.get("default_role")

    problem = None
    if identity not in (IDENTITY_DECLARED, IDENTITY_OS):
        problem = f"security.identity must be 'declared' or 'os', not {raw_identity!r}"
    elif not isinstance(users_raw, dict):
        problem = "security.users must map OS account names to roles"
    elif default_role is not None and not isinstance(default_role, str):
        problem = "security.default_role must be a role name"
    if problem:
        return SecuritySettings(
            identity=IDENTITY_INVALID,
            require_encrypted_storage=require,
            config_path=path,
            problem=problem,
        )

    users = {str(name): str(role) for name, role in users_raw.items()}
    return SecuritySettings(
        identity=identity,
        users=users,
        default_role=default_role,
        require_encrypted_storage=require,
        config_path=path,
    )


def _truthy(value: Any) -> bool:
    # Anything that isn't plainly "off" counts as on: a misspelled value
    # should make NeuralMind stricter, never quietly looser.
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in _FALSE_WORDS
    return bool(value)


def _mentions_enforcement(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return True  # can't read it either: assume the worst
    return any(key in text for key in _ENFORCEMENT_KEYS)
