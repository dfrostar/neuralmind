"""Tests for EULA clickwrap functionality."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuralmind.onboarding import _cmd_onboarding_eula


class Args:
    def __init__(self, config_path: str):
        self.quick = True
        self.config_path = config_path


class TestEULA:
    def test_eula_auto_accepted_quick_mode(self, tmp_path):
        """In quick mode, EULA is auto-accepted."""
        config_path = tmp_path / "tier2.yaml"
        license_path = tmp_path / "license.json"
        config_path.write_text(f"license_file: {license_path}\ntier: team\nseats: 5\n")

        result = _cmd_onboarding_eula(Args(str(config_path)))
        assert result == 0

    def test_eula_creates_acceptance_file(self, tmp_path):
        """EULA acceptance creates a sidecar file."""
        config_path = tmp_path / "tier2.yaml"
        license_path = tmp_path / "license.json"
        config_path.write_text(f"license_file: {license_path}\ntier: team\nseats: 5\n")

        _cmd_onboarding_eula(Args(str(config_path)))
        eula_path = license_path.with_suffix(".eula_accepted")
        assert eula_path.exists()

    def test_eula_skipped_if_already_accepted(self, tmp_path):
        """EULA step is skipped if already accepted."""
        config_path = tmp_path / "tier2.yaml"
        license_path = tmp_path / "license.json"
        eula_path = license_path.with_suffix(".eula_accepted")
        config_path.write_text(f"license_file: {license_path}\ntier: team\nseats: 5\n")
        eula_path.write_text(json.dumps({
            "accepted_at": "2026-01-01T00:00:00+00:00",
            "agreement_version": "1.0",
        }))

        result = _cmd_onboarding_eula(Args(str(config_path)))
        assert result == 0
