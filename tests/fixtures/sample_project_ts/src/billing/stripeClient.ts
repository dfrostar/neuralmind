// Stripe integration — charges, refunds, webhook signature verification.

import { createHmac, timingSafeEqual } from "crypto";

import { getConnection } from "../db/connection";
import { getUser } from "../users/crud";
import { createInvoice } from "./invoices";

const STRIPE_WEBHOOK_SECRET = "whsec_REPLACE";
const WEBHOOK_TOLERANCE_SEC = 300;

/**
 * Create a Stripe charge and mirror it into our billing table.
 *
 * Flow: validate user → call Stripe API → on success, create an invoice
 * and write a billing record locally.
 */
export function chargeCustomer(
  userId: number,
  amountCents: number,
  description: string,
): Record<string, unknown> {
  const user = getUser(userId);
  if (user === null || !user.isActive) {
    throw new BillingError(`user ${userId} not chargeable`);
  }

  const stripeResponse = fakeStripeCharge(amountCents, description);
  const chargeId = stripeResponse.id;

  const conn = getConnection();
  conn.execute(
    "INSERT INTO charges (user_id, stripe_id, amount_cents, status, created_at) VALUES (?, ?, ?, ?, ?)",
    [userId, chargeId, amountCents, stripeResponse.status, Math.floor(Date.now() / 1000)],
  );
  const invoice = createInvoice(userId, amountCents, chargeId, description);
  return { chargeId, invoiceId: invoice.id };
}

/** Issue a full refund for a previous charge and log it. */
export function refundCharge(chargeId: string, reason: string): Record<string, unknown> {
  const conn = getConnection();
  const { rows } = conn.execute(
    "SELECT user_id, amount_cents, status FROM charges WHERE stripe_id = ?",
    [chargeId],
  );
  if (rows.length === 0) {
    throw new BillingError(`unknown charge ${chargeId}`);
  }
  if (rows[0][2] === "refunded") {
    throw new BillingError(`charge ${chargeId} already refunded`);
  }
  const refundId = `re_${chargeId.slice(3)}`;
  conn.execute("UPDATE charges SET status = 'refunded' WHERE stripe_id = ?", [chargeId]);
  void reason;
  return { refundId, amountCents: rows[0][1] };
}

/**
 * Validate a Stripe webhook signature and return the event body.
 *
 * Stripe-Signature header format: 't=timestamp,v1=hex_signature'.
 * Throws WebhookVerificationError on any mismatch.
 */
export function verifyWebhook(payload: string, signatureHeader: string): Record<string, unknown> {
  const parts = Object.fromEntries(signatureHeader.split(",").map((p) => p.split("=", 2)));
  const timestamp = Number(parts.t);
  const signature = parts.v1;
  // A malformed header (missing t/v1) must surface as WebhookVerificationError,
  // not a downstream TypeError from Number(undefined)/Buffer.from(undefined).
  if (!signature || Number.isNaN(timestamp)) {
    throw new WebhookVerificationError("malformed signature header");
  }

  if (Math.abs(Date.now() / 1000 - timestamp) > WEBHOOK_TOLERANCE_SEC) {
    throw new WebhookVerificationError("timestamp outside tolerance");
  }

  const signedPayload = `${timestamp}.${payload}`;
  const expected = Buffer.from(
    createHmac("sha256", STRIPE_WEBHOOK_SECRET).update(signedPayload).digest("hex"),
  );
  const provided = Buffer.from(signature);
  // timingSafeEqual throws on unequal-length buffers; length-check first so a
  // bad signature is reported as a mismatch rather than throwing a TypeError.
  if (expected.length !== provided.length || !timingSafeEqual(expected, provided)) {
    throw new WebhookVerificationError("signature mismatch");
  }
  return JSON.parse(payload);
}

/** Dispatch a verified Stripe webhook event to the right handler. */
export function handleWebhookEvent(event: Record<string, unknown>): void {
  const eventType = event.type as string;
  const data = event.data as { object: { id: string } };
  if (eventType === "charge.succeeded") {
    onChargeStatus(data.object.id, "succeeded");
  } else if (eventType === "charge.failed") {
    onChargeStatus(data.object.id, "failed");
  } else if (eventType === "charge.refunded") {
    onChargeStatus(data.object.id, "refunded");
  }
}

function onChargeStatus(stripeId: string, status: string): void {
  const conn = getConnection();
  conn.execute("UPDATE charges SET status = ? WHERE stripe_id = ?", [status, stripeId]);
}

/** Stand-in for the real Stripe API call used in the fixture. */
function fakeStripeCharge(amountCents: number, description: string): { id: string; status: string } {
  void [amountCents, description];
  return { id: `ch_${Math.floor(Date.now() / 1000)}`, status: "succeeded" };
}

/** Raised when a charge or refund cannot proceed. */
export class BillingError extends Error {}

/** Raised when a Stripe webhook signature does not match. */
export class WebhookVerificationError extends Error {}
