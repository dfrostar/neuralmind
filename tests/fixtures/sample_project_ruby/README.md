# sample_project_ruby

A tiny Ruby project used as a **structural parity fixture** for NeuralMind's
built-in tree-sitter backend. It mirrors the Python/Java/C# fixtures' module
shape (auth / users / api / billing / db) so the Ruby extractor is gated against
the same expectations: ≥90% symbol coverage vs the hand-authored gold graph and
zero dangling edges.

## Why this fixture?

graphify cannot parse Ruby, so `graphify-out/graph.json` here is a **hand-authored
expected symbol set** — the classes, modules, methods, and constants a correct
parser *should* recover — not a graphify export. The parity gate
(`python -m evals.parity.run`) builds this project with the built-in backend and
checks it rises to that gold.

## Shape

- `src/db/connection.rb` — `DataStore` base class + `Connection` (`< DataStore`).
- `src/users/` — `User` + `Crud` class methods.
- `src/auth/` — `JwtUtils` signing + `Handlers` login/session flow.
- `src/billing/` — `StripeClient` + `Invoices`/`Invoice`.
- `src/api/routes.rb` — `Method` module of constants, `Route`, and the `Routes`
  table that wires auth + billing handlers to endpoints.

Cross-file `require_relative`, `class Foo < Bar` inheritance, best-effort `calls`,
and `#` doc-comment rationale are all exercised. Ruby is dynamic, so call edges
are best-effort (no receiver-type resolution) — disclosed honestly.
