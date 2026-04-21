# Graph Report - /home/runner/work/neuralmind/neuralmind/tests/fixtures/sample_project  (2026-04-21)

## Corpus Check
- 13 files · ~2,204 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 115 nodes · 193 edges · 16 communities detected
- Extraction: 75% EXTRACTED · 25% INFERRED · 0% AMBIGUOUS · INFERRED: 48 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]

## God Nodes (most connected - your core abstractions)
1. `get_connection()` - 17 edges
2. `TokenExpiredError` - 14 edges
3. `decode_token()` - 9 edges
4. `authenticate_user()` - 8 edges
5. `verify_session()` - 8 edges
6. `charge_customer()` - 8 edges
7. `get_user()` - 7 edges
8. `refresh_session()` - 6 edges
9. `InvalidTokenError` - 6 edges
10. `encode_token()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `Revoke a refresh token by writing it to the revocation list.` --uses--> `TokenExpiredError`  [INFERRED]
  /home/runner/work/neuralmind/neuralmind/tests/fixtures/sample_project/auth/handlers.py → /home/runner/work/neuralmind/neuralmind/tests/fixtures/sample_project/auth/jwt_utils.py
- `create_user()` --calls--> `get_connection()`  [INFERRED]
  /home/runner/work/neuralmind/neuralmind/tests/fixtures/sample_project/users/crud.py → /home/runner/work/neuralmind/neuralmind/tests/fixtures/sample_project/db/connection.py
- `create_user_endpoint()` --calls--> `create_user()`  [INFERRED]
  /home/runner/work/neuralmind/neuralmind/tests/fixtures/sample_project/api/routes.py → /home/runner/work/neuralmind/neuralmind/tests/fixtures/sample_project/users/crud.py
- `get_user_by_email()` --calls--> `get_connection()`  [INFERRED]
  /home/runner/work/neuralmind/neuralmind/tests/fixtures/sample_project/users/crud.py → /home/runner/work/neuralmind/neuralmind/tests/fixtures/sample_project/db/connection.py
- `authenticate_user()` --calls--> `get_user_by_email()`  [INFERRED]
  /home/runner/work/neuralmind/neuralmind/tests/fixtures/sample_project/auth/handlers.py → /home/runner/work/neuralmind/neuralmind/tests/fixtures/sample_project/users/crud.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.17
Nodes (18): get_connection(), Return a thread-local connection to the fixture database.      The schema is cre, create_invoice(), Write an invoice row and return it., BillingError, charge_customer(), _fake_stripe_charge(), handle_webhook_event() (+10 more)

### Community 1 - "Community 1"
Cohesion: 0.22
Nodes (16): Exception, authenticate_user(), InvalidCredentialsError, InvalidTokenError, Authentication handlers — login, logout, token refresh., Validate credentials and issue an access + refresh token pair.      Looks the us, Return the user id if the access token is valid; raise if not., Exchange a refresh token for a new access token. (+8 more)

### Community 2 - "Community 2"
Cohesion: 0.12
Nodes (15): charge_endpoint(), create_user_endpoint(), get_me_endpoint(), login_endpoint(), HTTP route wiring for the sample web app., Minimal decorator recording a (method, path, handler) tuple., POST /api/auth/login — returns access + refresh tokens., POST /api/auth/refresh — returns a new access token. (+7 more)

### Community 3 - "Community 3"
Cohesion: 0.23
Nodes (12): _b64url(), _b64url_decode(), decode_token(), encode_token(), InvalidSignatureError, MalformedTokenError, JWT encode/decode helpers., Produce a signed JWT string from a claims dict.      Expiry should be passed as (+4 more)

### Community 4 - "Community 4"
Cohesion: 0.2
Nodes (11): create_user(), get_user(), get_user_by_email(), User model + CRUD operations., Canonical user record., Insert a new user and return the created record., Fetch a user by email, returning a raw dict (for auth hot path speed)., Fetch a user by primary key. (+3 more)

### Community 5 - "Community 5"
Cohesion: 0.2
Nodes (11): InvoiceNotFoundError, list_user_invoices(), Invoice generation and delivery., Render an invoice and hand it to the email transport.      In production this wo, Return all invoices for a user, newest first., Stand-in for the real mail-queue call., Raised when referencing a missing invoice., _render_and_queue() (+3 more)

### Community 6 - "Community 6"
Cohesion: 0.33
Nodes (6): POST /webhooks/stripe — entry point for Stripe events., stripe_webhook_endpoint(), Raised when a Stripe webhook signature does not match., Validate a Stripe webhook signature and return the event body.      Stripe-Signa, verify_webhook(), WebhookVerificationError

### Community 7 - "Community 7"
Cohesion: 0.33
Nodes (5): close_all(), _ensure_schema(), Database connection pool.  Uses SQLite for the fixture (zero external dependenci, Close the thread-local connection, if any., Create fixture tables if they don't exist yet.

### Community 8 - "Community 8"
Cohesion: 0.5
Nodes (4): logout(), Revoke a refresh token by writing it to the revocation list., logout_endpoint(), POST /api/auth/logout — revokes a refresh token.

### Community 9 - "Community 9"
Cohesion: 0.5
Nodes (4): deactivate_user(), Soft-delete a user by flipping is_active off., delete_me_endpoint(), DELETE /api/users/me — soft-delete the authenticated user.

### Community 10 - "Community 10"
Cohesion: 1.0
Nodes (0): 

### Community 11 - "Community 11"
Cohesion: 1.0
Nodes (0): 

### Community 12 - "Community 12"
Cohesion: 1.0
Nodes (0): 

### Community 13 - "Community 13"
Cohesion: 1.0
Nodes (0): 

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (0): 

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **43 isolated node(s):** `User model + CRUD operations.`, `Canonical user record.`, `Insert a new user and return the created record.`, `Fetch a user by email, returning a raw dict (for auth hot path speed).`, `Fetch a user by primary key.` (+38 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 10`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 11`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 12`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 13`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_connection()` connect `Community 0` to `Community 4`, `Community 5`, `Community 7`, `Community 8`, `Community 9`?**
  _High betweenness centrality (0.132) - this node is a cross-community bridge._
- **Why does `TokenExpiredError` connect `Community 1` to `Community 8`, `Community 3`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Why does `verify_session()` connect `Community 1` to `Community 9`, `Community 2`, `Community 3`, `Community 5`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `get_connection()` (e.g. with `create_user()` and `get_user_by_email()`) actually correct?**
  _`get_connection()` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `TokenExpiredError` (e.g. with `InvalidCredentialsError` and `InvalidTokenError`) actually correct?**
  _`TokenExpiredError` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `decode_token()` (e.g. with `verify_session()` and `refresh_session()`) actually correct?**
  _`decode_token()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `authenticate_user()` (e.g. with `get_user_by_email()` and `update_last_login()`) actually correct?**
  _`authenticate_user()` has 4 INFERRED edges - model-reasoned connections that need verification._