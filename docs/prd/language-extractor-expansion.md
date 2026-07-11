# PRD: Language-extractor expansion (competitive parity, breadth)

**Status:** Draft · **Owner:** dfrostar · **Created:** 2026-06-18
**Tracking branch:** `claude/codebase-memory-mcp-review-3r2mri`

## 1. Background & motivation

A competitive review of `DeusData/codebase-memory-mcp` (6.6k★, C, "158
languages") surfaced that NeuralMind's only genuine disadvantages are
**language breadth** and **packaging weight** — both commodity concerns, not
moat. Today the built-in tree-sitter backend (`neuralmind/graphgen.py`) ships
**three** languages: Python, TypeScript, Go (`_SUFFIX_LANG`, `_EXTRACTORS`).

The competitor's "158" is a vanity count — its own paper rates most languages
sub-75% ("Functional" tier) and macro-heavy C at 0.58. We do **not** need 158.
The 10–12 languages that cover the overwhelming majority of real repositories
(Rust, Java, C/C++, C#, Ruby, PHP, Kotlin, Swift, plus the three we have)
neutralize the breadth gap entirely while keeping our actual moat — the
Hebbian **synapse layer** (`neuralmind/synapses.py`), semantic vector
retrieval, and progressive L0–L3 disclosure — which the competitor lacks.

This PRD covers the **breadth** initiative. Packaging (ChromaDB-free default)
and cold-build parallelism are tracked separately.

## 2. Goals / non-goals

**Goals**
- Add languages through the existing `_EXTRACTORS` seam with **zero changes
  downstream of `graph.json`** (embedder, selector, synapses, MCP, UI).
- Each language ships **gated**: ≥90% structural symbol coverage vs a
  committed gold graph and **zero dangling edges** (`evals/parity/run.py`).
- Each language emits the full node/edge model where the grammar supports it:
  `code` nodes (file / type / function / field) + `contains` / `imports_from`
  / `inherits` / `calls` edges + `rationale` nodes from doc comments.
- Ship docs + SEO in the **same PR** as the feature (per `CLAUDE.md`).

**Non-goals**
- Compiler-accurate call/inherit resolution. The heuristic `calls` resolver
  (bare-name match) is intentionally best-effort; the optional SCIP precision
  pass (`neuralmind/precision.py`) remains the path to exactness.
- Macro/`cfg!` expansion, runtime/reflection edges (the competitor doesn't do
  these either; their paper concedes "static structure only").
- Hitting the competitor's raw C indexing throughput (different workload — our
  cost center is embedding, not parsing).

## 3. The seam (what a new language touches)

Adding a language is **purely additive** — five touch-points, all already
designed for extension:

1. `_SUFFIX_LANG` — register suffix(es) → language name (`graphgen.py:65`).
2. `_load_language` — import the vendored grammar (`graphgen.py:81`).
3. A `(_extract_symbols, _resolve_edges)` pass-1/pass-2 pair following the
   Go/TS shape (pass 1 = file + symbol nodes + name-table registration; pass 2
   = cross-symbol `imports_from` / `inherits` / `calls`).
4. Register the pair in `_EXTRACTORS` (`graphgen.py:1021`).
5. `_register_node_symbol` — language-specific module-key rebuild for the
   incremental updater (`graphgen.py:1049`).

Plus: a `tests/fixtures/sample_project_<lang>/` fixture mirroring the Python
fixture's module shape (auth / users / api / billing / db), a hand-authored
gold `graphify-out/graph.json`, a `benchmark_queries_<lang>.json` mirroring the
Python query set, wiring into `evals/parity/run.py` `_LANG_FIXTURES`, and the
`tests/test_polyglot_fixtures.py` / `tests/test_graphgen.py` cases.

### Gold-graph note (important)

The parity gate scores a new language against a committed
`graphify-out/graph.json` (`evals/parity/run.py:336`). For TS/Go that file was
produced by graphify itself. **graphify cannot parse Rust (or most target
languages)**, so for every new language the gold is a **hand-authored expected
symbol set** — the symbols a correct parser *should* recover, enumerated from
the fixture source independently of our implementation. This keeps the gate a
real test (implementation must rise to the gold) rather than a tautology. The
gold's schema is validated against the real Python graphify graph by
`test_polyglot_fixtures.py`, so it cannot silently drift.

## 4. Acceptance criteria (per language)

- [ ] `graphgen.build_graph` on the fixture yields a valid graph: unique ids,
      **zero dangling edges**, communities assigned.
- [ ] Symbol coverage ≥ `SYMBOL_COVERAGE_FLOOR` (0.90) vs the gold graph.
- [ ] All five edge relations present where the language supports them
      (`contains` always; `imports_from`, `inherits`, `calls`, `rationale_for`
      where applicable).
- [ ] Doc comments become `rationale` nodes.
- [ ] Incremental update (`update_files`) matches a full rebuild's symbol set.
- [ ] `tests/test_graphgen.py` language class + `test_polyglot_fixtures.py`
      case green; parity gate green.
- [ ] Grammar added to `pyproject.toml` runtime deps; suffix in
      `SUPPORTED_SUFFIXES`.
- [ ] Docs + SEO propagated (README, `docs/index.html`, `docs/about.html`,
      `docs/wiki/CLI-Reference.md`, a use-case touch, `RELEASE_NOTES_v*.md`,
      `pyproject.toml` keywords, `docs/sitemap.xml`).

## 5. Phasing

| Phase | Language | Why first | Edge richness |
|------:|----------|-----------|---------------|
| **1** | **Rust** | High demand; clean `struct`/`enum`/`trait`/`impl` map; `impl Trait for Type` gives a first-class `inherits` edge; strong vendored grammar. **This PR.** | full |
| 2 | Java | Huge footprint; most regular class/method/`extends`/`implements` map | full |
| 3 | C / C++ | Largest raw demand but macro-heavy (competitor's weak spot) — ship structural-first, accept a lower tier honestly | partial |
| 4 | Ruby | Dynamic; clean class/method, weak call edges | partial |

Languages ship one-per-PR so each clears the gate in isolation and gets its
own docs/SEO pass.

## 6. Phase 1 — Rust (this PR)

**Node mapping**
- `function_item` → function node (`…_fn`, label `name()`).
- `struct_item` / `enum_item` / `union_item` / `trait_item` / `type_item` →
  type node (`…_cls`).
- `impl_item` methods (`function_item` / `function_signature_item` inside
  `declaration_list`) → function nodes contained by the impl's **type** node.
- struct `field_declaration` → field sym node; `enum_variant` → sym node;
  `const_item` / `static_item` → sym node.
- inline `mod_item` → descend, attaching items to the module's file node.

**Edges**
- `contains` — file→type/fn/sym, type→method/field/variant.
- `inherits` — `impl Trait for Type` (the `trait`/`type` fields) → edge
  `Type → Trait`; external traits synthesized as nodes (mirrors TS behaviour)
  so the edge never dangles.
- `calls` — `call_expression`, last path segment matched against
  `func_by_name` (best-effort, same heuristic as Go/TS).
- `imports_from` — `use_declaration`, resolved best-effort against a Rust
  module-key table (file stem / parent dir); only emitted to existing file ids
  so it never dangles.
- `rationale_for` — Rust doc comments are `line_comment`/`block_comment`
  nodes (NOT `comment`), so a Rust-specific leading-doc grabber is required;
  `_leading_comment_text` does not see them.

**Fixture:** `tests/fixtures/sample_project_rust/` mirroring the Python
fixture: `src/auth/{handlers,jwt_utils}.rs`, `src/users/crud.rs`,
`src/api/routes.rs`, `src/billing/{stripe_client,invoices}.rs`,
`src/db/connection.rs`, `src/lib.rs`, `Cargo.toml`, `README.md`, plus a
hand-authored `graphify-out/graph.json` gold and `benchmark_queries_rust.json`.

## 7. Risks & mitigations

- **Gold-graph circularity** — mitigated by authoring the gold from fixture
  *intent* before implementation and schema-validating it against the real
  Python graphify graph.
- **`use` resolution false edges** — mitigated by emitting `imports_from`
  only to resolved, existing file ids (dangling-free by construction).
- **Grammar API churn (tree-sitter 0.21 vs 0.23+)** — already handled by
  `_make_parser`; the Rust loader rides the same path.
- **Doc-comment node-type drift** — covered by a fixture assertion that a
  `///` comment becomes a `rationale` node.

## 8. Success metric

Breadth gap closed from **3 → 4** languages this PR, with a repeatable,
gated recipe proven to scale to the Phase 2–4 backlog without touching
anything downstream of `graph.json`.
