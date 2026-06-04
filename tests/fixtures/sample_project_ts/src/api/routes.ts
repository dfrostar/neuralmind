// HTTP route wiring for the sample web app.

import {
  authenticateUser,
  logout,
  refreshSession,
  verifySession,
} from "../auth/handlers";
import { listUserInvoices } from "../billing/invoices";
import {
  chargeCustomer,
  handleWebhookEvent,
  refundCharge,
  verifyWebhook,
} from "../billing/stripeClient";
import { createUser, deactivateUser, getUser } from "../users/crud";

export interface Request {
  json: Record<string, unknown>;
  body: string;
  headers: Record<string, string>;
}

type Handler = (request: Request) => unknown;

export const ROUTES: Array<[string, string, Handler]> = [];

/** Record a (method, path, handler) tuple. */
function route(method: string, path: string, fn: Handler): void {
  ROUTES.push([method.toUpperCase(), path, fn]);
}

/** POST /api/auth/login — returns access + refresh tokens. */
export function loginEndpoint(request: Request): unknown {
  const body = request.json;
  return authenticateUser(body.email as string, body.password as string);
}
route("POST", "/api/auth/login", loginEndpoint);

/** POST /api/auth/refresh — returns a new access token. */
export function refreshEndpoint(request: Request): unknown {
  return refreshSession(request.json.refreshToken as string);
}
route("POST", "/api/auth/refresh", refreshEndpoint);

/** POST /api/auth/logout — revokes a refresh token. */
export function logoutEndpoint(request: Request): unknown {
  logout(request.json.refreshToken as string);
  return { ok: true };
}
route("POST", "/api/auth/logout", logoutEndpoint);

/** POST /api/users — sign-up flow. */
export function createUserEndpoint(request: Request): unknown {
  const body = request.json;
  const user = createUser(body.email as string, body.passwordHash as string);
  return { id: user.id, email: user.email };
}
route("POST", "/api/users", createUserEndpoint);

/** GET /api/users/me — requires Authorization: Bearer header. */
export function getMeEndpoint(request: Request): unknown {
  const token = bearer(request);
  const userId = verifySession(token);
  const user = getUser(userId);
  return { id: user?.id, email: user?.email };
}
route("GET", "/api/users/me", getMeEndpoint);

/** DELETE /api/users/me — soft-delete the authenticated user. */
export function deleteMeEndpoint(request: Request): unknown {
  const token = bearer(request);
  const userId = verifySession(token);
  deactivateUser(userId);
  return { ok: true };
}
route("DELETE", "/api/users/me", deleteMeEndpoint);

/** POST /api/billing/charge — charge the authenticated user. */
export function chargeEndpoint(request: Request): unknown {
  const token = bearer(request);
  const userId = verifySession(token);
  const body = request.json;
  return chargeCustomer(userId, body.amountCents as number, body.description as string);
}
route("POST", "/api/billing/charge", chargeEndpoint);

/** POST /api/billing/refund — admin-only refund of a charge. */
export function refundEndpoint(request: Request): unknown {
  const body = request.json;
  return refundCharge(body.chargeId as string, body.reason as string);
}
route("POST", "/api/billing/refund", refundEndpoint);

/** GET /api/billing/invoices — list invoices for the authenticated user. */
export function listInvoicesEndpoint(request: Request): unknown {
  const token = bearer(request);
  const userId = verifySession(token);
  return listUserInvoices(userId);
}
route("GET", "/api/billing/invoices", listInvoicesEndpoint);

/** POST /webhooks/stripe — entry point for Stripe events. */
export function stripeWebhookEndpoint(request: Request): unknown {
  const event = verifyWebhook(request.body, request.headers["Stripe-Signature"]);
  handleWebhookEvent(event);
  return { received: true };
}
route("POST", "/webhooks/stripe", stripeWebhookEndpoint);

function bearer(request: Request): string {
  return request.headers["Authorization"].replace(/^Bearer /, "").trim();
}
