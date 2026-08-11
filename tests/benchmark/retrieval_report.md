# N-15 SOTA Retrieval Quality Benchmark

**Generated:** 2026-08-06 02:23:03
**Fixture:** `/home/dtfrost5/neuralmind/tests/fixtures/sample_project`
**Queries:** 19
**Judge:** ragas-stdlib-faithfulness

## Aggregate Metrics

| Metric | Value |
|--------|------:|
| Recall@1 | 0.3316 |
| Recall@3 | 0.5640 |
| Recall@5 | 0.5640 |
| Precision@5 | 0.3684 |
| MRR | 1.0000 |
| nDCG@5 | 0.8087 |
| Hit Rate | 1.0000 |
| Faithfulness | 0.0263 |
| Fact Recall | 0.0263 |
| Contradiction | 0.0000 |

## Per-Shape Breakdown

| Shape | Recall@5 | MRR | nDCG@5 | Hit Rate | Faithfulness |
|-------|---------:|----:|-------:|---------:|-------------:|
| cross-file | 0.4817 | 1.0000 | 0.7672 | 1.0000 | 0.0000 |
| focused | 0.6125 | 1.0000 | 0.8366 | 1.0000 | 0.0312 |
| identity | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.2500 |

## Per-Query Results

| # | ID | Shape | R@1 | R@3 | R@5 | P@5 | MRR | nDCG@5 | Hit | Faith |
|---|----|-------|-----|-----|-----|-----|-----|--------|-----|-------|
| 1 | `auth-flow` | cross-file | 0.20 | 0.40 | 0.40 | 0.40 | 1.00 | 0.78 | 1.0 | 0.00 |
| 2 | `api-endpoints` | focused | 0.17 | 0.33 | 0.33 | 0.40 | 1.00 | 0.75 | 1.0 | 0.25 |
| 3 | `billing-flow` | cross-file | 0.20 | 0.60 | 0.60 | 0.60 | 1.00 | 0.66 | 1.0 | 0.00 |
| 4 | `user-storage` | cross-file | 0.17 | 0.17 | 0.17 | 0.20 | 1.00 | 0.55 | 1.0 | 0.00 |
| 5 | `jwt-verify` | focused | 0.50 | 1.00 | 1.00 | 0.40 | 1.00 | 1.00 | 1.0 | 0.00 |
| 6 | `stripe-webhook` | focused | 0.33 | 0.33 | 0.33 | 0.20 | 1.00 | 0.86 | 1.0 | 0.00 |
| 7 | `create-user` | cross-file | 0.33 | 0.33 | 0.33 | 0.20 | 1.00 | 0.75 | 1.0 | 0.00 |
| 8 | `refund` | focused | 0.33 | 0.67 | 0.67 | 0.40 | 1.00 | 0.67 | 1.0 | 0.00 |
| 9 | `db-choice` | identity | 1.00 | 1.00 | 1.00 | 0.20 | 1.00 | 1.00 | 1.0 | 0.25 |
| 10 | `invoice-send` | cross-file | 0.25 | 0.75 | 0.75 | 0.60 | 1.00 | 0.95 | 1.0 | 0.00 |
| 11 | `debug-login-silent` | focused | 0.33 | 0.67 | 0.67 | 0.40 | 1.00 | 0.94 | 1.0 | 0.00 |
| 12 | `debug-webhook-reject` | focused | 0.50 | 0.50 | 0.50 | 0.20 | 1.00 | 0.92 | 1.0 | 0.00 |
| 13 | `debug-invoice-missing` | cross-file | 0.25 | 0.50 | 0.50 | 0.40 | 1.00 | 0.89 | 1.0 | 0.00 |
| 14 | `debug-token-expire` | focused | 0.50 | 1.00 | 1.00 | 0.40 | 1.00 | 0.71 | 1.0 | 0.00 |
| 15 | `refactor-add-user-field` | cross-file | 0.25 | 0.25 | 0.25 | 0.20 | 1.00 | 0.57 | 1.0 | 0.00 |
| 16 | `refactor-swap-database` | focused | 0.20 | 0.40 | 0.40 | 0.40 | 1.00 | 0.85 | 1.0 | 0.00 |
| 17 | `refactor-add-mfa` | cross-file | 0.25 | 0.75 | 0.75 | 0.60 | 1.00 | 0.83 | 1.0 | 0.00 |
| 18 | `next-after-jwt-change` | cross-file | 0.33 | 0.67 | 0.67 | 0.40 | 1.00 | 0.95 | 1.0 | 0.00 |
| 19 | `next-after-charge-change` | cross-file | 0.20 | 0.40 | 0.40 | 0.40 | 1.00 | 0.75 | 1.0 | 0.00 |

## Per-Query Module Rankings

### `auth-flow` — How does authentication work in this codebase?

**Expected:** `auth/handlers.py`, `auth/jwt_utils.py`, `api/routes.py`, `users/crud.py`, `db/connection.py`
**Ranked:** `auth/handlers.py`, `auth/jwt_utils.py`

### `api-endpoints` — What are the main API endpoints?

**Expected:** `auth/handlers.py`, `auth/jwt_utils.py`, `api/routes.py`, `billing/stripe_client.py`, `billing/invoices.py`, `users/crud.py`
**Ranked:** `api/routes.py`, `users/crud.py`

### `billing-flow` — Explain the billing flow from a user perspective.

**Expected:** `api/routes.py`, `billing/stripe_client.py`, `billing/invoices.py`, `users/crud.py`, `db/connection.py`
**Ranked:** `billing/stripe_client.py`, `api/routes.py`, `users/crud.py`

### `user-storage` — How are users stored in the database?

**Expected:** `auth/handlers.py`, `api/routes.py`, `billing/stripe_client.py`, `billing/invoices.py`, `users/crud.py`, `db/connection.py`
**Ranked:** `users/crud.py`

### `jwt-verify` — How does JWT signature verification work?

**Expected:** `auth/handlers.py`, `auth/jwt_utils.py`
**Ranked:** `auth/jwt_utils.py`, `auth/handlers.py`

### `stripe-webhook` — What happens when a Stripe webhook fires?

**Expected:** `api/routes.py`, `billing/stripe_client.py`, `db/connection.py`
**Ranked:** `billing/stripe_client.py`, `users/crud.py`

### `create-user` — How do I create a new user?

**Expected:** `api/routes.py`, `users/crud.py`, `db/connection.py`
**Ranked:** `users/crud.py`

### `refund` — Show me the refund logic.

**Expected:** `api/routes.py`, `billing/stripe_client.py`, `db/connection.py`
**Ranked:** `api/routes.py`, `billing/stripe_client.py`, `users/crud.py`

### `db-choice` — What database does this project use?

**Expected:** `db/connection.py`
**Ranked:** `db/connection.py`, `README.md`, `billing/stripe_client.py`

### `invoice-send` — How are invoices sent to users?

**Expected:** `api/routes.py`, `billing/invoices.py`, `users/crud.py`, `db/connection.py`
**Ranked:** `billing/invoices.py`, `api/routes.py`, `users/crud.py`

### `debug-login-silent` — A user login is failing without any error message — which file contains credential validation?

**Expected:** `auth/handlers.py`, `auth/jwt_utils.py`, `users/crud.py`
**Ranked:** `auth/handlers.py`, `auth/jwt_utils.py`

### `debug-webhook-reject` — Stripe webhooks are being rejected — where is the signature verified?

**Expected:** `api/routes.py`, `billing/stripe_client.py`
**Ranked:** `billing/stripe_client.py`, `users/crud.py`

### `debug-invoice-missing` — Invoices are not appearing for a user — which files handle invoice retrieval?

**Expected:** `api/routes.py`, `billing/invoices.py`, `users/crud.py`, `db/connection.py`
**Ranked:** `billing/invoices.py`, `users/crud.py`

### `debug-token-expire` — Users are being logged out unexpectedly — where is token expiry enforced?

**Expected:** `auth/handlers.py`, `auth/jwt_utils.py`
**Ranked:** `auth/handlers.py`, `auth/jwt_utils.py`

### `refactor-add-user-field` — I need to add an email_verified column to users — which files would change?

**Expected:** `auth/handlers.py`, `api/routes.py`, `users/crud.py`, `db/connection.py`
**Ranked:** `users/crud.py`

### `refactor-swap-database` — I need to replace the database backend — which file owns the connection pool?

**Expected:** `auth/handlers.py`, `billing/stripe_client.py`, `billing/invoices.py`, `users/crud.py`, `db/connection.py`
**Ranked:** `db/connection.py`, `billing/stripe_client.py`

### `refactor-add-mfa` — I want to add multi-factor authentication to the login flow — which files would I modify?

**Expected:** `auth/handlers.py`, `auth/jwt_utils.py`, `api/routes.py`, `users/crud.py`
**Ranked:** `auth/handlers.py`, `api/routes.py`, `users/crud.py`

### `next-after-jwt-change` — I just changed how JWT tokens are signed — what other files should I review?

**Expected:** `auth/handlers.py`, `auth/jwt_utils.py`, `api/routes.py`
**Ranked:** `auth/jwt_utils.py`, `auth/handlers.py`, `users/crud.py`

### `next-after-charge-change` — I updated the charge_customer function — what else commonly changes with billing?

**Expected:** `api/routes.py`, `billing/stripe_client.py`, `billing/invoices.py`, `users/crud.py`, `db/connection.py`
**Ranked:** `billing/stripe_client.py`, `users/crud.py`
