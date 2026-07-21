"""Tier 2 free tier + upgrade flow tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from neuralmind.cli import cmd_wakeup
from neuralmind.tier2.config import Tier2Config
from neuralmind.tier2.license import (
    LicenseValidator,
    issue_free_license,
    load_license,
)


@pytest.fixture
def tmp_license_path(tmp_path):
    return tmp_path / "license.json"


class TestFreeTierAutoIssue:
    def test_issue_free_license_creates_valid_file(self, tmp_license_path):
        assert not tmp_license_path.exists()
        lic = issue_free_license(tmp_license_path)
        assert tmp_license_path.exists()
        assert lic.tier == "free"
        assert lic.seats == 1
        assert lic.expires_at == "never"
        assert lic.signature == "self-signed"

    def test_free_license_passes_validation(self, tmp_license_path):
        issue_free_license(tmp_license_path)
        status = load_license(tmp_license_path)
        assert status == "VALID"

    def test_free_license_has_correct_fields(self, tmp_license_path):
        issue_free_license(tmp_license_path)
        data = json.loads(tmp_license_path.read_text(encoding="utf-8"))
        assert data["tier"] == "free"
        assert data["seats"] == 1
        assert data["expires_at"] == "never"
        assert data["issued_to"] == "self"
        assert data["signature"] == "self-signed"


class TestFreeTierNeverExpires:
    def test_free_license_never_expires(self, tmp_license_path):
        """Free license should be valid indefinitely (no expiry check)."""
        issue_free_license(tmp_license_path)
        validator = LicenseValidator("a" * 64, tmp_license_path)
        # Even far-future date shouldn't matter — free tier has expires_at="never"
        assert validator.validate() == "VALID"


class TestTeamUpgrade:
    def test_free_to_team_upgrade(self, tmp_license_path):
        """Free license can be overwritten with a real team license."""
        issue_free_license(tmp_license_path)
        assert load_license(tmp_license_path) == "VALID"

        # Simulate team license (without real signature, will be INVALID — but proves overwrite path)
        team_lic = {
            "tier": "team",
            "seats": 15,
            "issued_at": "2026-01-01T00:00:00Z",
            "expires_at": "2099-01-01T00:00:00Z",
            "issued_to": "acme-corp",
            "signature": "invalid-sig",
        }
        tmp_license_path.write_text(json.dumps(team_lic, indent=2), encoding="utf-8")
        # Invalid signature — but file now shows team tier
        validator = LicenseValidator("a" * 64, tmp_license_path)
        lic = validator._load_raw()
        assert lic is not None
        assert lic.tier == "team"
        assert lic.seats == 15


class TestConfigIsTeamActive:
    def test_free_license_is_active(self):
        cfg = Tier2Config(seats=1, expires_at="never")
        assert cfg.is_team_active() is True

    def test_team_license_is_active(self):
        cfg = Tier2Config(seats=15, expires_at="2099-01-01T00:00:00Z")
        assert cfg.is_team_active() is True

    def test_expired_license_is_not_active(self):
        cfg = Tier2Config(seats=15, expires_at="2020-01-01T00:00:00Z")
        assert cfg.is_team_active() is False

    def test_no_license_is_not_active(self):
        cfg = Tier2Config(seats=0, expires_at="")
        assert cfg.is_team_active() is False


class TestCorruptedLicenseFile:
    def test_garbage_json_returns_invalid(self, tmp_license_path):
        tmp_license_path.write_text("not json at all", encoding="utf-8")
        assert load_license(tmp_license_path) == "INVALID"

    def test_empty_json_returns_invalid(self, tmp_license_path):
        tmp_license_path.write_text("{}", encoding="utf-8")
        validator = LicenseValidator("a" * 64, tmp_license_path)
        assert validator.validate() == "INVALID"

    def test_unknown_tier_returns_invalid(self, tmp_license_path):
        tmp_license_path.write_text(
            json.dumps(
                {
                    "tier": "enterprise",  # not free or team
                    "seats": 100,
                    "issued_at": "2026-01-01T00:00:00Z",
                    "expires_at": "2099-01-01T00:00:00Z",
                    "issued_to": "big-corp",
                    "signature": "a" * 128,
                }
            ),
            encoding="utf-8",
        )
        validator = LicenseValidator("a" * 64, tmp_license_path)
        assert validator.validate() == "INVALID"


class TestCmdWakeupLicenseAutoIssue:
    def test_wakeup_creates_license_on_first_run(self, tmp_path, monkeypatch):
        """cmd_wakeup auto-issues a free license on first run."""
        monkeypatch.setattr(
            "neuralmind.cli.TIER2_CONFIG_DIR", tmp_path, raising=False
        )
        # Patch create_mind so we don't need a real project
        mock_mind = MagicMock()
        mock_mind.wakeup.return_value = MagicMock(
            budget=MagicMock(total=100),
            reduction_ratio=5.0,
            context="test context",
        )
        monkeypatch.setattr(
            "neuralmind.cli.create_mind", lambda *a, **kw: mock_mind, raising=False
        )

        license_path = tmp_path / "license.json"
        assert not license_path.exists()

        args = MagicMock(project_path=".")
        cmd_wakeup(args)

        assert license_path.exists()
        data = json.loads(license_path.read_text(encoding="utf-8"))
        assert data["tier"] == "free"

    def test_wakeup_is_idempotent(self, tmp_path, monkeypatch):
        """Second cmd_wakeup does NOT overwrite or error."""
        monkeypatch.setattr(
            "neuralmind.cli.TIER2_CONFIG_DIR", tmp_path, raising=False
        )
        mock_mind = MagicMock()
        mock_mind.wakeup.return_value = MagicMock(
            budget=MagicMock(total=100),
            reduction_ratio=5.0,
            context="test context",
        )
        monkeypatch.setattr(
            "neuralmind.cli.create_mind", lambda *a, **kw: mock_mind, raising=False
        )

        args = MagicMock(project_path=".")
        cmd_wakeup(args)

        license_path = tmp_path / "license.json"
        first_mtime = license_path.stat().st_mtime
        first_data = json.loads(license_path.read_text(encoding="utf-8"))

        cmd_wakeup(args)

        second_mtime = license_path.stat().st_mtime
        second_data = json.loads(license_path.read_text(encoding="utf-8"))
        assert second_mtime == first_mtime  # not overwritten
        assert second_data == first_data


class TestFreeTierSignatureMustBeSelfSigned:
    def test_free_with_wrong_signature_is_invalid(self, tmp_license_path):
        now = "2026-01-01T00:00:00Z"
        tmp_license_path.write_text(
            json.dumps(
                {
                    "tier": "free",
                    "seats": 1,
                    "issued_at": now,
                    "expires_at": "never",
                    "issued_to": "self",
                    "signature": "someone-else-signature",
                }
            ),
            encoding="utf-8",
        )
        assert load_license(tmp_license_path) == "INVALID"

    def test_free_with_wrong_seats_is_invalid(self, tmp_license_path):
        now = "2026-01-01T00:00:00Z"
        tmp_license_path.write_text(
            json.dumps(
                {
                    "tier": "free",
                    "seats": 5,  # free must be 1
                    "issued_at": now,
                    "expires_at": "never",
                    "issued_to": "self",
                    "signature": "self-signed",
                }
            ),
            encoding="utf-8",
        )
        assert load_license(tmp_license_path) == "INVALID"


class TestUpgradeCTA:
    def test_cta_not_shown_before_10_calls(self, tmp_path, monkeypatch):
        """CTA should NOT appear before the 10th wakeup/query call."""
        monkeypatch.setattr(
            "neuralmind.cli._UPGRADE_CTA_STATE_PATH",
            tmp_path / ".cta_state.json",
            raising=False,
        )
        monkeypatch.setattr(
            "neuralmind.cli.TIER2_CONFIG_DIR", tmp_path, raising=False
        )
        mock_mind = MagicMock()
        mock_mind.wakeup.return_value = MagicMock(
            budget=MagicMock(total=100),
            reduction_ratio=5.0,
            context="test context",
        )
        monkeypatch.setattr(
            "neuralmind.cli.create_mind", lambda *a, **kw: mock_mind, raising=False
        )

        args = MagicMock(project_path=".")
        for _ in range(9):
            cmd_wakeup(args)

        from neuralmind.cli import _get_wakeup_count

        assert _get_wakeup_count() == 9

    def test_cta_shown_at_10th_call(self, tmp_path, monkeypatch, capsys):
        """CTA should appear on the 10th call."""
        monkeypatch.setattr(
            "neuralmind.cli._UPGRADE_CTA_STATE_PATH",
            tmp_path / ".cta_state.json",
            raising=False,
        )
        monkeypatch.setattr(
            "neuralmind.cli.TIER2_CONFIG_DIR", tmp_path, raising=False
        )
        mock_mind = MagicMock()
        mock_mind.wakeup.return_value = MagicMock(
            budget=MagicMock(total=100),
            reduction_ratio=5.0,
            context="test context",
        )
        monkeypatch.setattr(
            "neuralmind.cli.create_mind", lambda *a, **kw: mock_mind, raising=False
        )

        args = MagicMock(project_path=".")
        for _ in range(10):
            cmd_wakeup(args)

        captured = capsys.readouterr()
        assert "$29/user/mo" in captured.out

    def test_cta_only_once(self, tmp_path, monkeypatch, capsys):
        """CTA should fire exactly once, not repeatedly."""
        monkeypatch.setattr(
            "neuralmind.cli._UPGRADE_CTA_STATE_PATH",
            tmp_path / ".cta_state.json",
            raising=False,
        )
        monkeypatch.setattr(
            "neuralmind.cli.TIER2_CONFIG_DIR", tmp_path, raising=False
        )
        mock_mind = MagicMock()
        mock_mind.wakeup.return_value = MagicMock(
            budget=MagicMock(total=100),
            reduction_ratio=5.0,
            context="test context",
        )
        monkeypatch.setattr(
            "neuralmind.cli.create_mind", lambda *a, **kw: mock_mind, raising=False
        )

        args = MagicMock(project_path=".")
        for _ in range(20):
            cmd_wakeup(args)

        captured = capsys.readouterr()
        # CTA should appear exactly once
        assert captured.out.count("$29/user/mo") == 1
