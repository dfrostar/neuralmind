# Use Case: Find the Coverage That Lies — Endpoints Tested Only in Mock Mode

## What you're solving for

Your test suite is green. But an endpoint can pass every test *in mock mode* — an
in-memory store that happily accepts any string where Postgres would reject a
non-UUID foreign key — and still throw the moment it hits a real database. That's
the `P2003` shape: three passing tests, all `SKIP_PG`-guarded, zero live coverage,
one production failure. "All tests pass" told you nothing about the path that
actually breaks.

`neuralmind gaps` cross-references the routes your app registers against the tests
that exercise them, and tells you which endpoints are *actually* covered against a
live database versus which are only pretending.

## Setup (one time)

```bash
pip install neuralmind
```

No index build required — `gaps` reads your source and test files directly.

## Run it

```bash
cd your-project
neuralmind gaps
```

```
## neuralmind gaps — live-Postgres coverage

Routes tested in-memory only (no live-DB coverage):
  POST /api/sessions            — 3 tests — all SKIP_PG  ❌
  GET  /.well-known/jwks.json   — 1 test — all SKIP_PG   ❌
Endpoints with no tests:
  POST /api/auth/jwk/rotate     ⚠️
Live-covered:
  GET  /health                  ✅
```

Read it top to bottom:

- **Mock-only (❌)** — the dangerous middle. Tests exist and pass, so CI is green,
  but nothing exercises the live DB path. `POST /api/sessions` with three
  `SKIP_PG`-guarded tests is exactly where a foreign-key bug hides.
- **Untested (⚠️)** — no test references the route at all. Honest, at least.
- **Live-covered (✅)** — a non-skipped test that touches the real DB fixture.

## How it decides

Phase 1 covers **Express + Jest** (JS/TS):

- **Routes** come from `app.get(...)` / `router.post(...)` registrations.
- **Test references** come from each `it()` / `test()` case — from both its name and
  its body — with route paths normalized across `:id` / `{id}` / `${...}` / `*`
  styles so a registration and a test reference match.
- A test **hits the real DB** when its file imports a real-DB fixture (e.g. `@/db`,
  `testDb`) and the case is not skip-guarded (`SKIP_PG`, `.skip`).

## Wire it into CI

Run it as a gate so a new mock-only endpoint fails the build instead of shipping:

```bash
neuralmind gaps | tee gaps.txt
grep -q "❌" gaps.txt && echo "::warning::endpoints lack live-DB coverage"
```

## Honest scope

Phase 1 is Express/Jest heuristics (regex over JS/TS), not a full parser — it does
not cover other frameworks yet, and route matching is best-effort on unusual path
construction. It surfaces suspects to verify, not a proof of coverage.

## Related

- [Decision provenance](./decision-provenance.md) — the "why is it like this?"
  companion to this "what did I actually test?" check.
