# PRD: C# extractor (language breadth, parity-gated)

**Status:** Draft · **Owner:** dfrostar · **Created:** 2026-06-20
**Tracking branch:** `claude/csharp-extractor`

## 1. Background & motivation

NeuralMind's built-in tree-sitter backend ships **seven** languages today —
Python, TypeScript, Go, Rust, Java, C, C++ (`neuralmind/graphgen.py`,
`_SUFFIX_LANG` → `_EXTRACTORS`). The only genuine competitive gap vs
breadth-first indexers is *language count*; the moat (Hebbian synapses,
semantic vector retrieval, L0–L3 progressive disclosure) is unaffected by it.

This PRD adds **C#** — the first of the next breadth tier (C# / Ruby / PHP from
the roadmap), one language per PR so each clears the parity gate in isolation
and gets its own docs/SEO pass. C# is the natural first pick: it maps almost
1:1 onto the existing **Java** extractor (namespaces ≈ packages; class /
interface / struct / record / enum → type nodes; `base_list` → `inherits`;
`using` → `imports_from`), so it rides a proven shape with the smallest risk.

## 2. Goals / non-goals

**Goals**
- Add C# through the existing `_EXTRACTORS` seam with **zero changes downstream
  of `graph.json`** (embedder, selector, synapses, MCP, UI untouched).
- Ship **gated**: ≥90% structural symbol coverage vs a hand-authored gold
  graph and **zero dangling edges** (`evals/parity/run.py`).
- Emit the full model where the grammar supports it: `code` nodes (file / type
  / method / field / property / enum-member) + `contains` / `imports_from` /
  `inherits` / `calls` edges + `rationale` nodes from `///` doc comments.
- Ship docs + SEO in the **same PR** (per `CLAUDE.md`).

**Non-goals**
- Compiler-accurate call/inherit resolution — the heuristic bare-name `calls`
  resolver stays best-effort (SCIP precision pass remains the exact path).
- Generics/partial-class merging, `using` aliases, reflection edges.
- Top-level statements / `Program.cs` implicit `Main` (rare in libraries).

## 3. The seam (what C# touches)

Purely additive, mirroring Java's five touch-points:

1. `_SUFFIX_LANG` — `.cs` → `csharp` (`graphgen.py`).
2. `_load_language` — `import tree_sitter_c_sharp`.
3. A `(_csharp_extract_symbols, _csharp_resolve_edges)` pass-1/pass-2 pair
   following the Java shape (pass 1 = file + type/member nodes + name tables;
   pass 2 = `imports_from` / `inherits` / `calls`).
4. Register the pair in `_EXTRACTORS`.
5. `_register_node_symbol` — the generic `_cls`/`_fn` handling already covers
   C#'s `class_by_name` / `func_by_name` rebuild on incremental update (same as
   Java, which adds no special branch).

Plus a `tests/fixtures/sample_project_csharp/` fixture mirroring the Python
fixture's module shape (auth / users / api / billing / db), a hand-authored gold
`graphify-out/graph.json`, wiring into `evals/parity/run.py` `_LANG_FIXTURES`,
and `tests/test_graphgen.py` / `tests/test_polyglot_fixtures.py` cases.

### Gold-graph note

graphify cannot parse C#, so the gold is a **hand-authored expected symbol
set** — the symbols a correct parser *should* recover, enumerated from the
fixture source independently of our implementation, keeping the gate a real
test rather than a tautology. Its schema is validated against the real Python
graphify graph by `test_polyglot_fixtures.py`, so it cannot silently drift.

## 4. Node / edge mapping (grammar-verified)

**Types** (`…_cls`): `class_declaration`, `interface_declaration`,
`struct_declaration`, `record_declaration`, `enum_declaration`. Name via the
`name` field; members in the `body` (`declaration_list`) or, for enums, the
`enum_member_declaration_list`.

**Members:**
- `method_declaration`, `constructor_declaration` → function node (`…_fn`,
  label `name()`), contained by the type.
- `property_declaration` → symbol node (`…_sym`).
- `field_declaration` → `variable_declaration` → each `variable_declarator` →
  symbol node.
- `enum_member_declaration` → symbol node.
- positional `record` `parameter`s → symbol nodes.
- nested type declarations → recurse, contained by the outer type.

**Namespaces:** both `namespace_declaration` (body `declaration_list`) and
`file_scoped_namespace_declaration` (members are trailing siblings). Types are
contained by the **file** node (matching Java, which contains types by file,
not package); the namespace string is registered as a module key.

**Edges:**
- `contains` — file→type, type→method/field/property/enum-member.
- `inherits` — `base_list` entries (`identifier` / `qualified_name` /
  `generic_name`) → resolved against `class_by_name`; external bases synthesized
  as `ext__…_cls` so the edge never dangles (mirrors Java/TS).
- `calls` — `invocation_expression`, `function` child is `identifier` (bare) or
  `member_access_expression` (last `.` segment) → matched against
  `func_by_name`, best-effort.
- `imports_from` — `using_directive` namespace → resolved against a namespace /
  type-name module table; only emitted to existing file ids (dangling-free by
  construction).
- `rationale_for` — `///` docs are `comment` nodes, so `_leading_comment_text`
  / `_attach_comment_rationale` work directly (no Java/Rust-style custom
  grabber needed).

## 5. Acceptance criteria

- [ ] `build_graph` on the fixture yields a valid graph: unique ids, **zero
      dangling edges**, communities assigned.
- [ ] Symbol coverage ≥ `SYMBOL_COVERAGE_FLOOR` (0.90) vs the gold graph.
- [ ] `contains` / `imports_from` / `inherits` / `calls` / `rationale_for` all
      present in the fixture graph.
- [ ] `///` doc comments become `rationale` nodes (fixture assertion).
- [ ] Incremental update (`update_files`) matches a full rebuild's symbol set.
- [ ] `tests/test_graphgen.py` C# class + `test_polyglot_fixtures.py` case
      green; parity gate green (`python -m evals.parity.run`).
- [ ] Grammar added to `pyproject.toml` runtime deps; `.cs` in
      `SUPPORTED_SUFFIXES`.
- [ ] Docs + SEO propagated (README, `docs/index.html`, `docs/about.html`,
      `docs/wiki/CLI-Reference.md`, a use-case touch, `RELEASE_NOTES_v*.md`,
      `pyproject.toml` keywords, `docs/sitemap.xml`).

## 6. Risks & mitigations

- **Gold-graph circularity** — author the gold from fixture *intent* before
  implementation; schema-validated against the Python graphify graph.
- **`using` false edges** — emit `imports_from` only to resolved, existing file
  ids (dangling-free by construction).
- **Grammar version drift (0.21 vs 0.23)** — handled by `_make_parser`; the C#
  loader rides the same path.
- **File-scoped vs block namespaces** — both handled; types contained by file
  so namespace style doesn't change the node tree.

## 7. Success metric

Breadth grows **7 → 8** languages, with the gated recipe proven to extend to
Ruby and PHP next without touching anything downstream of `graph.json`.
