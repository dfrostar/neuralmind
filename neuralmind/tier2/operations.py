# Copyright (c) 2026 Cheval-Volant LLC (d/b/a NeuralMind).
# Source-available under the NeuralMind Commercial Modules License
# (neuralmind/tier2/LICENSE) — NOT MIT. Free 1-seat use included; see LICENSING.md.
"""operations.py — License & Partner operations for NeuralMind."""

from __future__ import annotations

import calendar
import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import license
from .pricing import calculate_price, load_pricing


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _add_months(start: datetime, months: int) -> datetime:
    """Add calendar months to ``start``, clamping to the last valid day.

    Terms are sold in months, so they have to land on the calendar. Adding
    30-day months shortchanged an annual customer by five days and drifted
    further on longer terms. Day-of-month is clamped, so 31 Jan + 1 month is
    28/29 Feb rather than rolling into March.

    Args:
        start: The instant the term runs from.
        months: Number of calendar months to add.

    Returns:
        ``start`` advanced by ``months``, at the same time of day.
    """
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


class LicenseOperations:
    """Manage Team license issuance, renewal, and revocation."""

    def __init__(
        self,
        private_key_hex: str,
        storage_path: Path,
    ):
        # Store key as bytearray for secure wiping (M1 fix)
        self._private_key_bytes = bytearray.fromhex(private_key_hex)
        self.storage = Path(storage_path)
        self.storage.mkdir(parents=True, exist_ok=True)
        self.customers_path = self.storage / "customers.yaml"
        self.partners_path = self.storage / "partners.yaml"
        self.audit_path = self.storage / "audit_log.jsonl"

    def __del__(self):
        # Securely wipe private key from memory on destruction
        if hasattr(self, "_private_key_bytes"):
            for i in range(len(self._private_key_bytes)):
                self._private_key_bytes[i] = 0

    def _load_customers(self) -> dict:
        if not self.customers_path.exists():
            return {"customers": {}}
        import yaml

        with open(self.customers_path) as f:
            data = yaml.safe_load(f)
        # H2 fix: YAML safe_load can return non-dict types (list, string, number)
        if not isinstance(data, dict):
            return {"customers": {}}
        if "customers" not in data:
            data["customers"] = {}
        return data

    def _save_customers(self, data: dict) -> None:
        import yaml

        fd, tmp = tempfile.mkstemp(dir=self.storage, suffix=".tmp")
        try:
            with open(fd, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
            Path(tmp).replace(self.customers_path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise

    def _load_partners(self) -> dict:
        if not self.partners_path.exists():
            return {"partners": {}}
        import yaml

        with open(self.partners_path) as f:
            return yaml.safe_load(f) or {"partners": {}}

    def _save_partners(self, data: dict) -> None:
        import yaml

        fd, tmp = tempfile.mkstemp(dir=self.storage, suffix=".tmp")
        try:
            with open(fd, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
            Path(tmp).replace(self.partners_path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise

    def _log_audit(self, action: str, **kwargs) -> None:
        entry = {"timestamp": _now_iso(), "action": action, **kwargs}
        # Sanitize all string values to prevent JSONL injection
        sanitized = {}
        for k, v in entry.items():
            if isinstance(v, str):
                # Replace newlines and control chars to prevent line injection
                sanitized[k] = v.replace("\n", " ").replace("\r", " ")
            else:
                sanitized[k] = v
        with open(self.audit_path, "a") as f:
            f.write(json.dumps(sanitized, ensure_ascii=True) + "\n")

    def _generate_license_id(self) -> str:
        return f"lic_{uuid.uuid4().hex[:12]}"

    def _generate_customer_id(self) -> str:
        return f"cust_{uuid.uuid4().hex[:12]}"

    def _sign_license(self, data: dict) -> str:
        """Sign license data with Ed25519 private key."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        priv_key = Ed25519PrivateKey.from_private_bytes(bytes(self._private_key_bytes))
        msg = json.dumps(data, sort_keys=True, separators=(",", ":"))
        sig = priv_key.sign(msg.encode("utf-8"))
        return sig.hex()

    def _verify_existing_signature(self, lic_data: dict) -> bool:
        """Verify the signature on an existing license file."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )

        try:
            # Derive public key from private key for verification
            priv_key = Ed25519PrivateKey.from_private_bytes(bytes(self._private_key_bytes))
            pub_key = priv_key.public_key()
            sig = lic_data.get("signature", "")
            if not sig or sig == "self-signed":
                return False
            msg_dict = {k: v for k, v in lic_data.items() if k != "signature"}
            msg = json.dumps(msg_dict, sort_keys=True, separators=(",", ":"))
            sig_bytes = bytes.fromhex(sig)
            pub_key.verify(sig_bytes, msg.encode("utf-8"))
            return True
        except Exception:
            return False

    def issue_team_license(
        self,
        customer_name: str,
        seats: int,
        term_months: int,
        partner_id: str | None = None,
        output_path: Path | None = None,
    ) -> license.LicenseInfo:
        """Issue a new Team license."""
        if seats <= 0:
            raise ValueError("seats must be positive")
        if term_months not in (1, 3, 6, 12, 24, 36):
            raise ValueError("term_months must be 1, 3, 6, 12, 24, or 36")

        pricing = load_pricing()
        total_price = calculate_price(pricing, "team", seats, term_months)

        license_id = self._generate_license_id()
        customer_id = self._generate_customer_id()
        now = datetime.now(timezone.utc)
        expires_at = _add_months(now, term_months)

        # Build license data
        license_data = {
            "tier": "team",
            "seats": seats,
            "issued_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "issued_to": customer_name,
            "license_id": license_id,
            "agreement_version": "1.0",
            "accepted_at": now.isoformat(),
        }
        if partner_id:
            license_data["partner_id"] = partner_id

        # Sign
        signature = self._sign_license(license_data)
        license_data["signature"] = signature

        # Write license file — sanitize customer_name to prevent path traversal
        if output_path is None:
            safe_name = "".join(c for c in customer_name.lower() if c.isalnum() or c in "-_")
            output_path = self.storage / f"{safe_name}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Verify the resolved path is still inside storage
        if not str(output_path.resolve()).startswith(str(self.storage.resolve())):
            raise ValueError("Invalid customer name: path traversal detected")
        fd, tmp = tempfile.mkstemp(dir=output_path.parent, suffix=".tmp")
        try:
            with open(fd, "w") as f:
                json.dump(license_data, f, indent=2)
            Path(tmp).replace(output_path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise

        # Update customers.yaml
        customers = self._load_customers()
        customers["customers"][customer_name] = {
            "customer_id": customer_id,
            "name": customer_name,
            "tier": "team",
            "seats": seats,
            "license_id": license_id,
            "partner_id": partner_id,
            "issued_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "status": "active",
            "total_paid": total_price,
            "currency": "USD",
        }
        self._save_customers(customers)

        # Log
        self._log_audit(
            "issue",
            license_id=license_id,
            customer=customer_name,
            seats=seats,
            term_months=term_months,
            partner_id=partner_id,
            total_price=total_price,
        )

        return license.LicenseInfo(
            tier="team",
            seats=seats,
            issued_at=license_data["issued_at"],
            expires_at=license_data["expires_at"],
            issued_to=customer_name,
            signature=signature,
            raw=license_data,
        )

    def renew_license(
        self,
        customer_name: str,
        term_months: int,
    ) -> license.LicenseInfo:
        """Renew an existing license."""
        customers = self._load_customers()
        if customer_name not in customers["customers"]:
            raise ValueError(f"customer {customer_name!r} not found")
        cust = customers["customers"][customer_name]

        old_expires = datetime.fromisoformat(cust["expires_at"])
        new_expires = _add_months(old_expires, term_months)

        # H4 fix: Do not revive revoked licenses
        if cust.get("status") == "revoked":
            raise ValueError(
                f"License for {customer_name} is revoked. Issue a new license instead of renewing."
            )

        # Update license file — verify existing signature before re-signing
        lic_data = {}
        safe_name = "".join(c for c in customer_name.lower() if c.isalnum() or c in "-_")
        license_path = self.storage / f"{safe_name}.json"
        if not str(license_path.resolve()).startswith(str(self.storage.resolve())):
            raise ValueError("Invalid customer name: path traversal detected")
        if license_path.exists():
            with open(license_path) as f:
                lic_data = json.load(f)
            # Verify existing signature before re-signing (C2 fix)
            if not self._verify_existing_signature(lic_data):
                raise ValueError("License file has been tampered with: signature invalid")
            lic_data["expires_at"] = new_expires.isoformat()
            signature = self._sign_license({k: v for k, v in lic_data.items() if k != "signature"})
            lic_data["signature"] = signature
            with open(license_path, "w") as f:
                json.dump(lic_data, f, indent=2)

        # Update customers.yaml
        cust["expires_at"] = new_expires.isoformat()
        cust["status"] = "active"
        self._save_customers(customers)

        # Log
        self._log_audit(
            "renew",
            license_id=cust["license_id"],
            customer=customer_name,
            term_months=term_months,
            new_expires=new_expires.isoformat(),
        )

        return license.LicenseInfo(
            tier="team",
            seats=cust["seats"],
            issued_at=cust["issued_at"],
            expires_at=new_expires.isoformat(),
            issued_to=customer_name,
            signature=lic_data.get("signature", ""),
            raw=lic_data,
        )

    def revoke_license(
        self,
        customer_name: str,
        reason: str,
    ) -> license.LicenseInfo:
        """Revoke (expire immediately) a license."""
        customers = self._load_customers()
        if customer_name not in customers["customers"]:
            raise ValueError(f"customer {customer_name!r} not found")
        cust = customers["customers"][customer_name]

        now = datetime.now(timezone.utc)
        lic_data = {}

        # Update license file — verify existing signature before re-signing (C2 fix)
        safe_name = "".join(c for c in customer_name.lower() if c.isalnum() or c in "-_")
        license_path = self.storage / f"{safe_name}.json"
        if not str(license_path.resolve()).startswith(str(self.storage.resolve())):
            raise ValueError("Invalid customer name: path traversal detected")
        if license_path.exists():
            with open(license_path) as f:
                lic_data = json.load(f)
            # Verify existing signature before re-signing
            if not self._verify_existing_signature(lic_data):
                raise ValueError("License file has been tampered with: signature invalid")
            lic_data["expires_at"] = now.isoformat()
            signature = self._sign_license({k: v for k, v in lic_data.items() if k != "signature"})
            lic_data["signature"] = signature
            with open(license_path, "w") as f:
                json.dump(lic_data, f, indent=2)

        # Update customers.yaml
        cust["expires_at"] = now.isoformat()
        cust["status"] = "revoked"
        self._save_customers(customers)

        # Log
        self._log_audit(
            "revoke",
            license_id=cust["license_id"],
            customer=customer_name,
            reason=reason,
        )

        return license.LicenseInfo(
            tier="team",
            seats=cust["seats"],
            issued_at=cust["issued_at"],
            expires_at=now.isoformat(),
            issued_to=customer_name,
            signature=lic_data.get("signature", ""),
            raw=lic_data,
        )

    def get_license_status(self, customer_name: str) -> dict:
        """Get detailed license status for display."""
        customers = self._load_customers()
        if customer_name not in customers["customers"]:
            return {"error": f"customer {customer_name!r} not found"}
        cust = customers["customers"][customer_name]

        try:
            exp = datetime.fromisoformat(cust["expires_at"])
            days_remaining = (exp - datetime.now(timezone.utc)).days
        except (ValueError, TypeError):
            days_remaining = None

        return {
            "customer": customer_name,
            "license_id": cust.get("license_id"),
            "tier": cust.get("tier"),
            "seats": cust.get("seats"),
            "issued_at": cust.get("issued_at"),
            "expires_at": cust.get("expires_at"),
            "days_remaining": days_remaining,
            "status": cust.get("status"),
            "total_paid": cust.get("total_paid"),
            "partner_id": cust.get("partner_id"),
        }

    def list_customer_licenses(
        self,
        partner_id: str | None = None,
    ) -> list[dict]:
        """List all customer licenses, optionally filtered by partner."""
        customers = self._load_customers()
        results = []
        for name, cust in customers.get("customers", {}).items():
            if partner_id and cust.get("partner_id") != partner_id:
                continue
            results.append(
                {
                    "customer": name,
                    "license_id": cust.get("license_id"),
                    "tier": cust.get("tier"),
                    "seats": cust.get("seats"),
                    "status": cust.get("status"),
                    "expires_at": cust.get("expires_at"),
                    "total_paid": cust.get("total_paid"),
                }
            )
        return results


class PartnerOperations:
    """Manage partners (resellers)."""

    def __init__(self, storage_path: Path, audit_path: Path):
        self.storage = Path(storage_path)
        self.storage.mkdir(parents=True, exist_ok=True)
        self.partners_path = self.storage / "partners.yaml"
        self.audit_path = audit_path

    def _load_partners(self) -> dict:
        if not self.partners_path.exists():
            return {"partners": {}}
        import yaml

        with open(self.partners_path) as f:
            return yaml.safe_load(f) or {"partners": {}}

    def _save_partners(self, data: dict) -> None:
        import yaml

        fd, tmp = tempfile.mkstemp(dir=self.storage, suffix=".tmp")
        try:
            with open(fd, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
            Path(tmp).replace(self.partners_path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise

    def add_partner(
        self,
        name: str,
        commission_percent: float,
        contact_email: str,
    ) -> dict:
        """Add a new partner."""
        if not 0 < commission_percent <= 50:
            raise ValueError("commission_percent must be between 0 and 50")
        partners = self._load_partners()
        partner_id = f"partner_{uuid.uuid4().hex[:12]}"
        partners["partners"][partner_id] = {
            "partner_id": partner_id,
            "name": name,
            "commission_percent": commission_percent,
            "contact_email": contact_email,
            "customers": [],
            "total_commission_earned": 0.0,
            "created_at": _now_iso(),
        }
        self._save_partners(partners)
        return partners["partners"][partner_id]

    def list_partners(self) -> list[dict]:
        """List all partners."""
        partners = self._load_partners()
        return list(partners.get("partners", {}).values())

    def get_partner(self, partner_id: str) -> dict | None:
        """Get a single partner by ID."""
        partners = self._load_partners()
        return partners.get("partners", {}).get(partner_id)

    def record_commission(
        self,
        partner_id: str,
        amount: float,
        license_id: str,
    ) -> None:
        """Record a commission payment for a partner."""
        partners = self._load_partners()
        if partner_id not in partners["partners"]:
            raise ValueError(f"partner {partner_id!r} not found")
        partners["partners"][partner_id]["total_commission_earned"] += amount
        partners["partners"][partner_id].setdefault("commissions", []).append(
            {
                "amount": amount,
                "license_id": license_id,
                "timestamp": _now_iso(),
            }
        )
        self._save_partners(partners)

    def get_partner_licenses(self, partner_id: str) -> list[dict]:
        """Get all licenses issued through a partner."""
        # Delegate to LicenseOperations
