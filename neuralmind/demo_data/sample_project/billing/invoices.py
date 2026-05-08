"""Invoice generation and delivery."""

from __future__ import annotations

import time

from ..db.connection import get_connection
from ..users.crud import get_user


def create_invoice(user_id: int, amount_cents: int, charge_id: str, description: str) -> dict:
    """Write an invoice row and return it."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO invoices (user_id, amount_cents, charge_id, description, created_at) "
        "VALUES (?, ?, ?, ?, ?) RETURNING id",
        (user_id, amount_cents, charge_id, description, int(time.time())),
    )
    return {
        "id": cursor.fetchone()[0],
        "user_id": user_id,
        "amount_cents": amount_cents,
        "charge_id": charge_id,
        "description": description,
    }


def send_invoice_email(invoice_id: int) -> None:
    """Render an invoice and hand it to the email transport.

    In production this would call the mail service; here it just marks
    the invoice as sent.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT user_id, amount_cents, description FROM invoices WHERE id = ?",
        (invoice_id,),
    ).fetchone()
    if row is None:
        raise InvoiceNotFoundError(f"invoice {invoice_id} not found")

    user = get_user(row[0])
    if user is None:
        raise InvoiceNotFoundError(f"invoice {invoice_id} user missing")

    _render_and_queue(user.email, invoice_id, row[1], row[2])

    conn.execute(
        "UPDATE invoices SET sent_at = ? WHERE id = ?",
        (int(time.time()), invoice_id),
    )


def list_user_invoices(user_id: int) -> list[dict]:
    """Return all invoices for a user, newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, amount_cents, charge_id, description, created_at, sent_at "
        "FROM invoices WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    return [
        {
            "id": r[0],
            "amount_cents": r[1],
            "charge_id": r[2],
            "description": r[3],
            "created_at": r[4],
            "sent_at": r[5],
        }
        for r in rows
    ]


def _render_and_queue(email: str, invoice_id: int, amount: int, description: str) -> None:
    """Stand-in for the real mail-queue call."""
    _ = (email, invoice_id, amount, description)


class InvoiceNotFoundError(Exception):
    """Raised when referencing a missing invoice."""
