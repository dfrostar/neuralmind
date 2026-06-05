# NeuralMind Benchmark Fixture — TypeScript

A small but realistic TypeScript web-application stub used as a hermetic
fixture for the **polyglot** retrieval-quality suite (issue #173, Epic E2.2).
It mirrors the Python fixture (`tests/fixtures/sample_project`) domain-for-domain
so top-k retrieval hit-rate can be measured **per language**, not Python-only.

## Why this fixture?

- Mirrors the Python fixture's domains: auth (login + JWT), billing
  (Stripe charges, invoices), users (model + CRUD), api (HTTP route wiring),
  db (connection pool).
- Large enough to have **cross-file relationships** (auth depends on users +
  jwtUtils, billing depends on users, api wires everything together).
- Small enough that every CI run is fast (~450 lines across 7 source files).
- Fully static — no runtime dependencies required for indexing.

## Layout

```
sample_project_ts/
├── src/
│   ├── auth/        # handlers.ts (login/logout/refresh), jwtUtils.ts
│   ├── billing/     # stripeClient.ts (charge/refund/webhook), invoices.ts
│   ├── users/       # crud.ts (User + CRUD)
│   ├── api/         # routes.ts (HTTP route wiring)
│   └── db/          # connection.ts (connection pool)
├── graphify-out/
│   └── graph.json   # hand-authored knowledge graph (see below)
├── package.json
└── README.md
```

The matching query + gold-module set lives at
`tests/fixtures/benchmark_queries_ts.json` (same shape as
`benchmark_queries.json`).

## How `graph.json` was produced — IMPORTANT

graphify (the upstream tree-sitter graph extractor) is **not installed in this
repo's CI** — it is a single-maintainer dependency that v0.14 plans to decouple
(`docs/NEXT-RELEASE-PLAN.md`). So this `graph.json` was **hand-authored** by
`tests/fixtures/_gen_graph.py`, which emits the *exact same schema* graphify
produces for the Python fixture
(`neuralmind/demo_data/sample_project/graphify-out/graph.json`):

- `nodes`: `code` (file/function/class/interface), `rationale` (doc-comment
  summary), `document` (markdown) — each with `label, file_type, source_file,
  source_location, id, community, norm_label`.
- `links`: `contains` (file→symbol), `imports_from` (file→file), `calls`
  (symbol→symbol), `rationale_for` (rationale→symbol), `inherits` (class→base) —
  each with `relation, confidence, source_file, source_location, weight,
  source, target, confidence_score`.

Symbol `source_location` line numbers are **derived from the real source files**
at generation time, so they stay accurate.

> This is a faithful approximation of graphify's output shape, **not** a
> byte-identical reproduction. It is intended to let the retrieval-quality
> harness run without graphify present. The eval harness only depends on the
> `source_file` strings matching the gold modules in `benchmark_queries_ts.json`,
> which the generator guarantees.

### Regenerating from this script (no graphify needed)

```bash
python tests/fixtures/_gen_graph.py
```

### Regenerating with real graphify (preferred once available)

```bash
npm install        # if a graphify TS toolchain is wired up
graphify update tests/fixtures/sample_project_ts
```

Then the embedding DB is built by NeuralMind:

```bash
neuralmind build tests/fixtures/sample_project_ts --force
```
