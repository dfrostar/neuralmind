"""Tier 2 config tests — Tier2Config dataclass, validation, YAML roundtrip."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from neuralmind.tier2.config import (
    GovernanceConfig,
    Tier2Config,
    load_config,
    save_config,
    validate_data_dir,
    validate_half_life,
    validate_scope,
    validate_threshold,
)


class TestTier2ConfigDefaults:
    """Tier2Config dataclass defaults are correct."""

    def test_config_default_values(self) -> None:
        cfg = Tier2Config()
        assert cfg.tier == "free"
        assert cfg.seats == 1
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


class TestTier2ConfigLoadValidation:
    """Validators fire during _from_dict — crafted YAML is rejected."""

    def test_invalid_scope_in_yaml_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "tier2.yaml"
        p.write_text("governance:\n  publishing_scope: telepathy\n")
        with pytest.raises(ValueError, match="Invalid publishing_scope"):
            load_config(p)

    def test_invalid_threshold_in_yaml_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "tier2.yaml"
        p.write_text("governance:\n  weight_threshold: 99.0\n")
        with pytest.raises(ValueError, match="Invalid weight_threshold"):
            load_config(p)

    def test_negative_half_life_in_yaml_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "tier2.yaml"
        p.write_text("governance:\n  auto_decay_half_life: -5\n")
        with pytest.raises(ValueError, match="Invalid half_life"):
            load_config(p)

    def test_invalid_port_in_yaml_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "tier2.yaml"
        p.write_text("self_hosted:\n  port: 99999\n")
        with pytest.raises(ValueError, match="Invalid port"):
            load_config(p)

    def test_negative_seats_in_yaml_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "tier2.yaml"
        p.write_text("seats: -3\n")
        with pytest.raises(ValueError, match="Invalid seats"):
            load_config(p)

    def test_data_dir_non_absolute_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid data_dir"):
            validate_data_dir("relative/path")

    def test_data_dir_valid_absolute(self) -> None:
        home = Path.home()
        assert str(home / "foo") == validate_data_dir(str(home / "foo"))


class TestSanityUnchanged:
    """Existing invariants still hold after patch."""

    def test_defaults_still_clean(self) -> None:
        a = Tier2Config()
        b = Tier2Config()
        assert a.governance.admin_emails is not b.governance.admin_emails
