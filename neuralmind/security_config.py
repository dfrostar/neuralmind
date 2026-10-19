# SPDX-License-Identifier: MIT
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
``profile``
    ``cui`` turns on the settings a CUI enclave needs as one unit: it forces
    ``identity: os`` and ``require_encrypted_storage: true``, and adds the
    refusals in ``security_profile.py`` (no listener beyond loopback or
    without its token, no LLM documentation seeding). A profile can't be
    loosened: ``profile: cui`` with ``identity: declared`` or
    ``require_encrypted_storage: false`` is a contradiction and fails closed.

The general config loader treats a file that doesn't parse as empty, which is
right for backend tuning and wrong for a security policy: a YAML typo would
silently switch enforcement off. So when the file fails to parse and its text
names one of these settings, this module fails closed instead.

The machine policy
------------------
``neuralmind-backend.yaml`` lives in the project root, and whoever owns that
directory can delete it, even when an administrator owns the file. Deleting it
used to switch every setting above off. An administrator can also write
``/etc/neuralmind/policy.yaml`` (``C:\\ProgramData\\NeuralMind\\policy.yaml``
on Windows) with a ``security:`` section holding ``profile``, ``identity`` or
``require_encrypted_storage``. It applies to every project on the machine and
only tightens: each setting takes the stricter of the machine's and the
project's value, so neither file can loosen the other. It can't grant roles
(``users``, ``default_role`` and ``roles`` stay in the project file), so a
user who manages to create it gains nothing. A machine policy that doesn't
parse, names anything else, holds an invalid value, or on POSIX isn't owned by root and writable only
by root holds every project to the strictest settings.
"""

from __future__ import annotations

import stat
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .backend_manager import backend_config_path, read_backend_config_file

IDENTITY_DECLARED = "declared"
IDENTITY_OS = "os"
# Not a mode a user can choose: an unparseable or contradictory identity
# setting, which the MCP server answers by refusing every call.
IDENTITY_INVALID = "invalid"

PROFILE_CUI = "cui"
_PROFILES = (PROFILE_CUI,)

_ENFORCEMENT_KEYS = ("identity", "require_encrypted_storage", "profile")
_FALSE_WORDS = {"false", "no", "off", "0"}
_TRUE_WORDS = {"true", "yes", "on", "1"}

MACHINE_POLICY_NAME = "policy.yaml"


def _program_data() -> Path:
    """The all-users application data folder on Windows.

    Asked of the shell rather than read from ``%ProgramData%``: any user can
    set that variable, and pointing it at an empty folder would hide the
    machine policy.
    """
    fallback = Path("C:\\ProgramData")
    try:
        import ctypes

        buffer = ctypes.create_unicode_buffer(260)
        # CSIDL_COMMON_APPDATA
        status = ctypes.windll.shell32.SHGetFolderPathW(None, 0x23, None, 0, buffer)
    except (AttributeError, OSError):
        # No shell32 to ask (not Windows), or the call failed: the default.
        return fallback
    return Path(buffer.value) if status == 0 and buffer.value else fallback


def _default_machine_policy_path() -> Path:
    if sys.platform == "win32":
        return _program_data() / "NeuralMind" / MACHINE_POLICY_NAME
    return Path("/etc/neuralmind") / MACHINE_POLICY_NAME


# Deliberately not configurable from the environment: a variable the user
# controls could point it at an empty file. Tests replace the attribute.
MACHINE_POLICY_PATH = _default_machine_policy_path()


@dataclass(frozen=True)
class SecuritySettings:
    identity: str = IDENTITY_DECLARED
    users: dict[str, str] = field(default_factory=dict)
    default_role: str | None = None
    require_encrypted_storage: bool = False
    profile: str | None = None
    config_path: Path | None = None
    # Why the settings were forced to their strictest values, if they were.
    problem: str | None = None
    # The machine policy that applied, if one exists.
    machine_policy: Path | None = None


def load_security_settings(project_path: str | Path) -> SecuritySettings:
    project = _load_project_settings(project_path)
    machine = load_machine_policy()
    if machine is None:
        return project
    return _tightened(project, machine)


def load_machine_policy() -> SecuritySettings | None:
    """The machine policy's settings, or None when there is no machine policy."""
    path = MACHINE_POLICY_PATH
    try:
        present = path.exists()
    except OSError:
        present = True  # can't even tell: treat it as present, and unreadable below
    if not present:
        return None

    def strictest(problem: str) -> SecuritySettings:
        return SecuritySettings(
            identity=IDENTITY_INVALID,
            require_encrypted_storage=True,
            profile=PROFILE_CUI,
            config_path=path,
            problem=f"machine policy {path} {problem}",
            machine_policy=path,
        )

    untrusted = _untrusted_machine_policy(path)
    if untrusted:
        return strictest(untrusted)
    try:
        config = read_backend_config_file(path)
    except Exception as exc:
        return strictest(f"does not parse ({exc})")
    security = config.get("security")
    if not isinstance(security, dict):
        return strictest("needs a `security` mapping")
    extra = sorted(str(key) for key in security if key not in _ENFORCEMENT_KEYS)
    if extra:
        return strictest(
            f"can only set {', '.join(_ENFORCEMENT_KEYS)}, not {', '.join(extra)}; "
            "users and roles stay in each project's neuralmind-backend.yaml"
        )
    settings = _parse(security, path)
    if settings.problem:
        # Strictest, not just _parse's refusal of MCP calls: an invalid value
        # such as `identity: sometimes` must not leave the profile and the
        # encryption check off.
        return strictest(f"is invalid: {settings.problem}")
    if _malformed_required(security):
        # A project file reads a misspelling as on (_required); here it holds
        # every project to the strictest settings, like any other invalid value.
        value = security["require_encrypted_storage"]
        return strictest(
            f"is invalid: security.require_encrypted_storage must be true or false, not {value!r}"
        )
    return replace(settings, machine_policy=path)


def _untrusted_machine_policy(path: Path) -> str | None:
    """Why ``path`` could be changed by someone other than an administrator.

    POSIX: the file and its directory must be owned by root and writable by
    no one else, since a writable directory lets its file be replaced. Windows
    ACLs aren't mode bits, so nothing is checked there; the walkthrough
    says how to restrict the folder.
    """
    if sys.platform == "win32":
        return None
    for target in (path, path.parent):
        try:
            info = target.stat()
        except OSError as exc:
            return f"can't be checked ({exc})"
        if info.st_uid != 0:
            return f"is not owned by root ({target} belongs to uid {info.st_uid})"
        if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            return f"is writable by users other than root ({target}); chmod go-w it"
    return None


def _tightened(project: SecuritySettings, machine: SecuritySettings) -> SecuritySettings:
    """Each setting at the stricter of the project's and the machine's value."""
    if IDENTITY_INVALID in (project.identity, machine.identity):
        identity = IDENTITY_INVALID
    elif IDENTITY_OS in (project.identity, machine.identity):
        identity = IDENTITY_OS
    else:
        identity = IDENTITY_DECLARED
    return replace(
        project,
        identity=identity,
        require_encrypted_storage=(
            project.require_encrypted_storage or machine.require_encrypted_storage
        ),
        profile=machine.profile or project.profile,
        problem=machine.problem or project.problem,
        machine_policy=machine.machine_policy,
    )


def _load_project_settings(project_path: str | Path) -> SecuritySettings:
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
                # An unreadable file that names a profile is held to the
                # strictest one, not to none.
                profile=PROFILE_CUI if config_mentions(path, ("profile",)) else None,
                config_path=path,
                problem=f"{path.name} does not parse ({exc}); refusing rather than ignoring its security settings",
            )
        return SecuritySettings(config_path=path)

    security = config.get("security") or {}
    if not isinstance(security, dict):
        return SecuritySettings(
            identity=IDENTITY_INVALID,
            require_encrypted_storage=True,
            # As for a file that doesn't parse: a malformed section that
            # names a profile is held to the strictest one.
            profile=PROFILE_CUI if config_mentions(path, ("profile",)) else None,
            config_path=path,
            problem="`security` must be a mapping",
        )
    return _parse(security, path)


def _parse(security: dict[str, Any], path: Path) -> SecuritySettings:
    require = _required(security)
    raw_profile = security.get("profile")
    profile = str(raw_profile).strip().lower() if raw_profile is not None else None
    if profile == PROFILE_CUI:
        require = True
    default_identity = IDENTITY_OS if profile == PROFILE_CUI else IDENTITY_DECLARED
    raw_identity = security.get("identity", default_identity)
    identity = str(raw_identity).strip().lower() if raw_identity is not None else ""
    users_raw = security.get("users", {}) or {}
    default_role = security.get("default_role")

    problem = None
    if "profile" in security and profile not in _PROFILES:
        # A blank or misspelled profile is never read as "no profile": it is
        # held to the strictest one, and MCP calls are refused until it's fixed.
        problem = f"security.profile must be 'cui', not {raw_profile!r}"
        require = True
        profile = PROFILE_CUI
    elif profile == PROFILE_CUI and identity != IDENTITY_OS:
        problem = (
            "security.profile: cui requires identity: os; remove security.identity or set it to os"
        )
    elif (
        profile == PROFILE_CUI
        and not _required(security)
        and "require_encrypted_storage" in security
    ):
        problem = (
            "security.profile: cui requires encrypted storage; remove "
            "security.require_encrypted_storage or set it to true"
        )
    elif identity not in (IDENTITY_DECLARED, IDENTITY_OS):
        problem = f"security.identity must be 'declared' or 'os', not {raw_identity!r}"
    elif not isinstance(users_raw, dict):
        problem = "security.users must map OS account names to roles"
    elif default_role is not None and not isinstance(default_role, str):
        problem = "security.default_role must be a role name"
    if problem:
        return SecuritySettings(
            identity=IDENTITY_INVALID,
            require_encrypted_storage=require,
            profile=profile if profile in _PROFILES else None,
            config_path=path,
            problem=problem,
        )

    users = {str(name): str(role) for name, role in users_raw.items()}
    return SecuritySettings(
        identity=identity,
        users=users,
        default_role=default_role,
        require_encrypted_storage=require,
        profile=profile,
        config_path=path,
    )


def _required(security: dict[str, Any]) -> bool:
    """Read ``require_encrypted_storage``. Absent means off.

    Present, only an explicit "off" turns it off: ``false``, ``0``, or the
    words false/no/off/0. A blank value (``require_encrypted_storage:``
    parses as None), an empty list or mapping, or a misspelling counts as on —
    a malformed setting should make NeuralMind stricter, never quietly looser.
    """
    if "require_encrypted_storage" not in security:
        return False
    value = security["require_encrypted_storage"]
    if value is False:
        return False
    if isinstance(value, int) and not isinstance(value, bool) and value == 0:
        return False
    if isinstance(value, str) and value.strip().lower() in _FALSE_WORDS:
        return False
    return True


def _malformed_required(security: dict[str, Any]) -> bool:
    """Whether ``require_encrypted_storage`` is present but neither on nor off."""
    if "require_encrypted_storage" not in security:
        return False
    value = security["require_encrypted_storage"]
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value not in (0, 1)
    if isinstance(value, str):
        return value.strip().lower() not in _FALSE_WORDS | _TRUE_WORDS
    return True


def _mentions_enforcement(path: Path) -> bool:
    return config_mentions(path, _ENFORCEMENT_KEYS)


def config_mentions(path: Path, keys: tuple[str, ...]) -> bool:
    """Whether a config file's raw text names any of ``keys`` outside a comment.

    For a file that doesn't parse: if it names a security setting, the caller
    fails closed; if not, the file is left to the lenient general loader. The
    match is plain text rather than key syntax, so a policy whose key is itself
    mistyped (``identity os``) still counts; only YAML comments are skipped.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return True  # can't read it either: assume the worst
    if path.suffix in {".yaml", ".yml"}:
        text = "\n".join(_without_comment(line) for line in text.splitlines())
    return any(key in text for key in keys)


def _without_comment(line: str) -> str:
    # YAML starts a comment with '#' at the start of a line or after
    # whitespace; a '#' inside a value such as a URL fragment is kept.
    if line.lstrip().startswith("#"):
        return ""
    cuts = [i for i in (line.find(" #"), line.find("\t#")) if i >= 0]
    return line[: min(cuts)] if cuts else line
