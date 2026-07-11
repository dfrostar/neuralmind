"""HTTP route wiring for the sample web app."""

from __future__ import annotations

from ..auth.handlers import authenticate_user, logout, refresh_session, verify_session
from ..billing.invoices import list_user_invoices
from ..billing.stripe_client import (
    charge_customer,
    handle_webhook_event,
    refund_charge,
    verify_webhook,
)
from ..users.crud import create_user, deactivate_user, get_user

ROUTES = []


def route(method: str, path: str):
    """Minimal decorator recording a (method, path, handler) tuple."""

    def wrap(fn):
        ROUTES.append((method.upper(), path, fn))
        return fn

    return wrap


@route("POST", "/api/auth/login")
def login_endpoint(request):
    """POST /api/auth/login — returns access + refresh tokens."""
    body = request.json
    return authenticate_user(body["email"], body["password"])


@route("POST", "/api/auth/refresh")
def refresh_endpoint(request):
    """POST /api/auth/refresh — returns a new access token."""
    return refresh_session(request.json["refresh_token"])


@route("POST", "/api/auth/logout")
def logout_endpoint(request):
    """POST /api/auth/logout — revokes a refresh token."""
    logout(request.json["refresh_token"])
    return {"ok": True}


@route("POST", "/api/users")
def create_user_endpoint(request):
    """POST /api/users — sign-up flow."""
    body = request.json
    # password_hash computation omitted in fixture
    user = create_user(body["email"], body["password_hash"])
    return {"id": user.id, "email": user.email}


@route("GET", "/api/users/me")
def get_me_endpoint(request):
    """GET /api/users/me — requires Authorization: Bearer header."""
    token = request.headers["Authorization"].removeprefix("Bearer ").strip()
    user_id = verify_session(token)
    user = get_user(user_id)
    return {"id": user.id, "email": user.email, "created_at": str(user.created_at)}


@route("DELETE", "/api/users/me")
def delete_me_endpoint(request):
    """DELETE /api/users/me — soft-delete the authenticated user."""
    token = request.headers["Authorization"].removeprefix("Bearer ").strip()
    user_id = verify_session(token)
    deactivate_user(user_id)
    return {"ok": True}


@route("POST", "/api/billing/charge")
def charge_endpoint(request):
    """POST /api/billing/charge — charge the authenticated user."""
    token = request.headers["Authorization"].removeprefix("Bearer ").strip()
    user_id = verify_session(token)
    body = request.json
    return charge_customer(user_id, body["amount_cents"], body["description"])


@route("POST", "/api/billing/refund")
def refund_endpoint(request):
    """POST /api/billing/refund — admin-only refund of a charge."""
    body = request.json
    return refund_charge(body["charge_id"], body["reason"])


@route("GET", "/api/billing/invoices")
def list_invoices_endpoint(request):
    """GET /api/billing/invoices — list invoices for the authenticated user."""
    token = request.headers["Authorization"].removeprefix("Bearer ").strip()
    user_id = verify_session(token)
    return list_user_invoices(user_id)


@route("POST", "/webhooks/stripe")
def stripe_webhook_endpoint(request):
    """POST /webhooks/stripe — entry point for Stripe events."""
    event = verify_webhook(request.body, request.headers["Stripe-Signature"])
    handle_webhook_event(event)
    return {"received": True}
