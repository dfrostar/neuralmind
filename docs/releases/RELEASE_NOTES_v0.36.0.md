# NeuralMind v0.36.0 — Ruby joins the bundled backend (nine languages)

**Release Date:** June 2026

## TL;DR

The bundled tree-sitter backend now indexes **Ruby** (`.rb`) — taking NeuralMind
to **nine languages** (Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby) with
**no external tooling**. It passes the same structural-parity gate as
Rust/Java/C/C++/C#: **46/46 symbols (100% structural coverage) vs the committed
gold, zero dangling edges**.

```bash
neuralmind build /path/to/your/ruby/project   # bundled — nothing extra to install
```

## Why this one matters

Language breadth is the one place breadth-first indexers genuinely lead — and the
only competitive gap that doesn't touch NeuralMind's moat (Hebbian synapses,
semantic vector retrieval, L0–L3 progressive disclosure are all unaffected by
language count). Ruby is the second pick of the breadth tier (C# / Ruby / PHP):
its class/module/method **structure** is clean and recovers well, so the
structural layer the parity gate proves is solid — and Ruby's dynamism (no static
receiver types) is disclosed honestly rather than overclaimed. One language per
PR, each clearing the parity gate in isolation with its own docs/SEO pass.

## What it indexes

- **Types** — `class` and `module` declarations become type nodes (name via the
  `name` field, `Acme::Foo` scope-resolution → simple name; nested types recurse,
  contained by the outer type).
- **Methods** — `def foo` (`method`) and `def self.foo` (`singleton_method`)
  become function nodes.
- **Constants** — an `assignment` whose left side is a `constant`
  (`ATTEMPTS = 3`, module constant groups like `GET = "GET"`) becomes a symbol
  node. Ruby has no static field declarations, so **constants are the symbol
  layer**.
- **`require_relative` → `imports_from` edges.** The string arg is resolved
  against the requiring file's directory (the same relative-path resolver as TS);
  edges are emitted **only to existing file ids**, so they're dangling-free by
  construction. A `require` of a gem/stdlib is external and skipped.
- **Inheritance** — `class Foo < Bar` produces an `inherits` edge, resolved
  against the class table; external bases are synthesized so the edge never
  dangles (mirrors Java/TS).
- **`#` doc comments → the `rationale` layer.** A leading `#` marker is stripped
  so it doesn't leak into rationale text, exactly like Javadoc / Rust `///`.
- **Calls** — bare-name best-effort, same heuristic as the other languages; the
  opt-in **SCIP precision pass** remains the path to compiler-accurate edges.

## Honestly out of scope (disclosed, not hidden)

So you know exactly what you're getting:

- **Compiler-accurate call resolution isn't done** — Ruby is dynamic (no static
  receiver types), so `calls` stays bare-name best-effort and dynamic dispatch /
  metaprogramming (`define_method`, `method_missing`) isn't resolved. The SCIP
  precision pass remains the exact path to compiler-accurate edges.
- **Mixins aren't modelled as inheritance** — `include`/`extend`/`prepend` are
  **not** emitted as `inherits` edges (only `class Foo < Bar` is); a follow-up
  could add them.
- **`attr_accessor` accessors and instance variables aren't emitted as fields** —
  Ruby has no static field declarations, so the generated accessors and ivars
  aren't synthesized; **constants** are the symbol layer.

These are deliberate MVP boundaries, tracked as follow-ups. The structural-parity
gate proves the in-scope coverage is real, not aspirational.

## Per-agent expectations

| Agent | What changes in v0.36.0 |
|-------|--------------------------|
| **All** | `neuralmind build` now indexes Ruby projects out of the box; retrieval, progressive disclosure, and the synapse layer work identically to the other eight languages. |
| **Claude Code / Cursor / Cline / generic MCP** | No config change — drop NeuralMind on a Ruby repo and query it. `.rb` files are picked up automatically. |

## What ships

- **`neuralmind/graphgen.py`** — a `ruby` extractor behind the existing
  `_SUFFIX_LANG` → `_EXTRACTORS` seam (a pass-1/pass-2 pair following the Java/C#
  shape), with `.rb` registered in `SUPPORTED_SUFFIXES`.
- **`tree-sitter-ruby`** added to the runtime deps so the grammar is bundled.
- Fixture `tests/fixtures/sample_project_ruby` + a committed gold graph,
  registered in the parity gate (`evals/parity/run.py`) and `test_graphgen.py` /
  `test_polyglot_fixtures.py`.
- PRD: `docs/prd/ruby-extractor.md`.

## Upgrade

```bash
pip install --upgrade neuralmind
```

No migration. Ruby files are picked up automatically on the next
`neuralmind build`.
