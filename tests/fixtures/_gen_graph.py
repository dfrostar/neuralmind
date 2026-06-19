#!/usr/bin/env python3
"""Hand-authored graph.json generator for the polyglot eval fixtures.

graphify is NOT installed in CI (it is a single-maintainer dependency, see
docs/NEXT-RELEASE-PLAN.md v0.14). To keep the TS and Go retrieval-quality
fixtures self-contained, this script emits a graph.json in the *exact* schema
graphify produces for the Python fixture
(``neuralmind/demo_data/sample_project/graphify-out/graph.json``):

    {
      "directed": false, "multigraph": false, "graph": {},
      "nodes": [{label, file_type, source_file, source_location, id,
                 community, norm_label}, ...],
      "links": [{relation, [context], confidence, source_file,
                 source_location, weight, source, target, confidence_score}, ...],
      "hyperedges": [],
      "built_at_commit": "<sha>"
    }

Node ``file_type`` is one of ``code`` (a file, function, class, or interface),
``rationale`` (a docstring/leading doc-comment summary), or ``document`` (markdown).
Edge ``relation`` is one of ``contains`` (file→symbol), ``imports_from``
(file→file), ``calls`` (symbol→symbol), ``rationale_for`` (rationale→symbol),
or ``inherits`` (class→base).

The structure below is authored *by hand* to mirror the shape graphify would
extract — it is a faithful approximation, not a byte-identical reproduction of
graphify's own output. When graphify is available it should be regenerated with
``graphify update`` (see each fixture's README); the eval harness only depends
on ``source_file`` strings matching the gold modules, which this guarantees.

Run:  python tests/fixtures/_gen_graph.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMIT = "handauthored0000000000000000000000000000"


def _def_line(source_path: Path, name: str) -> int:
    """Find the 1-based line where ``name`` is defined in ``source_path``.

    Recognizes TS (function/interface/class) and Go (func/type) definitions.
    Line numbers are derived from the *real* source so the graph's
    source_location values stay faithful even though the graph is
    hand-authored. Falls back to L1 if the symbol can't be located.
    """
    base = name.rstrip("()")
    lines = source_path.read_text().splitlines()
    pat = re.compile(rf"\b(?:function|interface|class|func|type)\b[^\n]*\b{re.escape(base)}\b")
    for i, line in enumerate(lines, 1):
        if pat.search(line):
            return i
    return 1


def _call_line(source_path: Path, callee: str, start_line: int) -> int | None:
    """Find the 1-based line at/after ``start_line`` where ``callee`` is invoked.

    Derives the edge's ``source_location`` from the *real* source (rather than
    a hand-maintained number that silently goes stale when the fixture is
    edited), starting the scan at the caller's definition so an unrelated call
    of the same function elsewhere isn't picked up. Returns ``None`` if no call
    site is found so the caller can fall back to the spec's hint.
    """
    base = callee.rstrip("()")
    lines = source_path.read_text().splitlines()
    pat = re.compile(rf"\b{re.escape(base)}\s*\(")
    for i in range(max(start_line, 1), len(lines) + 1):
        if pat.search(lines[i - 1]):
            return i
    return None


def _import_line(source_path: Path, dst: str) -> int | None:
    """Find the 1-based line that imports module ``dst`` from ``source_path``.

    Handles both TS (``import ... from "../db/connection"`` — matched by the
    file basename) and Go (grouped ``import (`` block referencing the package
    directory, e.g. ``"example.com/sample/db"`` — matched by the parent dir).
    Returns ``None`` if no import line is found.
    """
    dst_p = Path(dst)
    candidates = {dst_p.stem, dst_p.parent.name}
    quoted = re.compile(r"""['"]([^'"]+)['"]""")
    in_block = False
    for i, line in enumerate(source_path.read_text().splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("import ("):
            in_block = True
        if in_block or stripped.startswith("import") or "from" in line:
            for path in quoted.findall(line):
                if path.rstrip("/").rsplit("/", 1)[-1] in candidates:
                    return i
        if in_block and stripped == ")":
            in_block = False
    return None


def make_graph(spec: dict, fixture_dir: Path) -> dict:
    nodes: list[dict] = []
    links: list[dict] = []

    file_ids: dict[str, str] = {}
    symbol_ids: dict[tuple[str, str], str] = {}
    symbol_lines: dict[tuple[str, str], int] = {}

    # 1. file + symbol + rationale nodes
    for f in spec["files"]:
        src = f["path"]
        fid = f["id"]
        file_ids[src] = fid
        community = f["community"]
        nodes.append(
            {
                "label": Path(src).name,
                "file_type": "code",
                "source_file": src,
                "source_location": "L1",
                "id": fid,
                "community": community,
                "norm_label": Path(src).name.lower(),
            }
        )
        # file-level rationale (module docstring / header comment)
        if f.get("rationale"):
            rid = f"{fid}_rationale_1"
            nodes.append(
                {
                    "label": f["rationale"],
                    "file_type": "rationale",
                    "source_file": src,
                    "source_location": "L1",
                    "id": rid,
                    "community": community,
                    "norm_label": f["rationale"].lower(),
                }
            )
            links.append(_link("rationale_for", src, "L1", rid, fid))

        for sym in f["symbols"]:
            sid = f"{fid}_{sym['name'].lower().rstrip('()')}"
            symbol_ids[(src, sym["name"])] = sid
            line = _def_line(fixture_dir / src, sym["name"])
            if line == 1 and sym.get("line"):
                # _def_line couldn't locate it (e.g. an interface method with
                # no def keyword); fall back to the spec's hand-authored hint.
                line = sym["line"]
            symbol_lines[(src, sym["name"])] = line
            loc = f"L{line}"
            nodes.append(
                {
                    "label": sym["name"],
                    "file_type": "code",
                    "source_file": src,
                    "source_location": loc,
                    "id": sid,
                    "community": community,
                    "norm_label": sym["name"].lower(),
                }
            )
            links.append(_link("contains", src, loc, fid, sid))
            if sym.get("rationale"):
                rid = f"{sid}_rationale"
                nodes.append(
                    {
                        "label": sym["rationale"],
                        "file_type": "rationale",
                        "source_file": src,
                        "source_location": loc,
                        "id": rid,
                        "community": community,
                        "norm_label": sym["rationale"].lower(),
                    }
                )
                links.append(_link("rationale_for", src, loc, rid, sid))
            if sym.get("inherits"):
                links.append(
                    _link("inherits", src, loc, sid, sym["inherits"], confidence="EXTRACTED")
                )

    # error base node shared target of inherits (like Python fixture's "exception")
    base_targets = {lk["target"] for lk in links if lk["relation"] == "inherits"}
    for bt in sorted(base_targets):
        if not any(n["id"] == bt for n in nodes):
            nodes.append(
                {
                    "label": bt,
                    "file_type": "code",
                    "source_file": "<builtin>",
                    "source_location": "L1",
                    "id": bt,
                    "community": 0,
                    "norm_label": bt.lower(),
                }
            )

    # 2. imports_from links (file -> file). Location derived from the real
    #    source; the spec's number is only a fallback if it can't be found.
    for imp in spec["imports"]:
        src, line, dst = imp
        derived = _import_line(fixture_dir / src, dst)
        links.append(
            _link(
                "imports_from",
                src,
                f"L{derived if derived is not None else line}",
                file_ids[src],
                file_ids[dst],
                context="import",
                confidence="EXTRACTED",
            )
        )

    # 3. calls links (symbol -> symbol). Location derived from the real source,
    #    scanning from the caller's definition; spec number is a fallback.
    for call in spec["calls"]:
        src_file, line, caller, callee_file, callee = call
        sid = symbol_ids[(src_file, caller)]
        tid = symbol_ids[(callee_file, callee)]
        derived = _call_line(
            fixture_dir / src_file, callee, symbol_lines.get((src_file, caller), 1)
        )
        links.append(
            _link(
                "calls",
                src_file,
                f"L{derived if derived is not None else line}",
                sid,
                tid,
                context="call",
                confidence="INFERRED",
                confidence_score=0.8,
            )
        )

    return {
        "directed": False,
        "multigraph": False,
        "graph": {},
        "nodes": nodes,
        "links": links,
        "hyperedges": [],
        "built_at_commit": COMMIT,
    }


def _link(
    relation: str,
    source_file: str,
    location: str,
    source: str,
    target: str,
    *,
    context: str | None = None,
    confidence: str = "EXTRACTED",
    confidence_score: float = 1.0,
) -> dict:
    d: dict = {"relation": relation}
    if context:
        d["context"] = context
    d["confidence"] = confidence
    d.update(
        {
            "source_file": source_file,
            "source_location": location,
            "weight": 1.0,
            "source": source,
            "target": target,
            "confidence_score": confidence_score,
        }
    )
    return d


# --------------------------------------------------------------------------- TS

TS_SPEC = {
    "files": [
        {
            "path": "src/db/connection.ts",
            "id": "db_connection_ts",
            "community": 1,
            "rationale": "Database connection pool for the fixture.",
            "symbols": [
                {"name": "Connection", "rationale": "Minimal connection interface."},
                {
                    "name": "getConnection()",
                    "rationale": "Return a process-wide connection to the fixture database.",
                },
                {"name": "closeAll()", "line": 30},
                {"name": "createConnection()", "line": 37},
                {
                    "name": "ensureSchema()",
                    "rationale": "Create fixture tables if they don't exist yet.",
                },
            ],
        },
        {
            "path": "src/users/crud.ts",
            "id": "users_crud_ts",
            "community": 2,
            "rationale": "User model + CRUD operations.",
            "symbols": [
                {"name": "User", "rationale": "Canonical user record."},
                {
                    "name": "createUser()",
                    "rationale": "Insert a new user and return the created record.",
                },
                {"name": "getUserByEmail()", "rationale": "Fetch a user by email (auth hot path)."},
                {"name": "getUser()", "rationale": "Fetch a user by primary key."},
                {"name": "updateLastLogin()", "line": 60},
                {
                    "name": "deactivateUser()",
                    "rationale": "Soft-delete a user by flipping isActive off.",
                },
            ],
        },
        {
            "path": "src/auth/jwtUtils.ts",
            "id": "auth_jwtutils_ts",
            "community": 3,
            "rationale": "JWT encode/decode helpers.",
            "symbols": [
                {
                    "name": "encodeToken()",
                    "rationale": "Produce a signed JWT string from a claims object.",
                },
                {
                    "name": "decodeToken()",
                    "rationale": "Verify signature + expiry and return the claims object.",
                },
                {"name": "sign()", "line": 44},
                {"name": "TokenExpiredError", "inherits": "Error"},
                {"name": "InvalidSignatureError", "inherits": "Error"},
                {"name": "MalformedTokenError", "inherits": "Error"},
            ],
        },
        {
            "path": "src/auth/handlers.ts",
            "id": "auth_handlers_ts",
            "community": 3,
            "rationale": "Authentication handlers — login, logout, token refresh.",
            "symbols": [
                {
                    "name": "authenticateUser()",
                    "rationale": "Validate credentials and issue an access + refresh token pair.",
                },
                {
                    "name": "verifySession()",
                    "rationale": "Return the user id if the access token is valid.",
                },
                {
                    "name": "refreshSession()",
                    "rationale": "Exchange a refresh token for a new access token.",
                },
                {
                    "name": "logout()",
                    "rationale": "Revoke a refresh token by writing it to the revocation list.",
                },
                {
                    "name": "verifyPassword()",
                    "rationale": "Constant-time password verification against stored hash.",
                },
                {"name": "InvalidCredentialsError", "inherits": "Error"},
                {"name": "InvalidTokenError", "inherits": "Error"},
            ],
        },
        {
            "path": "src/billing/invoices.ts",
            "id": "billing_invoices_ts",
            "community": 4,
            "rationale": "Invoice generation and delivery.",
            "symbols": [
                {"name": "createInvoice()", "rationale": "Write an invoice row and return it."},
                {
                    "name": "sendInvoiceEmail()",
                    "rationale": "Render an invoice and hand it to the email transport.",
                },
                {
                    "name": "listUserInvoices()",
                    "rationale": "Return all invoices for a user, newest first.",
                },
                {"name": "renderAndQueue()", "line": 76},
                {"name": "InvoiceNotFoundError", "inherits": "Error"},
            ],
        },
        {
            "path": "src/billing/stripeClient.ts",
            "id": "billing_stripeclient_ts",
            "community": 4,
            "rationale": "Stripe integration — charges, refunds, webhook signature verification.",
            "symbols": [
                {
                    "name": "chargeCustomer()",
                    "rationale": "Create a Stripe charge and mirror it into our billing table.",
                },
                {
                    "name": "refundCharge()",
                    "rationale": "Issue a full refund for a previous charge and log it.",
                },
                {
                    "name": "verifyWebhook()",
                    "rationale": "Validate a Stripe webhook signature and return the event body.",
                },
                {
                    "name": "handleWebhookEvent()",
                    "rationale": "Dispatch a verified Stripe webhook event to the right handler.",
                },
                {"name": "fakeStripeCharge()", "line": 105},
                {"name": "BillingError", "inherits": "Error"},
                {"name": "WebhookVerificationError", "inherits": "Error"},
            ],
        },
        {
            "path": "src/api/routes.ts",
            "id": "api_routes_ts",
            "community": 5,
            "rationale": "HTTP route wiring for the sample web app.",
            "symbols": [
                {
                    "name": "loginEndpoint()",
                    "rationale": "POST /api/auth/login — returns access + refresh tokens.",
                },
                {
                    "name": "refreshEndpoint()",
                    "rationale": "POST /api/auth/refresh — returns a new access token.",
                },
                {
                    "name": "logoutEndpoint()",
                    "rationale": "POST /api/auth/logout — revokes a refresh token.",
                },
                {"name": "createUserEndpoint()", "rationale": "POST /api/users — sign-up flow."},
                {
                    "name": "getMeEndpoint()",
                    "rationale": "GET /api/users/me — requires Authorization: Bearer header.",
                },
                {
                    "name": "deleteMeEndpoint()",
                    "rationale": "DELETE /api/users/me — soft-delete the authenticated user.",
                },
                {
                    "name": "chargeEndpoint()",
                    "rationale": "POST /api/billing/charge — charge the authenticated user.",
                },
                {
                    "name": "refundEndpoint()",
                    "rationale": "POST /api/billing/refund — admin-only refund of a charge.",
                },
                {
                    "name": "listInvoicesEndpoint()",
                    "rationale": "GET /api/billing/invoices — list invoices for the authenticated user.",
                },
                {
                    "name": "stripeWebhookEndpoint()",
                    "rationale": "POST /webhooks/stripe — entry point for Stripe events.",
                },
            ],
        },
    ],
    "imports": [
        ("src/users/crud.ts", 3, "src/db/connection.ts"),
        ("src/auth/handlers.ts", 6, "src/db/connection.ts"),
        ("src/auth/handlers.ts", 7, "src/users/crud.ts"),
        ("src/auth/handlers.ts", 8, "src/auth/jwtUtils.ts"),
        ("src/billing/invoices.ts", 3, "src/db/connection.ts"),
        ("src/billing/invoices.ts", 4, "src/users/crud.ts"),
        ("src/billing/stripeClient.ts", 5, "src/db/connection.ts"),
        ("src/billing/stripeClient.ts", 6, "src/users/crud.ts"),
        ("src/billing/stripeClient.ts", 7, "src/billing/invoices.ts"),
        ("src/api/routes.ts", 3, "src/auth/handlers.ts"),
        ("src/api/routes.ts", 9, "src/billing/invoices.ts"),
        ("src/api/routes.ts", 10, "src/billing/stripeClient.ts"),
        ("src/api/routes.ts", 16, "src/users/crud.ts"),
    ],
    "calls": [
        ("src/auth/handlers.ts", 22, "authenticateUser()", "src/users/crud.ts", "getUserByEmail()"),
        (
            "src/auth/handlers.ts",
            29,
            "authenticateUser()",
            "src/users/crud.ts",
            "updateLastLogin()",
        ),
        ("src/auth/handlers.ts", 31, "authenticateUser()", "src/auth/jwtUtils.ts", "encodeToken()"),
        ("src/auth/handlers.ts", 40, "verifySession()", "src/auth/jwtUtils.ts", "decodeToken()"),
        ("src/auth/handlers.ts", 49, "refreshSession()", "src/auth/jwtUtils.ts", "decodeToken()"),
        ("src/auth/handlers.ts", 60, "logout()", "src/db/connection.ts", "getConnection()"),
        ("src/billing/stripeClient.ts", 24, "chargeCustomer()", "src/users/crud.ts", "getUser()"),
        (
            "src/billing/stripeClient.ts",
            37,
            "chargeCustomer()",
            "src/billing/invoices.ts",
            "createInvoice()",
        ),
        ("src/billing/invoices.ts", 42, "sendInvoiceEmail()", "src/users/crud.ts", "getUser()"),
        ("src/api/routes.ts", 36, "loginEndpoint()", "src/auth/handlers.ts", "authenticateUser()"),
        ("src/api/routes.ts", 56, "createUserEndpoint()", "src/users/crud.ts", "createUser()"),
        ("src/api/routes.ts", 64, "getMeEndpoint()", "src/auth/handlers.ts", "verifySession()"),
        ("src/api/routes.ts", 65, "getMeEndpoint()", "src/users/crud.ts", "getUser()"),
        (
            "src/api/routes.ts",
            82,
            "chargeEndpoint()",
            "src/billing/stripeClient.ts",
            "chargeCustomer()",
        ),
        (
            "src/api/routes.ts",
            86,
            "refundEndpoint()",
            "src/billing/stripeClient.ts",
            "refundCharge()",
        ),
        (
            "src/api/routes.ts",
            97,
            "listInvoicesEndpoint()",
            "src/billing/invoices.ts",
            "listUserInvoices()",
        ),
        (
            "src/api/routes.ts",
            105,
            "stripeWebhookEndpoint()",
            "src/billing/stripeClient.ts",
            "verifyWebhook()",
        ),
        (
            "src/api/routes.ts",
            106,
            "stripeWebhookEndpoint()",
            "src/billing/stripeClient.ts",
            "handleWebhookEvent()",
        ),
    ],
}

# --------------------------------------------------------------------------- Go

GO_SPEC = {
    "files": [
        {
            "path": "db/connection.go",
            "id": "db_connection_go",
            "community": 1,
            "rationale": "Package db provides the fixture's database connection pool.",
            "symbols": [
                {
                    "name": "Connection",
                    "rationale": "Minimal connection interface used by the fixture.",
                },
                {
                    "name": "GetConnection()",
                    "rationale": "Return a process-wide connection to the fixture database.",
                },
                {
                    "name": "Execute()",
                    "rationale": "Run a statement and return rows plus the last inserted id.",
                },
                {"name": "Close()", "line": 47},
                {
                    "name": "ensureSchema()",
                    "rationale": "Create fixture tables if they don't exist yet.",
                },
            ],
        },
        {
            "path": "users/crud.go",
            "id": "users_crud_go",
            "community": 2,
            "rationale": "Package users provides the user model and CRUD operations.",
            "symbols": [
                {"name": "User", "rationale": "Canonical user record."},
                {
                    "name": "CreateUser()",
                    "rationale": "Insert a new user and return the created record.",
                },
                {"name": "GetUserByEmail()", "rationale": "Fetch a user by email (auth hot path)."},
                {"name": "GetUser()", "rationale": "Fetch a user by primary key."},
                {"name": "UpdateLastLogin()", "line": 63},
                {
                    "name": "DeactivateUser()",
                    "rationale": "Soft-delete a user by flipping is_active off.",
                },
            ],
        },
        {
            "path": "auth/jwt_utils.go",
            "id": "auth_jwtutils_go",
            "community": 3,
            "rationale": "Package auth provides JWT encode/decode helpers and auth handlers.",
            "symbols": [
                {
                    "name": "EncodeToken()",
                    "rationale": "Produce a signed JWT string from a claims map.",
                },
                {
                    "name": "DecodeToken()",
                    "rationale": "Verify signature + expiry and return the claims map.",
                },
                {"name": "sign()", "line": 66},
            ],
        },
        {
            "path": "auth/handlers.go",
            "id": "auth_handlers_go",
            "community": 3,
            "rationale": "Authentication handlers — login, logout, token refresh.",
            "symbols": [
                {
                    "name": "AuthenticateUser()",
                    "rationale": "Validate credentials and issue an access + refresh token pair.",
                },
                {
                    "name": "VerifySession()",
                    "rationale": "Return the user id if the access token is valid.",
                },
                {
                    "name": "RefreshSession()",
                    "rationale": "Exchange a refresh token for a new access token.",
                },
                {
                    "name": "Logout()",
                    "rationale": "Revoke a refresh token by writing it to the revocation list.",
                },
                {
                    "name": "VerifyPassword()",
                    "rationale": "Constant-time password verification against stored hash.",
                },
            ],
        },
        {
            "path": "billing/invoices.go",
            "id": "billing_invoices_go",
            "community": 4,
            "rationale": "Package billing provides invoice generation and Stripe integration.",
            "symbols": [
                {"name": "CreateInvoice()", "rationale": "Write an invoice row and return it."},
                {
                    "name": "SendInvoiceEmail()",
                    "rationale": "Render an invoice and hand it to the email transport.",
                },
                {
                    "name": "ListUserInvoices()",
                    "rationale": "Return all invoices for a user, newest first.",
                },
                {"name": "renderAndQueue()", "line": 74},
            ],
        },
        {
            "path": "billing/stripe_client.go",
            "id": "billing_stripeclient_go",
            "community": 4,
            "rationale": "Stripe integration — charges, refunds, webhook signature verification.",
            "symbols": [
                {
                    "name": "ChargeCustomer()",
                    "rationale": "Create a Stripe charge and mirror it into our billing table.",
                },
                {
                    "name": "RefundCharge()",
                    "rationale": "Issue a full refund for a previous charge and log it.",
                },
                {
                    "name": "VerifyWebhook()",
                    "rationale": "Validate a Stripe webhook signature and return the event body.",
                },
                {
                    "name": "HandleWebhookEvent()",
                    "rationale": "Dispatch a verified Stripe webhook event to the right handler.",
                },
                {"name": "fakeStripeCharge()", "line": 119},
            ],
        },
        {
            "path": "api/routes.go",
            "id": "api_routes_go",
            "community": 5,
            "rationale": "Package api wires HTTP routes for the sample web app.",
            "symbols": [
                {
                    "name": "LoginEndpoint()",
                    "rationale": "POST /api/auth/login — returns access + refresh tokens.",
                },
                {
                    "name": "RefreshEndpoint()",
                    "rationale": "POST /api/auth/refresh — returns a new access token.",
                },
                {
                    "name": "LogoutEndpoint()",
                    "rationale": "POST /api/auth/logout — revokes a refresh token.",
                },
                {"name": "CreateUserEndpoint()", "rationale": "POST /api/users — sign-up flow."},
                {
                    "name": "GetMeEndpoint()",
                    "rationale": "GET /api/users/me — requires Authorization: Bearer header.",
                },
                {
                    "name": "DeleteMeEndpoint()",
                    "rationale": "DELETE /api/users/me — soft-delete the authenticated user.",
                },
                {
                    "name": "ChargeEndpoint()",
                    "rationale": "POST /api/billing/charge — charge the authenticated user.",
                },
                {
                    "name": "RefundEndpoint()",
                    "rationale": "POST /api/billing/refund — admin-only refund of a charge.",
                },
                {
                    "name": "ListInvoicesEndpoint()",
                    "rationale": "GET /api/billing/invoices — list invoices for the authenticated user.",
                },
                {
                    "name": "StripeWebhookEndpoint()",
                    "rationale": "POST /webhooks/stripe — entry point for Stripe events.",
                },
            ],
        },
    ],
    "imports": [
        ("users/crud.go", 6, "db/connection.go"),
        ("auth/handlers.go", 8, "db/connection.go"),
        ("auth/handlers.go", 9, "users/crud.go"),
        ("billing/invoices.go", 7, "db/connection.go"),
        ("billing/invoices.go", 8, "users/crud.go"),
        ("billing/stripe_client.go", 12, "db/connection.go"),
        ("billing/stripe_client.go", 13, "users/crud.go"),
        ("api/routes.go", 6, "auth/handlers.go"),
        ("api/routes.go", 7, "billing/invoices.go"),
        ("api/routes.go", 8, "users/crud.go"),
    ],
    "calls": [
        ("auth/handlers.go", 27, "AuthenticateUser()", "users/crud.go", "GetUserByEmail()"),
        ("auth/handlers.go", 34, "AuthenticateUser()", "users/crud.go", "UpdateLastLogin()"),
        ("auth/handlers.go", 37, "AuthenticateUser()", "auth/jwt_utils.go", "EncodeToken()"),
        ("auth/handlers.go", 49, "VerifySession()", "auth/jwt_utils.go", "DecodeToken()"),
        ("auth/handlers.go", 61, "RefreshSession()", "auth/jwt_utils.go", "DecodeToken()"),
        ("auth/handlers.go", 74, "Logout()", "db/connection.go", "GetConnection()"),
        ("billing/stripe_client.go", 33, "ChargeCustomer()", "users/crud.go", "GetUser()"),
        (
            "billing/stripe_client.go",
            44,
            "ChargeCustomer()",
            "billing/invoices.go",
            "CreateInvoice()",
        ),
        ("billing/invoices.go", 43, "SendInvoiceEmail()", "users/crud.go", "GetUser()"),
        ("api/routes.go", 35, "LoginEndpoint()", "auth/handlers.go", "AuthenticateUser()"),
        ("api/routes.go", 51, "CreateUserEndpoint()", "users/crud.go", "CreateUser()"),
        ("api/routes.go", 57, "GetMeEndpoint()", "auth/handlers.go", "VerifySession()"),
        ("api/routes.go", 61, "GetMeEndpoint()", "users/crud.go", "GetUser()"),
        ("api/routes.go", 80, "ChargeEndpoint()", "billing/stripe_client.go", "ChargeCustomer()"),
        ("api/routes.go", 86, "RefundEndpoint()", "billing/stripe_client.go", "RefundCharge()"),
        (
            "api/routes.go",
            93,
            "ListInvoicesEndpoint()",
            "billing/invoices.go",
            "ListUserInvoices()",
        ),
        (
            "api/routes.go",
            102,
            "StripeWebhookEndpoint()",
            "billing/stripe_client.go",
            "VerifyWebhook()",
        ),
        (
            "api/routes.go",
            103,
            "StripeWebhookEndpoint()",
            "billing/stripe_client.go",
            "HandleWebhookEvent()",
        ),
    ],
}


# ----------------------------------------------------------------- Rust / Java

# Top-level keys graphify's Python gold carries — the Rust/Java golds are
# reshaped to match this exact set so test_polyglot_fixtures' schema check passes.
_GRAPHIFY_TOP_KEYS = (
    "directed",
    "multigraph",
    "graph",
    "nodes",
    "links",
    "hyperedges",
)


def build_builtin_gold(fixture_dir: Path) -> dict:
    """Generate a gold graph from the built-in tree-sitter extractor.

    graphify cannot parse Rust or Java, so unlike TS/Go (hand-authored to mirror
    graphify) those golds are the built-in backend's own output, reshaped into
    graphify's schema (drop ``generated_by``/``schema_version``, stamp the
    hand-authored commit sentinel). The *independent* correctness oracle is
    ``tests/test_graphgen.py``'s hand-listed expected symbols; this gold then
    serves as the parity gate's regression baseline.
    """
    from neuralmind import graphgen

    g = graphgen.build_graph(fixture_dir)
    gold = {k: g[k] for k in _GRAPHIFY_TOP_KEYS}
    gold["built_at_commit"] = COMMIT
    return gold


def main() -> None:
    for name, spec in (("sample_project_ts", TS_SPEC), ("sample_project_go", GO_SPEC)):
        fixture_dir = HERE / name
        graph = make_graph(spec, fixture_dir)
        out = fixture_dir / "graphify-out" / "graph.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(graph, indent=2) + "\n")
        print(f"wrote {out}  ({len(graph['nodes'])} nodes, {len(graph['links'])} links)")

    # Rust + Java: golds are generated from the built-in extractor (graphify
    # can't parse either). Requires the matching tree-sitter grammar to import.
    for name in (
        "sample_project_rust",
        "sample_project_java",
        "sample_project_c",
        "sample_project_cpp",
    ):
        fixture_dir = HERE / name
        graph = build_builtin_gold(fixture_dir)
        out = fixture_dir / "graphify-out" / "graph.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(graph, indent=2) + "\n")
        print(f"wrote {out}  ({len(graph['nodes'])} nodes, {len(graph['links'])} links)")


if __name__ == "__main__":
    main()
