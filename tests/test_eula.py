"""Tests for EULA clickwrap functionality."""

from __future__ import annotations

import json

from neuralmind.onboarding import _cmd_onboarding_eula


class TestEULA:
    def test_eula_auto_accepted_quick_mode(self, tmp_path):
        """In quick mode, EULA is auto-accepted."""
        config_path = tmp_path / "tier2.yaml"
        config_path.write_text(f"license_file: {tmp_path / 'license.json'}")

        class Args:
            quick = True
            config_path = str(config_path)

        result = _cmd_onboarding_eula(Args())
        assert result == 0

    def test_eula_creates_acceptance_file(self, tmp_path):
        """EULA acceptance creates a sidecar file."""
        config_path = tmp_path / "tier2.yaml"
        lic_path = tmp_path / "license.json"
        config_path.write_text(f"license_file: {lic_path}")

        class Args:
            quick = True
            config_path = str(config_path)

        _cmd_onboarding_eula(Args())
        eula_path = lic_path.with_suffix(".eula_accepted")
        assert eula_path.exists()
        data = json.loads(eula_path.read_text())
        assert "accepted_at" in data
        assert data["agreement_version"] == "1.0"

    def test_eula_skipped_if_already_accepted(self, tmp_path):
        """EULA step is skipped if already accepted."""
        config_path = tmp_path / "tier2.yaml"
        lic_path = tmp_path / "license.json"
        eula_path = lic_path.with_suffix(".eula_accepted")
        config_path.write_text(f"license_file: {lic_path}")
        eula_path.write_text(
            json.dumps(
                {
                    "accepted_at": "2026-01-01T00:00:00+00:00",
                    "agreement_version": "1.0",
                }
            )
        )

        class Args:
            quick = True
            config_path = str(config_path)

        result = _cmd_onboarding_eula(Args())
        assert result == 0
