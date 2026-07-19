"""Tier 2 config tests — Tier2Config dataclass, validation, YAML roundtrip."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from neuralmind.tier2.config import (
    GovernanceConfig,
    PublishingScope,
    SelfHostedConfig,
    Tier2Config,
    load_config,
    save_config,
    validate_half_life,
    validate_scope,
    validate_threshold,
)


class TestTier2ConfigDefaults:
    """Tier2Config dataclass defaults are correct."""

    def test_config_default_values(self) -> None:
        cfg = Tier2Config()
        assert cfg.tier == "team"
        assert cfg.seats == 0
        assert cfg.governance.enabled is True
        assert cfg.governance.publishing_scope == "both"
        assert cfg.governance.weight_threshold == 0.1
        assert cfg.governance.auto_decay_half_life == 30.0


class TestTier2ConfigIO:
    """YAML load/save roundtrip."""

    def test_config_load_from_yaml(self, tmp_path: Path) -> None:
        data = {
            "tier": "team",
            "seats": 10,
            "expires_at": "2027-01-01T00:00:00Z",
            "issued_to": "acme",
            "governance": {
                "enabled": True,
                "publishing_scope": "shared",
                "weight_threshold": 0.5,
                "auto_decay_half_life": 60.0,
                "admin_emails": ["<EMAIL>"],
            },
        }
        yaml_path = tmp_path / "tier2.yaml"
        with open(yaml_path, "w") as f:
            yaml.safe_dump(data, f)

        cfg = load_config(yaml_path)
        assert cfg.tier == "team"
        assert cfg.seats == 10
        assert cfg.expires_at == "2027-01-01T00:00:00Z"
        assert cfg.issued_to == "acme"
        assert cfg.governance.enabled is True
        assert cfg.governance.publishing_scope == "shared"
        assert cfg.governance.weight_threshold == 0.5
        assert cfg.governance.auto_decay_half_life == 60.0
        assert cfg.governance.admin_emails == ["<EMAIL>"]

    def test_config_save_roundtrip(self, tmp_path: Path) -> None:
        cfg = Tier2Config(
            tier="team",
            seats=5,
            expires_at="2027-06-01T00:00:00Z",
            issued_to="test-org",
            governance=GovernanceConfig(
                enabled=True,
                publishing_scope="shared",
                weight_threshold=0.25,
                admin_emails=["<EMAIL>"],
            ),
        )
        yaml_path = tmp_path / "tier2.yaml"
        save_config(cfg, yaml_path)

        loaded = load_config(yaml_path)
        assert loaded == cfg


class TestTier2ConfigValidation:
    """Validation helpers reject invalid inputs."""

    def test_config_invalid_scope(self) -> None:
        with pytest.raises(ValueError, match="Invalid publishing_scope"):
            validate_scope("public")

    def test_config_invalid_threshold(self) -> None:
        with pytest.raises(ValueError, match="Invalid weight_threshold"):
            validate_threshold(1.5)

    def test_config_negative_half_life(self) -> None:
        with pytest.raises(ValueError, match="Invalid half_life"):
            validate_half_life(-1)
