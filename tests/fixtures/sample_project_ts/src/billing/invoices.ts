// Invoice generation and delivery.

import { getConnection } from "../db/connection";
import { getUser } from "../users/crud";

/** Write an invoice row and return it. */
export function createInvoice(
  userId: number,
  amountCents: number,
  chargeId: string,
  description: string,
): Record<string, unknown> {
  const conn = getConnection();
  const result = conn.execute(
    "INSERT INTO invoices (user_id, amount_cents, charge_id, description, created_at) VALUES (?, ?, ?, ?, ?)",
    [userId, amountCents, chargeId, description, Math.floor(Date.now() / 1000)],
  );
  return {
    id: result.lastId,
    userId,
    amountCents,
    chargeId,
    description,
  };
}

/**
 * Render an invoice and hand it to the email transport.
 *
 * In production this would call the mail service; here it just marks
 * the invoice as sent.
 */
export function sendInvoiceEmail(invoiceId: number): void {
  const conn = getConnection();
  const { rows } = conn.execute(
    "SELECT user_id, amount_cents, description FROM invoices WHERE id = ?",
    [invoiceId],
  );
  if (rows.length === 0) {
    throw new InvoiceNotFoundError(`invoice ${invoiceId} not found`);
  }
  const row = rows[0];
  const user = getUser(row[0] as number);
  if (user === null) {
    throw new InvoiceNotFoundError(`invoice ${invoiceId} user missing`);
  }
  renderAndQueue(user.email, invoiceId, row[1] as number, row[2] as string);
  conn.execute("UPDATE invoices SET sent_at = ? WHERE id = ?", [
    Math.floor(Date.now() / 1000),
    invoiceId,
  ]);
}

/** Return all invoices for a user, newest first. */
export function listUserInvoices(userId: number): Record<string, unknown>[] {
  const conn = getConnection();
  const { rows } = conn.execute(
    "SELECT id, amount_cents, charge_id, description, created_at, sent_at FROM invoices WHERE user_id = ? ORDER BY created_at DESC",
    [userId],
  );
  return rows.map((r) => ({
    id: r[0],
    amountCents: r[1],
    chargeId: r[2],
    description: r[3],
    createdAt: r[4],
    sentAt: r[5],
  }));
}

/** Stand-in for the real mail-queue call. */
function renderAndQueue(
  email: string,
  invoiceId: number,
  amount: number,
  description: string,
): void {
  void [email, invoiceId, amount, description];
}

/** Raised when referencing a missing invoice. */
export class InvoiceNotFoundError extends Error {}
