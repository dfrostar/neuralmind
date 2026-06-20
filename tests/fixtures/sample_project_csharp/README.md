# sample_project_csharp

A tiny C# project used as a **structural parity fixture** for NeuralMind's
built-in tree-sitter backend. It mirrors the Python/Java fixtures' module shape
(auth / users / api / billing / db) so the C# extractor is gated against the
same expectations: ≥90% symbol coverage vs the hand-authored gold graph and
zero dangling edges.

## Why this fixture?

graphify cannot parse C#, so `graphify-out/graph.json` here is a **hand-authored
expected symbol set** — the types, methods, properties, fields, and enum members
a correct parser *should* recover — not a graphify export. The parity gate
(`python -m evals.parity.run`) builds this project with the built-in backend and
checks it rises to that gold.

## Shape

- `Acme.Db` — `DataStore` interface + `Connection` (implements it).
- `Acme.Users` — `User` record-ish class + `Crud` operations.
- `Acme.Auth` — `JwtUtils` signing + `Handlers` login/session flow.
- `Acme.Billing` — `StripeClient` + `Invoices`/`Invoice`.
- `Acme.Api` — `Method` enum, `Route`, and the `Routes` table that wires
  auth + billing handlers to endpoints.

Cross-file `using` directives, `: Base`/`: IInterface` inheritance, best-effort
`calls`, and `///` doc-comment rationale are all exercised.
