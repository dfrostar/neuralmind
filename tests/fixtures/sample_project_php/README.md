# sample_project_php

A tiny PHP project used as a **structural parity fixture** for NeuralMind's
built-in tree-sitter backend. It mirrors the Python/Java/C#/Ruby fixtures'
module shape (auth / users / api / billing / db) so the PHP extractor is gated
against the same expectations: ≥90% symbol coverage vs the hand-authored gold
graph and zero dangling edges.

## Why this fixture?

graphify cannot parse PHP, so `graphify-out/graph.json` here is a **hand-authored
expected symbol set** — the classes, interfaces, methods, properties, and
constants a correct parser *should* recover — not a graphify export. The parity
gate (`python -m evals.parity.run`) builds this project with the built-in
backend and checks it rises to that gold.

## Shape

- `src/Db/Connection.php` — `DataStore` interface + `Connection` (implements it).
- `src/Users/` — `User` + `Crud` static operations.
- `src/Auth/` — `JwtUtils` signing + `Handlers` login/session flow.
- `src/Billing/` — `StripeClient` + `Invoices`/`Invoice`.
- `src/Api/Routes.php` — `Method` interface of constants, `Route`, and the
  `Routes` table that wires auth + billing handlers to endpoints.

Cross-file `use` imports (resolved by class name, like Java), `extends`/
`implements` inheritance, best-effort `calls` (`Class::method` and
`$obj->method`), and `/** */` doc-comment rationale are all exercised.
