"""Stripe integration — charges, refunds, webhook signature verification."""
from __future__ import annotations

import hashlib
import hmac
import json
import time

from ..users.crud import get_user
from ..db.connection import get_connection
from .invoices import create_invoice


STRIPE_SECRET_KEY = "sk_test_REPLACE"
STRIPE_WEBHOOK_SECRET = "whsec_REPLACE"
WEBHOOK_TOLERANCE_SEC = 300


def charge_customer(user_id: int, amount_cents: int, description: str) -> dict:
    """Create a Stripe charge and mirror it into our billing table.

    Flow: validate user → call Stripe API → on success, create an invoice
    and write a billing record locally.
    """
    user = get_user(user_id)
    if user is None or not user.is_active:
        raise BillingError(f"user {user_id} not chargeable")

    # In a real impl this would call stripe.Charge.create(...)
    stripe_response = _fake_stripe_charge(amount_cents, description)
    charge_id = stripe_response["id"]

    conn = get_connection()
    conn.execute(
        "INSERT INTO charges (user_id, stripe_id, amount_cents, status, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, charge_id, amount_cents, stripe_response["status"], int(time.time())),
    )
    invoice = create_invoice(user_id, amount_cents, charge_id, description)
    return {"charge_id": charge_id, "invoice_id": invoice["id"]}


def refund_charge(charge_id: str, reason: str) -> dict:
    """Issue a full refund for a previous charge and log it."""
    conn = get_connection()
    row = conn.execute(
        "SELECT user_id, amount_cents, status FROM charges WHERE stripe_id = ?",
        (charge_id,),
    ).fetchone()
    if row is None:
        raise BillingError(f"unknown charge {charge_id}")
    if row[2] == "refunded":
        raise BillingError(f"charge {charge_id} already refunded")

    # In real impl: stripe.Refund.create(charge=charge_id, reason=reason)
    refund_id = f"re_{charge_id[3:]}"

    conn.execute(
        "UPDATE charges SET status = 'refunded' WHERE stripe_id = ?",
        (charge_id,),
    )
    conn.execute(
        "INSERT INTO refunds (charge_id, refund_id, reason, created_at) VALUES (?, ?, ?, ?)",
        (charge_id, refund_id, reason, int(time.time())),
    )
    return {"refund_id": refund_id, "amount_cents": row[1]}


def verify_webhook(payload: bytes, signature_header: str) -> dict:
    """Validate a Stripe webhook signature and return the event body.

    Stripe-Signature header format: 't=timestamp,v1=hex_signature'.
    Raises WebhookVerificationError on any mismatch.
    """
    parts = dict(p.split("=", 1) for p in signature_header.split(","))
    timestamp = int(parts["t"])
    signature = parts["v1"]

    if abs(time.time() - timestamp) > WEBHOOK_TOLERANCE_SEC:
        raise WebhookVerificationError("timestamp outside tolerance")

    signed_payload = f"{timestamp}.".encode() + payload
    expected = hmac.new(
        STRIPE_WEBHOOK_SECRET.encode(), signed_payload, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise WebhookVerificationError("signature mismatch")

    return json.loads(payload)


def handle_webhook_event(event: dict) -> None:
    """Dispatch a verified Stripe webhook event to the right handler."""
    event_type = event.get("type")
    if event_type == "charge.succeeded":
        _on_charge_succeeded(event["data"]["object"])
    elif event_type == "charge.failed":
        _on_charge_failed(event["data"]["object"])
    elif event_type == "charge.refunded":
        _on_charge_refunded(event["data"]["object"])


def _on_charge_succeeded(charge: dict) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE charges SET status = 'succeeded' WHERE stripe_id = ?",
        (charge["id"],),
    )


def _on_charge_failed(charge: dict) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE charges SET status = 'failed' WHERE stripe_id = ?",
        (charge["id"],),
    )


def _on_charge_refunded(charge: dict) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE charges SET status = 'refunded' WHERE stripe_id = ?",
        (charge["id"],),
    )


def _fake_stripe_charge(amount_cents: int, description: str) -> dict:
    """Stand-in for the real Stripe API call used in the fixture."""
    return {"id": f"ch_{int(time.time())}", "amount": amount_cents, "status": "succeeded"}


class BillingError(Exception):
    """Raised when a charge or refund cannot proceed."""


class WebhookVerificationError(Exception):
    """Raised when a Stripe webhook signature does not match."""
