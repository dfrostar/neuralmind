# PRD: PHP extractor (language breadth, parity-gated)

**Status:** Draft · **Owner:** dfrostar · **Created:** 2026-06-20
**Tracking branch:** `claude/php-extractor`

## 1. Background & motivation

NeuralMind's built-in tree-sitter backend ships **nine** languages today —
Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby. This PRD adds **PHP**, the
third and final language of the breadth tier (C# / Ruby / PHP), one language per
PR so each clears the parity gate in isolation with its own docs/SEO pass.

PHP maps almost 1:1 onto the proven **Java** extractor plus a namespace layer:
`class`/`interface`/`trait`/`enum` → type nodes; `extends`/`implements` →
`inherits`; `use` → `imports_from` (resolved by class name, exactly like Java
imports). It rides a proven shape at the smallest risk.

## 2. Goals / non-goals

**Goals**
- Add PHP through the existing `_EXTRACTORS` seam with **zero changes downstream
  of `graph.json`**.
- Ship **gated**: ≥90% structural symbol coverage vs a hand-authored gold and
  **zero dangling edges** (`evals/parity/run.py`).
- Emit the model where the grammar supports it: `code` nodes (file / class /
  interface / trait / enum / method / property / constant / enum-case) +
  `contains` / `imports_from` / `inherits` / `calls` edges + `rationale` nodes
  from `/** */` doc comments.
- Ship docs + SEO in the **same PR** (per `CLAUDE.md`).

**Non-goals**
- Compiler-accurate call resolution — bare-name best-effort, same as the other
  languages (the `$obj->method` receiver type isn't resolved).
- `require`/`include` path-based imports — `use` (namespace import) is the edge
  source, resolved by class name like Java; `require` of a path is not modelled.
- Traits-as-inheritance via `use TraitName;` inside a class body, dynamic
  `$$var` access, and variadic/heredoc edge cases.

## 3. The seam (what PHP touches)

Additive, mirroring the Java/C#/Ruby touch-points:

1. `_SUFFIX_LANG` — `.php` → `php`.
2. `_load_language` — `import tree_sitter_php` (`Language(ts.language_php())`).
3. A `(_php_extract_symbols, _php_resolve_edges)` pass-1/pass-2 pair.
4. Register the pair in `_EXTRACTORS`.
5. `_register_node_symbol` — the generic `_cls`/`_fn` handling already covers
   PHP's `class_by_name` / `func_by_name` rebuild on incremental update.

Plus a `tests/fixtures/sample_project_php/` fixture (under `src/`, not `lib/` —
the repo `.gitignore` ignores `lib/`), a hand-authored gold, `_LANG_FIXTURES` +
`_gen_graph.py` wiring, and `tests/test_graphgen.py::PhpTests`.

## 4. Node / edge mapping (grammar-verified)

- **Types** (`…_cls`): `class_declaration`, `interface_declaration`,
  `trait_declaration`, `enum_declaration` (name field; `declaration_list` body).
- **Methods** (`…_fn`): `method_declaration` and top-level `function_definition`.
- **Properties** (`…_sym`): `property_declaration` → `property_element` →
  `variable_name` (the leading `$` is stripped from the label).
- **Constants** (`…_sym`): `const_declaration` → `const_element` name; **enum
  cases** → `enum_case` name.
- **`use` → `imports_from`** — `namespace_use_declaration` →
  `namespace_use_clause`; resolved against the class-name / FQN module table
  (the imported `Acme\Db\Connection` matches the file that declares it), emitted
  only to existing file ids → dangling-free.
- **`extends` / `implements` → `inherits`** — `base_clause` /
  `class_interface_clause`; external bases synthesized so the edge never dangles.
- **`/** */` doc comments → `rationale`** — they are `comment` nodes, so
  `_attach_comment_rationale` works directly (markers stripped by `_clean_comment`).
- **Calls** — `scoped_call_expression` (`Class::method`), `member_call_expression`
  (`$obj->method`), and `function_call_expression` (bare), matched by method name
  against `func_by_name`, best-effort.

## 5. Acceptance criteria

- [ ] `build_graph` on the fixture yields a valid graph: unique ids, **zero
      dangling edges**, communities assigned.
- [ ] Symbol coverage ≥ `SYMBOL_COVERAGE_FLOOR` (0.90) vs the gold graph.
- [ ] `contains` / `imports_from` / `inherits` / `calls` / `rationale_for` all
      present.
- [ ] `/** */` doc comments become `rationale` nodes with markers stripped.
- [ ] Incremental update (`update_files`) matches a full rebuild's symbol set.
- [ ] `PhpTests` + parity gate green (`python -m evals.parity.run`).
- [ ] Grammar in `pyproject.toml` runtime deps; `.php` in `SUPPORTED_SUFFIXES`.
- [ ] Docs + SEO propagated (README, `docs/index.html`, `docs/about.html`,
      `docs/wiki/CLI-Reference.md`, a use-case touch, `RELEASE_NOTES_v*.md`,
      `pyproject.toml` keywords).

## 6. Success metric

Breadth grows **9 → 10** languages, completing the C# / Ruby / PHP breadth tier
with the gated recipe proven across five additive languages without touching
anything downstream of `graph.json`.
