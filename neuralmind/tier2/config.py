"""config.py — Tier 2 YAML configuration schema and I/O.

Tier 2 config lives at ~/.config/neuralmind/tier2.yaml by default. All values
are additive to the MIT product — no MIT paths are altered.

Example:
    >>> from neuralmind.tier2.config import load_config, save_config
    >>> cfg = load_config()
    >>> cfg.seats = 5
    >>> save_config(cfg)  # doctest: +SKIP

See Also:
    - ``neuralmind.tier2.governance`` — governance rules consuming this config
    - ``neuralmind.tier2.license`` — license validation feeding expires_at/seats
    - ``tests/test_config.py`` — test cases and usage patterns
    - ``docs/wiki/Architecture.md#tier2`` — high-level design

Version:
    0.53.0
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

log = logging.getLogger(__name__)

TIER2_CONFIG_DIR = Path(
    os.environ.get("NEURALMIND_CONFIG_DIR", Path.home() / ".config" / "neuralmind")
)
DEFAULT_CONFIG_PATH = TIER2_CONFIG_DIR / "tier2.yaml"

PublishingScope = Literal["personal", "shared", "both"]


@dataclass
class GovernanceConfig:
    """Governance settings for team shared namespace publishing.

    Args:
        enabled: Whether governance checks are active.
        publishing_scope: One of ``"personal"``, ``"shared"``, ``"both"``.
        weight_threshold: Minimum edge weight for auto-publish (0.0-1.0).
        auto_decay_half_life: Days for edge weight to decay by half.
        admin_emails: List of admin email addresses (lowercase-normalized).
    """

    enabled: bool = True
    publishing_scope: PublishingScope = "both"
    weight_threshold: float = 0.1
    auto_decay_half_life: float = 30.0  # days
    admin_emails: list[str] = field(default_factory=list)


@dataclass
class SelfHostedConfig:
    """Self-hosted deployment settings.

    Args:
        enabled: Whether self-hosted mode is active.
        data_dir: Absolute path within user home for data storage.
        bind_address: Network bind address (default 127.0.0.1).
        port: Network port (1-65535).
        offline_grace_days: Days to allow offline operation.
    """

    enabled: bool = False
    data_dir: str = str(Path.home() / ".local" / "share" / "neuralmind")
    bind_address: str = "127.0.0.1"
    port: int = 8765
    offline_grace_days: int = 30


@dataclass
class Tier2Config:
    """Top-level Tier 2 configuration container.

    Args:
        tier: License tier string (``"free"`` or ``"team"``).
        license_file: Path to license.json.
        audit_db: Path to audit log file.
        seats: License seat limit (1 for free tier).
        expires_at: ISO date string or ``"never"``.
        issued_to: License recipient identifier.
        governance: Nested governance config.
        self_hosted: Nested self-hosted config.
    """

    tier: str = "free"
    license_file: str = str(TIER2_CONFIG_DIR / "license.json")
    audit_db: str = str(TIER2_CONFIG_DIR / "audit.db")
    seats: int = 1  # license seat limit; 1 = free tier default
    expires_at: str = ""  # ISO date, from license
    issued_to: str = ""
    governance: GovernanceConfig = field(default_factory=GovernanceConfig)
    self_hosted: SelfHostedConfig = field(default_factory=SelfHostedConfig)

    def is_team_active(self) -> bool:
        """True when license present and not expired.

        Returns:
            True if the license is valid and not expired. Free tier
            (``expires_at="never"``) is always active. Missing or
            unparseable ``expires_at`` returns False.

        Example:
            >>> cfg = Tier2Config(expires_at="never")
            >>> cfg.is_team_active()
            True
        """
        if self.expires_at == "never":
            return True
        if not self.expires_at:
            return False
        from datetime import datetime, timezone

        try:
            exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) <= exp
        except ValueError:
            return False


def load_config(path: Path | None = None) -> Tier2Config:
    """Load Tier 2 config from YAML.

    Args:
        path: Optional path to YAML file. Defaults to ``DEFAULT_CONFIG_PATH``.

    Returns:
        A ``Tier2Config`` instance populated from the file, or defaults
        if the file is missing or unreadable.

    Example:
        >>> cfg = load_config()
        >>> cfg.tier
        'team'
    """
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    if not p.exists():
        return Tier2Config(
            license_file=str(p.with_name("license.json")), audit_db=str(p.with_name("audit.db"))
        )
    try:
        with p.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return Tier2Config()
    return _from_dict(raw)


def save_config(config: Tier2Config, path: Path | None = None) -> Path:
    """Serialize config to YAML.

    Args:
        config: The ``Tier2Config`` to serialize.
        path: Optional path to write to. Defaults to ``DEFAULT_CONFIG_PATH``.

    Returns:
        The path to the written file.

    Example:
        >>> import tempfile
        >>> with tempfile.TemporaryDirectory() as td:
        ...     p = Path(td) / "tier2.yaml"
        ...     _ = save_config(Tier2Config(), p)
        ...     p.exists()
        True
    """
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    data = _to_dict(config)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=True)
    return p


def _from_dict(raw: dict[str, Any]) -> Tier2Config:
    """Reconstruct a ``Tier2Config`` from a raw dict.

    Args:
        raw: Dictionary parsed from YAML.

    Returns:
        A fully validated ``Tier2Config`` instance.
    """
    gov_raw = raw.get("governance", {})
    sh_raw = raw.get("self_hosted", {})
    return Tier2Config(
        tier=str(raw.get("tier", "team")),
        license_file=str(raw.get("license_file", str(TIER2_CONFIG_DIR / "license.json"))),
        audit_db=str(raw.get("audit_db", str(TIER2_CONFIG_DIR / "audit.db"))),
        seats=validate_seats(raw.get("seats", 0)),
        expires_at=str(raw.get("expires_at", "")),
        issued_to=str(raw.get("issued_to", "")),
        governance=GovernanceConfig(
            enabled=gov_raw.get("enabled", True),
            publishing_scope=validate_scope(gov_raw.get("publishing_scope", "both")),
            weight_threshold=validate_threshold(gov_raw.get("weight_threshold", 0.1)),
            auto_decay_half_life=validate_half_life(gov_raw.get("auto_decay_half_life", 30.0)),
            admin_emails=list(gov_raw.get("admin_emails", [])),
        ),
        self_hosted=SelfHostedConfig(
            enabled=sh_raw.get("enabled", False),
            data_dir=validate_data_dir(
                sh_raw.get("data_dir", str(Path.home() / ".local" / "share" / "neuralmind"))
            ),
            bind_address=str(sh_raw.get("bind_address", "127.0.0.1")),
            port=validate_port(sh_raw.get("port", 8765)),
            offline_grace_days=validate_grace_days(sh_raw.get("offline_grace_days", 30)),
        ),
    )


def _to_dict(config: Tier2Config) -> dict[str, Any]:
    """Convert a ``Tier2Config`` to a plain dict for serialization.

    Args:
        config: The config to convert.

    Returns:
        A dictionary suitable for YAML serialization.
    """
    return {
        "tier": config.tier,
        "license_file": config.license_file,
        "audit_db": config.audit_db,
        "seats": config.seats,
        "expires_at": config.expires_at,
        "issued_to": config.issued_to,
        "governance": asdict(config.governance),
        "self_hosted": dict(asdict(config.self_hosted).items()),
    }


def validate_scope(scope: str) -> PublishingScope:
    """Validate publishing scope string.

    Args:
        scope: The scope string to validate.

    Returns:
        The validated scope string.

    Raises:
        ValueError: If ``scope`` is not one of ``"personal"``, ``"shared"``, ``"both"``.

    Example:
        >>> validate_scope("shared")
        'shared'
        >>> validate_scope("invalid")
        Traceback (most recent call last):
            ...
        ValueError: Invalid publishing_scope: 'invalid'. Must be 'personal', 'shared', or 'both'.
    """
    if scope not in ("personal", "shared", "both"):
        raise ValueError(
            f"Invalid publishing_scope: {scope!r}. Must be 'personal', 'shared', or 'both'."
        )
    return scope  # type: ignore[return-value]


def validate_threshold(value: float) -> float:
    """Validate weight threshold.

    Args:
        value: The threshold value to validate.

    Returns:
        The validated threshold as a float.

    Raises:
        ValueError: If ``value`` is not a number or is outside 0.0-1.0.

    Example:
        >>> validate_threshold(0.5)
        0.5
        >>> validate_threshold(1.5)
        Traceback (most recent call last):
            ...
        ValueError: Invalid weight_threshold: 1.5. Must be 0.0–1.0.
    """
    if not isinstance(value, (int, float)) or value < 0.0 or value > 1.0:
        raise ValueError(f"Invalid weight_threshold: {value}. Must be 0.0–1.0.")
    return float(value)


def validate_half_life(value: float) -> float:
    """Validate auto-decay half-life.

    Args:
        value: The half-life value in days.

    Returns:
        The validated half-life as a float.

    Raises:
        ValueError: If ``value`` is not a number or is <= 0.

    Example:
        >>> validate_half_life(30.0)
        30.0
        >>> validate_half_life(-1)
        Traceback (most recent call last):
            ...
        ValueError: Invalid half_life: -1. Must be > 0.
    """
    if not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"Invalid half_life: {value}. Must be > 0.")
    return float(value)


def validate_port(value: int | str | None) -> int:
    """Validate network port.

    Args:
        value: The port number to validate.

    Returns:
        The validated port as an integer.

    Raises:
        ValueError: If ``value`` is not an integer or is outside 1-65535.

    Example:
        >>> validate_port(8080)
        8080
        >>> validate_port(70000)
        Traceback (most recent call last):
            ...
        ValueError: Invalid port: 70000. Must be 1-65535.
    """
    if value is None:
        return 8765
    try:
        v = int(value)
    except (TypeError, ValueError) as err:
        raise ValueError(f"Invalid port: {value!r}. Must be an integer.") from err
    if not (1 <= v <= 65535):
        raise ValueError(f"Invalid port: {v}. Must be 1-65535.")
    return v


def validate_grace_days(value: int | str | None) -> int:
    """Validate offline grace days.

    Args:
        value: The number of grace days to validate.

    Returns:
        The validated grace days as an integer.

    Raises:
        ValueError: If ``value`` is not a non-negative integer.

    Example:
        >>> validate_grace_days(30)
        30
        >>> validate_grace_days(-1)
        Traceback (most recent call last):
            ...
        ValueError: Invalid offline_grace_days: -1. Must be >= 0.
    """
    if value is None:
        return 30
    try:
        v = int(value)
    except (TypeError, ValueError) as err:
        raise ValueError(f"Invalid offline_grace_days: {value!r}. Must be an integer.") from err
    if v < 0:
        raise ValueError(f"Invalid offline_grace_days: {v}. Must be >= 0.")
    return v


def validate_data_dir(value: str | Path | None) -> str:
    """Validate data_dir: must be an absolute path within the user home directory.

    Args:
        value: The data directory path to validate.

    Returns:
        The validated, resolved path as a string.

    Raises:
        ValueError: If ``value`` is not absolute, not within user home, or invalid.

    Example:
        >>> from pathlib import Path
        >>> validate_data_dir(str(Path.home() / ".local" / "share" / "neuralmind"))  # doctest: +SKIP
        '/home/user/.local/share/neuralmind'
    """
    default = str(Path.home() / ".local" / "share" / "neuralmind")
    if value is None or str(value).strip() == "":
        return default
    # Reject relative paths BEFORE resolve() — resolve() silently makes
    # relative paths absolute, hiding user error.
    if not Path(value).is_absolute():
        raise ValueError(f"Invalid data_dir: {value!r}. Must be an absolute path.")
    try:
        resolved = Path(value).resolve()
    except Exception as err:
        raise ValueError(f"Invalid data_dir: {value!r}. Must be a valid path.") from err
    home = Path.home().resolve()
    try:
        resolved.relative_to(home)
    except ValueError as err:
        raise ValueError(
            f"Invalid data_dir: {value!r}. Must be within user home {home!s}."
        ) from err
    return str(resolved)


def validate_seats(value: int | str | None) -> int:
    """Validate license seats.

    Args:
        value: The number of seats to validate.

    Returns:
        The validated seat count as an integer.

    Raises:
        ValueError: If ``value`` is not a non-negative integer.

    Example:
        >>> validate_seats(5)
        5
        >>> validate_seats(-1)
        Traceback (most recent call last):
            ...
        ValueError: Invalid seats: -1. Must be >= 0.
    """
    if value is None:
        return 0
    try:
        v = int(value)
    except (TypeError, ValueError) as err:
        raise ValueError(f"Invalid seats: {value!r}. Must be an integer.") from err
    if v < 0:
        raise ValueError(f"Invalid seats: {v}. Must be >= 0.")
    return v
