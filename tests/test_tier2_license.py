"""Tier 2 license tests — LicenseValidator status transitions."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from neuralmind.tier2.license import (
    GRACE_DAYS,
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
        past = (datetime.now(timezone.utc) - timedelta(days=GRACE_DAYS + 1)).isoformat()
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

    def test_grace_is_the_agreements_30_days(self) -> None:
        """License agreement §4.2 grants a fixed 30-day grace period."""
        assert GRACE_DAYS == 30

    @pytest.mark.parametrize(
        ("expired_days_ago", "last_validation", "expected"),
        [
            # Within 30 days of expiry: grace, whenever it last ran.
            (5, 3, "OFFLINE_OK"),
            (25, 45, "OFFLINE_OK"),  # last ran 20 days before expiry
            (5, None, "OFFLINE_OK"),  # no validation on record
            (5, "not a timestamp", "OFFLINE_OK"),
            (29, 1, "OFFLINE_OK"),
            # Grace ends 30 days after expiry, however recently it ran.
            (31, 1, "EXPIRED"),
            (31, None, "EXPIRED"),
            # A validation recorded in the future: the clock was set back.
            (5, -30, "EXPIRED"),
        ],
        ids=[
            "recent-validation",
            "validated-20-days-before-expiry",
            "no-record",
            "unreadable-record",
            "day-29",
            "day-31",
            "day-31-no-record",
            "clock-set-back",
        ],
    )
    def test_license_grace_runs_30_days_from_expiry(
        self,
        license_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        expired_days_ago: int,
        last_validation: int | str | None,
        expected: str,
    ) -> None:
        """Expired license → OFFLINE_OK for 30 days after expires_at, then EXPIRED.

        ``last_validation`` is the ``.last_valid`` sidecar: days ago (negative
        is the future), raw file text, or None for no sidecar.
        """
        now = datetime.now(timezone.utc)
        lic_path = license_dir / "license.json"
        self._write_license(
            lic_path, expires_at=(now - timedelta(days=expired_days_ago)).isoformat()
        )

        validator = LicenseValidator("a" * 64, lic_path)
        monkeypatch.setattr(validator, "_verify_signature", lambda lic: True)

        sidecar = lic_path.with_suffix(".last_valid")
        if isinstance(last_validation, int):
            sidecar.write_text((now - timedelta(days=last_validation)).isoformat())
        elif isinstance(last_validation, str):
            sidecar.write_text(last_validation)

        assert validator.validate() == expected

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
