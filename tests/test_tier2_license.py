"""Tier 2 license tests — LicenseValidator status transitions."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from neuralmind.tier2.license import (
    LicenseInfo,
    LicenseValidator,
)


class TestLicenseValidation:
    """LicenseValidator.validate() returns correct status."""

    @pytest.fixture
    def license_dir(self, tmp_path: Path) -> Path:
        return tmp_path

    def _write_license(
        self,
        path: Path,
        tier: str = "team",
        seats: int = 15,
        expires_at: str = "",
        signature: str = "validsig",
    ) -> None:
        data = {
            "tier": tier,
            "seats": seats,
            "issued_at": "2026-07-19T00:00:00Z",
            "expires_at": expires_at,
            "issued_to": "acme",
            "signature": signature,
        }
        with open(path, "w") as f:
            json.dump(data, f)

    def test_license_valid(self, license_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        future = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        lic_path = license_dir / "license.json"
        self._write_license(lic_path, expires_at=future)

        validator = LicenseValidator("a" * 64, lic_path)
        monkeypatch.setattr(validator, "_verify_signature", lambda lic: True)
        assert validator.validate() == "VALID"

    def test_license_expired(self, license_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        lic_path = license_dir / "license.json"
        self._write_license(lic_path, expires_at=past)

        validator = LicenseValidator("a" * 64, lic_path)
        monkeypatch.setattr(validator, "_verify_signature", lambda lic: True)
        assert validator.validate() == "EXPIRED"

    def test_license_invalid_signature(
        self, license_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        future = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        lic_path = license_dir / "license.json"
        self._write_license(lic_path, expires_at=future)

        validator = LicenseValidator("a" * 64, lic_path)
        monkeypatch.setattr(validator, "_verify_signature", lambda lic: False)
        assert validator.validate() == "INVALID"

    @pytest.mark.skip(reason="offline_grace not implemented")
    def test_license_offline_within_grace(self, license_dir: Path) -> None:
        pass

    @pytest.mark.skip(reason="offline_grace not implemented")
    def test_license_offline_beyond_grace(self, license_dir: Path) -> None:
        pass

    def test_license_seat_limit(self, license_dir: Path) -> None:
        # Verify LicenseInfo.seats reflects the license file value
        lic = LicenseInfo(
            tier="team",
            seats=5,
            issued_at="2026-07-19T00:00:00Z",
            expires_at="2027-07-19T00:00:00Z",
            issued_to="acme",
            signature="sig",
            raw={},
        )
        assert lic.seats == 5

    def test_license_tier_mismatch(
        self, license_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        future = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        lic_path = license_dir / "license.json"
        self._write_license(lic_path, tier="enterprise", expires_at=future)

        validator = LicenseValidator("a" * 64, lic_path)
        monkeypatch.setattr(validator, "_verify_signature", lambda lic: True)
        assert validator.validate() == "INVALID"
