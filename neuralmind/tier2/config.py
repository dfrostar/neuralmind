"""config.py — Tier 2 YAML configuration schema and I/O.

Tier 2 config lives at ~/.config/neuralmind/tier2.yaml by default.  All values
are additive to the MIT product — no MIT paths are altered.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Literal

import yaml

log = logging.getLogger(__name__)

TIER2_CONFIG_DIR = Path(os.environ.get("NEURALMIND_CONFIG_DIR", Path.home() / ".config" / "neuralmind"))
DEFAULT_CONFIG_PATH = TIER2_CONFIG_DIR / "tier2.yaml"

PublishingScope = Literal["personal", "shared", "both"]


@dataclass
class GovernanceConfig:
    enabled: bool = True
    publishing_scope: PublishingScope = "both"
    weight_threshold: float = 0.1
    auto_decay_half_life: float = 30.0  # days
    admin_emails: list[str] = field(default_factory=list)


@dataclass
class SelfHostedConfig:
    enabled: bool = False
    data_dir: str = str(Path.home() / ".local" / "share" / "neuralmind")
    bind_address: str = "127.0.0.1"
    port: int = 8765
    offline_grace_days: int = 30


@dataclass
class Tier2Config:
    tier: str = "team"
    license_file: str = str(TIER2_CONFIG_DIR / "license.json")
    audit_db: str = str(TIER2_CONFIG_DIR / "audit.db")
    seats: int = 0  # license seat limit; 0 = no license
    expires_at: str = ""  # ISO date, from license
    issued_to: str = ""
    governance: GovernanceConfig = field(default_factory=GovernanceConfig)
    self_hosted: SelfHostedConfig = field(default_factory=SelfHostedConfig)

    def is_team_active(self) -> bool:
        """True when license present and not expired."""
        if not self.expires_at:
            return False
        from datetime import datetime, timezone
        try:
            exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) <= exp
        except ValueError:
            return False


def load_config(path: Path | None = None) -> Tier2Config:
    """Load Tier 2 config from YAML. Returns defaults if file missing."""
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    if not p.exists():
        return Tier2Config(license_file=str(p.with_name("license.json")), audit_db=str(p.with_name("audit.db")))
    try:
        with p.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return Tier2Config()
    return _from_dict(raw)


def save_config(config: Tier2Config, path: Path | None = None) -> Path:
    """Serialize config to YAML. Creates parent dirs if missing."""
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    data = _to_dict(config)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=True)
    return p


def _from_dict(raw: dict[str, Any]) -> Tier2Config:
    gov_raw = raw.get("governance", {})
    sh_raw = raw.get("self_hosted", {})
    return Tier2Config(
        tier=raw.get("tier", "team"),
        license_file=raw.get("license_file", str(TIER2_CONFIG_DIR / "license.json")),
        audit_db=raw.get("audit_db", str(TIER2_CONFIG_DIR / "audit.db")),
        seats=int(raw.get("seats", 0)),
        expires_at=raw.get("expires_at", ""),
        issued_to=raw.get("issued_to", ""),
        governance=GovernanceConfig(
            enabled=gov_raw.get("enabled", True),
            publishing_scope=gov_raw.get("publishing_scope", "both"),
            weight_threshold=float(gov_raw.get("weight_threshold", 0.1)),
            auto_decay_half_life=float(gov_raw.get("auto_decay_half_life", 30.0)),
            admin_emails=list(gov_raw.get("admin_emails", [])),
        ),
        self_hosted=SelfHostedConfig(
            enabled=sh_raw.get("enabled", False),
            data_dir=sh_raw.get("data_dir", str(Path.home() / ".local" / "share" / "neuralmind")),
            bind_address=sh_raw.get("bind_address", "127.0.0.1"),
            port=int(sh_raw.get("port", 8765)),
            offline_grace_days=int(sh_raw.get("offline_grace_days", 30)),
        ),
    )


def _to_dict(config: Tier2Config) -> dict[str, Any]:
    return {
        "tier": config.tier,
        "license_file": config.license_file,
        "audit_db": config.audit_db,
        "seats": config.seats,
        "expires_at": config.expires_at,
        "issued_to": config.issued_to,
        "governance": asdict(config.governance),
        "self_hosted": {**{k: v for k, v in asdict(config.self_hosted).items()}},
    }


def validate_scope(scope: str) -> PublishingScope:
    """Validate publishing scope string. Raises ValueError on invalid."""
    if scope not in ("personal", "shared", "both"):
        raise ValueError(f"Invalid publishing_scope: {scope!r}. Must be 'personal', 'shared', or 'both'.")
    return scope  # type: ignore[return-value]


def validate_threshold(value: float) -> float:
    """Validate weight threshold: 0.0 ≤ value ≤ 1.0. Raises ValueError."""
    if not isinstance(value, (int, float)) or value < 0.0 or value > 1.0:
        raise ValueError(f"Invalid weight_threshold: {value}. Must be 0.0–1.0.")
    return float(value)


def validate_half_life(value: float) -> float:
    """Validate auto-decay half-life: must be > 0. Raises ValueError."""
    if not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"Invalid half_life: {value}. Must be > 0.")
    return float(value)
