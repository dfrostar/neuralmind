# test_license_validator_anti_tamper.py
"""LicenseValidator anti-tamper DI tests (neuralmind repo).

These tests use a mock anti_tamper (no autopilot dependency).
The real AntiTamper lives in the autopilot repo; integration tests
live there too.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from neuralmind.tier2.license import LicenseValidator, issue_free_license


class TestLicenseValidatorAntiTamper:
    """Verify LicenseValidator anti_tamper injection works."""

    def test_anti_tamper_di_returns_tampered_on_regression(
        self, tmp_path: Path
    ) -> None:
        """When anti_tamper.check_regression() returns True, validate() returns TAMPERED."""
        lic_path = tmp_path / "license.json"
        issue_free_license(lic_path)

        mock_at = MagicMock()
        mock_at.check_regression.return_value = True

        validator = LicenseValidator("0" * 64, lic_path, anti_tamper=mock_at)
        assert validator.validate() == "TAMPERED"

    def test_anti_tamper_records_on_success(self, tmp_path: Path) -> None:
        """Successful validate() calls record_validation()."""
        lic_path = tmp_path / "license.json"
        issue_free_license(lic_path)

        mock_at = MagicMock()
        mock_at.check_regression.return_value = False

        validator = LicenseValidator("0" * 64, lic_path, anti_tamper=mock_at)
        assert validator.validate() == "VALID"

        mock_at.record_validation.assert_called_once()
        call_kwargs = mock_at.record_validation.call_args
        # Should pass license_id and validated_at
        assert "license_id" in call_kwargs.kwargs
        assert "validated_at" in call_kwargs.kwargs

    def test_backward_compat_no_anti_tamper(self, tmp_path: Path) -> None:
        """Without anti_tamper, validate() works as before."""
        lic_path = tmp_path / "license.json"
        issue_free_license(lic_path)

        validator = LicenseValidator("0" * 64, lic_path)
        assert validator.validate() == "VALID"

    def test_tampers_literal_in_license_status(self) -> None:
        """LicenseStatus Literal includes TAMPERED."""
        from neuralmind.tier2.license import LicenseStatus

        assert "TAMPERED" in LicenseStatus.__args__

    def test_license_validator_with_anti_tamper_none(self, tmp_path: Path) -> None:
        """Passing anti_tamper=None is equivalent to omitting it."""
        lic_path = tmp_path / "license.json"
        issue_free_license(lic_path)

        validator = LicenseValidator("0" * 64, lic_path, anti_tamper=None)
        assert validator.validate() == "VALID"

    def test_anti_tamper_check_regression_not_called_when_none(
        self, tmp_path: Path
    ) -> None:
        """If anti_tamper is None, check_regression is never called."""
        lic_path = tmp_path / "license.json"
        issue_free_license(lic_path)

        mock_at = MagicMock()
        mock_at.check_regression.return_value = True

        validator = LicenseValidator("0" * 64, lic_path, anti_tamper=None)
        validator.validate()
        mock_at.check_regression.assert_not_called()
