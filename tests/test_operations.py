"""Tests for license operations (issue, renew, revoke, partners)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from neuralmind.tier2.operations import LicenseOperations, PartnerOperations


@pytest.fixture
def temp_storage(tmp_path):
    """Create a temporary storage directory."""
    return tmp_path / ".neuralmind"


@pytest.fixture
def private_key():
    """Generate a test Ed25519 private key."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv = Ed25519PrivateKey.generate()
    return priv.private_bytes_raw().hex()


@pytest.fixture
def ops(temp_storage, private_key):
    """Create LicenseOperations instance."""
    return LicenseOperations(private_key, temp_storage)


class TestIssueLicense:
    def test_issue_basic(self, ops):
        """Issue a basic team license."""
        lic = ops.issue_team_license("Test Corp", 5, 12)
        assert lic.tier == "team"
        assert lic.seats == 5
        assert lic.issued_to == "Test Corp"
        assert lic.expires_at != "never"
        assert lic.signature != ""

    def test_issue_with_output(self, ops, temp_storage):
        """Issue license with explicit output path."""
        output = temp_storage / "test-corp.json"
        lic = ops.issue_team_license("Test Corp", 10, 6, output_path=output)
        assert output.exists()
        data = json.loads(output.read_text())
        assert data["tier"] == "team"
        assert data["seats"] == 10

    def test_issue_invalid_seats(self, ops):
        """Reject zero or negative seats."""
        with pytest.raises(ValueError, match="seats must be positive"):
            ops.issue_team_license("Test", 0, 12)
        with pytest.raises(ValueError, match="seats must be positive"):
            ops.issue_team_license("Test", -5, 12)

    def test_issue_invalid_term(self, ops):
        """Reject invalid term lengths."""
        with pytest.raises(ValueError, match="term_months must be"):
            ops.issue_team_license("Test", 5, 5)
        with pytest.raises(ValueError, match="term_months must be"):
            ops.issue_team_license("Test", 5, 7)

    def test_issue_customers_updated(self, ops):
        """Verify customers.yaml is updated after issuance."""
        ops.issue_team_license("Acme Corp", 15, 12)
        customers = ops._load_customers()
        assert "Acme Corp" in customers["customers"]
        assert customers["customers"]["Acme Corp"]["seats"] == 15

    def test_issue_audit_logged(self, ops, temp_storage):
        """Verify audit log entry is created."""
        ops.issue_team_license("Acme", 5, 12)
        audit_path = temp_storage / "audit_log.jsonl"
        assert audit_path.exists()
        entry = json.loads(audit_path.read_text().strip())
        assert entry["action"] == "issue"
        assert entry["customer"] == "Acme"


class TestTermArithmetic:
    """Terms are sold in calendar months and must land on the calendar."""

    def test_annual_term_is_a_calendar_year(self, ops):
        """A 12-month term expires a year out, not 360 days out."""
        lic = ops.issue_team_license("Acme", 5, 12)
        issued = datetime.fromisoformat(lic.issued_at)
        expires = datetime.fromisoformat(lic.expires_at)
        assert expires.year == issued.year + 1
        assert (expires.month, expires.day) == (issued.month, issued.day)

    @pytest.mark.parametrize("term", [1, 3, 6, 12, 24, 36])
    def test_every_offered_term_lands_on_the_calendar(self, ops, term):
        """Each term the CLI accepts advances by exactly that many months."""
        lic = ops.issue_team_license(f"Corp{term}", 5, term)
        issued = datetime.fromisoformat(lic.issued_at)
        expires = datetime.fromisoformat(lic.expires_at)
        months = (expires.year - issued.year) * 12 + (expires.month - issued.month)
        assert months == term

    def test_month_end_issue_date_clamps(self):
        """31 Jan + 1 month is 28 Feb, not 3 March."""
        from neuralmind.tier2.operations import _add_months

        assert _add_months(datetime(2027, 1, 31, tzinfo=timezone.utc), 1) == datetime(
            2027, 2, 28, tzinfo=timezone.utc
        )
        assert _add_months(datetime(2028, 1, 31, tzinfo=timezone.utc), 1) == datetime(
            2028, 2, 29, tzinfo=timezone.utc
        )

    def test_term_price_covers_the_whole_term(self):
        """Every offered term bills the flat monthly rate per month."""
        from neuralmind.tier2.pricing import DEFAULT_PRICING, calculate_price

        for term in (1, 3, 6, 12, 24, 36):
            assert calculate_price(DEFAULT_PRICING, "team", 5, term) == 29.00 * term * 5
        assert calculate_price(DEFAULT_PRICING, "free", 1, 12) == 0.0


class TestExpiringLicenses:
    """Renewal alerting: nothing else in the system watches expiry dates."""

    NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)

    def _seed(self, ops, **customers):
        """Write customer records directly, with controlled expiry dates."""
        data = {"customers": {}}
        for name, (days, status) in customers.items():
            data["customers"][name] = {
                "customer_id": f"cus_{name}",
                "license_id": f"lic_{name}",
                "seats": 10,
                "tier": "team",
                "status": status,
                "expires_at": (self.NOW + timedelta(days=days)).isoformat(),
            }
        ops._save_customers(data)

    def test_buckets_by_urgency(self, ops):
        """Expired, expiring-within-window, and healthy are separated."""
        self._seed(
            ops,
            lapsed=(-10, "active"),
            soon=(20, "active"),
            healthy=(300, "active"),
        )
        r = ops.list_expiring_licenses(within_days=60, now=self.NOW)
        assert [e["customer"] for e in r["expired"]] == ["lapsed"]
        assert [e["customer"] for e in r["expiring"]] == ["soon"]
        assert r["needs_attention"] == 2
        assert r["total_active"] == 3

    def test_revoked_excluded(self, ops):
        """A revoked licence cannot be renewed, so it is not a renewal lead."""
        self._seed(ops, gone=(-5, "revoked"), live=(10, "active"))
        r = ops.list_expiring_licenses(within_days=60, now=self.NOW)
        assert r["total_active"] == 1
        assert all(e["customer"] != "gone" for e in r["expired"] + r["expiring"])

    def test_sorted_most_urgent_first(self, ops):
        """Ordering is by remaining days so the top line is the worst case."""
        self._seed(ops, a=(50, "active"), b=(5, "active"), c=(30, "active"))
        r = ops.list_expiring_licenses(within_days=60, now=self.NOW)
        assert [e["customer"] for e in r["expiring"]] == ["b", "c", "a"]

    def test_window_is_respected(self, ops):
        """A licence outside the window is not reported."""
        self._seed(ops, later=(90, "active"))
        assert ops.list_expiring_licenses(within_days=60, now=self.NOW)["needs_attention"] == 0
        assert ops.list_expiring_licenses(within_days=120, now=self.NOW)["needs_attention"] == 1

    def test_unreadable_expiry_is_surfaced_not_swallowed(self, ops):
        """A record we cannot date is an operator problem, not a silent skip."""
        ops._save_customers(
            {"customers": {"broken": {"seats": 5, "status": "active", "expires_at": "soon-ish"}}}
        )
        r = ops.list_expiring_licenses(now=self.NOW)
        assert [e["customer"] for e in r["unknown"]] == ["broken"]
        assert r["needs_attention"] == 1

    def test_never_expires_is_not_an_alert(self, ops):
        """A perpetual licence is healthy, not overdue."""
        ops._save_customers(
            {"customers": {"perpetual": {"seats": 1, "status": "active", "expires_at": "never"}}}
        )
        r = ops.list_expiring_licenses(now=self.NOW)
        assert r["needs_attention"] == 0
        assert r["total_active"] == 1

    def test_naive_timestamp_treated_as_utc(self, ops):
        """Older records without a timezone must not raise on comparison."""
        ops._save_customers(
            {
                "customers": {
                    "legacy": {"seats": 5, "status": "active", "expires_at": "2026-06-20T00:00:00"}
                }
            }
        )
        r = ops.list_expiring_licenses(within_days=60, now=self.NOW)
        assert [e["customer"] for e in r["expiring"]] == ["legacy"]

    def test_empty_store_is_all_clear(self, ops):
        """No customers yet is a clean result, not an error."""
        r = ops.list_expiring_licenses(now=self.NOW)
        assert r["needs_attention"] == 0
        assert r["total_active"] == 0

    def test_day_count_truncates_toward_zero(self, ops):
        """4.1 days past due is 4 days ago, not 5; 17.9 left is 17, not 18."""
        ops._save_customers(
            {
                "customers": {
                    "past": {
                        "seats": 1,
                        "status": "active",
                        "expires_at": (self.NOW - timedelta(days=4, hours=2)).isoformat(),
                    },
                    "future": {
                        "seats": 1,
                        "status": "active",
                        "expires_at": (self.NOW + timedelta(days=17, hours=22)).isoformat(),
                    },
                }
            }
        )
        r = ops.list_expiring_licenses(within_days=60, now=self.NOW)
        assert r["expired"][0]["days_remaining"] == -4
        assert r["expiring"][0]["days_remaining"] == 17

    def test_lapsed_hours_ago_is_expired_not_due(self, ops):
        """A licence three hours past due must not read as a 0-day renewal."""
        ops._save_customers(
            {
                "customers": {
                    "justlapsed": {
                        "seats": 1,
                        "status": "active",
                        "expires_at": (self.NOW - timedelta(hours=3)).isoformat(),
                    }
                }
            }
        )
        r = ops.list_expiring_licenses(now=self.NOW)
        assert [e["customer"] for e in r["expired"]] == ["justlapsed"]
        assert r["expiring"] == []

    def test_negative_window_rejected(self, ops):
        with pytest.raises(ValueError, match="within_days"):
            ops.list_expiring_licenses(within_days=-1)

    def test_needs_no_issuer_key(self, temp_storage):
        """Alerting is read-only, so a scheduler can run it without the key."""
        readonly = LicenseOperations("", temp_storage)
        assert readonly.list_expiring_licenses(now=self.NOW)["needs_attention"] == 0


class TestRenewLicense:
    def test_renew_extends_expiry(self, ops):
        """Renewal extends expires_at by term months."""
        lic1 = ops.issue_team_license("Acme", 5, 12)
        old_expiry = lic1.expires_at
        lic2 = ops.renew_license("Acme", 12)
        assert lic2.expires_at > old_expiry

    def test_renew_extends_by_calendar_months(self, ops):
        """Renewal runs from the old expiry, by calendar months."""
        lic1 = ops.issue_team_license("Acme", 5, 12)
        old_expiry = datetime.fromisoformat(lic1.expires_at)
        lic2 = ops.renew_license("Acme", 12)
        new_expiry = datetime.fromisoformat(lic2.expires_at)
        assert new_expiry.year == old_expiry.year + 1
        assert (new_expiry.month, new_expiry.day) == (old_expiry.month, old_expiry.day)

    def test_renew_nonexistent(self, ops):
        """Renewal fails for non-existent customer."""
        with pytest.raises(ValueError, match="not found"):
            ops.renew_license("NonExistent", 12)


class TestRevokeLicense:
    def test_revoke_sets_expiry_to_now(self, ops):
        """Revocation sets expires_at to current time."""
        ops.issue_team_license("Acme", 5, 12)
        lic = ops.revoke_license("Acme", "non-payment")
        # Expires at should be very close to now
        from datetime import datetime, timezone

        exp = datetime.fromisoformat(lic.expires_at)
        now = datetime.now(timezone.utc)
        assert (now - exp).total_seconds() < 5

    def test_revoke_nonexistent(self, ops):
        """Revocation fails for non-existent customer."""
        with pytest.raises(ValueError, match="not found"):
            ops.revoke_license("NonExistent", "test")


class TestLicenseStatus:
    def test_status_valid(self, ops):
        """Get status for active license."""
        ops.issue_team_license("Acme", 10, 12)
        status = ops.get_license_status("Acme")
        assert status["customer"] == "Acme"
        assert status["seats"] == 10
        assert status["status"] == "active"
        assert status["days_remaining"] > 300

    def test_status_nonexistent(self, ops):
        """Status for non-existent customer."""
        status = ops.get_license_status("NonExistent")
        assert "error" in status


class TestListLicenses:
    def test_list_all(self, ops):
        """List all customer licenses."""
        ops.issue_team_license("Acme", 5, 12)
        ops.issue_team_license("Globex", 10, 6)
        licenses = ops.list_customer_licenses()
        assert len(licenses) == 2

    def test_list_by_partner(self, ops):
        """Filter licenses by partner."""
        ops.issue_team_license("Acme", 5, 12, partner_id="p1")
        ops.issue_team_license("Globex", 10, 6, partner_id="p2")
        licenses = ops.list_customer_licenses(partner_id="p1")
        assert len(licenses) == 1
        assert licenses[0]["customer"] == "Acme"


class TestPartners:
    def test_add_partner(self, temp_storage):
        """Add a new partner."""
        ops = PartnerOperations(temp_storage, temp_storage / "audit_log.jsonl")
        p = ops.add_partner("CyberSec Consulting", 25, "p@x.com")
        assert p["name"] == "CyberSec Consulting"
        assert p["commission_percent"] == 25
        assert p["partner_id"].startswith("partner_")


class TestPathTraversal:
    def test_path_traversal_blocked(self, ops):
        """Customer names with path traversal chars are sanitized."""
        # This should NOT create a file outside storage
        lic = ops.issue_team_license("../../../etc/evil", 1, 12)
        # File should be created with sanitized name inside storage
        assert lic.raw.get("license_id")
        # Verify no file outside storage
        storage_str = str(ops.storage.resolve())
        for f in ops.storage.rglob("*.json"):
            assert str(f.resolve()).startswith(storage_str)

    def test_special_chars_sanitized(self, ops):
        """Special characters in customer name are stripped."""
        lic = ops.issue_team_license("Acme Corp (Test) @2026!", 1, 12)
        assert lic.raw.get("license_id")


class TestRenewRevoked:
    def test_renew_revoked_license_blocked(self, ops):
        """Renewing a revoked license should be blocked (H4 fix)."""
        ops.issue_team_license("Acme", 5, 12)
        ops.revoke_license("Acme", "non-payment")
        with pytest.raises(ValueError, match="revoked"):
            ops.renew_license("Acme", 12)

    def test_add_partner_invalid_commission(self, temp_storage):
        """Reject invalid commission."""
        ops = PartnerOperations(temp_storage, temp_storage / "audit_log.jsonl")
        with pytest.raises(ValueError, match="commission_percent"):
            ops.add_partner("Bad", 0, "p@x.com")
        with pytest.raises(ValueError, match="commission_percent"):
            ops.add_partner("Bad", 51, "p@x.com")

    def test_list_partners(self, temp_storage):
        """List all partners."""
        ops = PartnerOperations(temp_storage, temp_storage / "audit_log.jsonl")
        ops.add_partner("Partner1", 20, "p1@x.com")
        ops.add_partner("Partner2", 25, "p2@x.com")
        partners = ops.list_partners()
        assert len(partners) == 2

    def test_record_commission(self, temp_storage):
        """Record commission payment."""
        ops = PartnerOperations(temp_storage, temp_storage / "audit_log.jsonl")
        p = ops.add_partner("Partner", 25, "p@x.com")
        ops.record_commission(p["partner_id"], 100.0, "lic_123")
        result = ops.get_partner(p["partner_id"])
        assert result is not None
        assert result["total_commission_earned"] == 100.0
