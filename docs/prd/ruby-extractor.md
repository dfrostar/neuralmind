# PRD: Ruby extractor (language breadth, parity-gated)

**Status:** Draft · **Owner:** dfrostar · **Created:** 2026-06-20
**Tracking branch:** `claude/ruby-extractor`

## 1. Background & motivation

NeuralMind's built-in tree-sitter backend ships **eight** languages today —
Python, TypeScript, Go, Rust, Java, C, C++, C# (`neuralmind/graphgen.py`,
`_SUFFIX_LANG` → `_EXTRACTORS`). This PRD adds **Ruby**, the second of the
breadth tier (C# / Ruby / PHP), one language per PR so each clears the parity
gate in isolation with its own docs/SEO pass.

Ruby is dynamic — class/module/method *structure* is clean and recovers well,
but call resolution is inherently best-effort (no static receiver types). That's
disclosed honestly; the structural layer is what the parity gate proves.

## 2. Goals / non-goals

**Goals**
- Add Ruby through the existing `_EXTRACTORS` seam with **zero changes
  downstream of `graph.json`**.
- Ship **gated**: ≥90% structural symbol coverage vs a hand-authored gold and
  **zero dangling edges** (`evals/parity/run.py`).
- Emit the model where the grammar supports it: `code` nodes (file / class /
  module / method / constant) + `contains` / `imports_from` / `inherits` /
  `calls` edges + `rationale` nodes from `#` doc comments.
- Ship docs + SEO in the **same PR** (per `CLAUDE.md`).

**Non-goals**
- Compiler-accurate call resolution — bare-name best-effort, same as the other
  languages; dynamic dispatch / metaprogramming (`define_method`, `method_missing`)
  is out of scope.
- Mixins as inheritance — `include`/`extend`/`prepend` are not modelled as
  `inherits` (only `class Foo < Bar` is); a follow-up could add them.
- `attr_accessor`-generated accessors and instance variables aren't emitted as
  fields (Ruby has no static field declarations); **constants** are the symbol
  layer.

## 3. The seam (what Ruby touches)

Additive, mirroring the C#/Java touch-points:

1. `_SUFFIX_LANG` — `.rb` → `ruby`.
2. `_load_language` — `import tree_sitter_ruby`.
3. A `(_ruby_extract_symbols, _ruby_resolve_edges)` pass-1/pass-2 pair.
4. Register the pair in `_EXTRACTORS`.
5. `_register_node_symbol` — the generic `_cls`/`_fn` handling already covers
   Ruby's `class_by_name` / `func_by_name` rebuild on incremental update.

Plus a `tests/fixtures/sample_project_ruby/` fixture mirroring the Python
fixture's module shape, a hand-authored gold, `_LANG_FIXTURES` + `_gen_graph.py`
wiring, and `tests/test_graphgen.py::RubyTests`.

## 4. Node / edge mapping (grammar-verified)

- **Types** (`…_cls`): `class` and `module` declarations (name via the `name`
  field, `scope_resolution` `Acme::Foo` → simple name; members in the
  `body_statement`; nested types recurse).
- **Methods** (`…_fn`): `method` (`def foo`) and `singleton_method`
  (`def self.foo`).
- **Constants** (`…_sym`): an `assignment` whose left side is a `constant`
  (`ATTEMPTS = 3`, module constant groups like `GET = "GET"`).
- **`require_relative` → `imports_from`** — the string arg is resolved against
  the requiring file's directory (same relative-path resolver as TS); emitted
  only to existing file ids, so dangling-free by construction. `require` of a
  gem/stdlib is external and skipped.
- **`class Foo < Bar` → `inherits`** — resolved against the class table;
  external bases synthesized as `ext__…_cls` so the edge never dangles.
- **`#` doc comments → `rationale`** — `_clean_comment` now also strips a
  leading `#`, so the comment marker doesn't leak into rationale text (no effect
  on the other languages, which don't use `#`).
- **Calls** — `call` nodes (`recv.method` or bare `method(...)`), matched by
  method name against `func_by_name`, best-effort.

## 5. Acceptance criteria

- [ ] `build_graph` on the fixture yields a valid graph: unique ids, **zero
      dangling edges**, communities assigned.
- [ ] Symbol coverage ≥ `SYMBOL_COVERAGE_FLOOR` (0.90) vs the gold graph.
- [ ] `contains` / `imports_from` / `inherits` / `calls` / `rationale_for` all
      present.
- [ ] `#` doc comments become `rationale` nodes with the `#` marker stripped.
- [ ] Incremental update (`update_files`) matches a full rebuild's symbol set.
- [ ] `RubyTests` + parity gate green (`python -m evals.parity.run`).
- [ ] Grammar in `pyproject.toml` runtime deps; `.rb` in `SUPPORTED_SUFFIXES`.
- [ ] Docs + SEO propagated (README, `docs/index.html`, `docs/about.html`,
      `docs/wiki/CLI-Reference.md`, a use-case touch, `RELEASE_NOTES_v*.md`,
      `pyproject.toml` keywords).

## 6. Success metric

Breadth grows **8 → 9** languages, with the gated recipe proven again and ready
to extend to PHP next without touching anything downstream of `graph.json`.
