# NeuralMind v0.37.0 — ten languages, a bigger benchmark, richer SEO

**Release Date:** June 2026

## What's in this release

v0.37.0 lands the full **language-breadth tier** plus benchmark and discovery
work in one release. The bundled tree-sitter backend goes from seven to **ten
languages** — adding **C#, Ruby, and PHP**, each proven at the same
structural-parity gate (100% symbol coverage vs a committed gold, zero dangling
edges):

| Change | What | Evidence |
|---|---|---|
| **C# extractor** | eighth language (`.cs`) | 52/52 symbols (100%), 0 dangling — see [`RELEASE_NOTES_v0.35.0.md`](RELEASE_NOTES_v0.35.0.md) |
| **Ruby extractor** | ninth language (`.rb`) | 46/46 symbols (100%), 0 dangling — see [`RELEASE_NOTES_v0.36.0.md`](RELEASE_NOTES_v0.36.0.md) |
| **PHP extractor** | tenth language (`.php`) | 54/54 symbols (100%), 0 dangling — detailed below |
| **Benchmark corpus** | the honest public benchmark expands `requests`/`click` → **+ `flask` + `rich`** (4 repos, 40 pre-registered def-site queries) | `evals/public/manifest.json`, `docs/benchmarks/public.md` |
| **SEO** | richer schema.org JSON-LD (`SoftwareApplication` + `WebSite`, `TechArticle`) on the docs pages | `docs/index.html`, `docs/about.html` |

The bundled backend now indexes **Python, TypeScript, Go, Rust, Java, C, C++,
C#, Ruby, PHP** out of the box, completing the C#/Ruby/PHP breadth tier. The rest
of this note details the PHP extractor (the headline tenth language); the C# and
Ruby deep-dives are in their per-language notes linked above.

---

## TL;DR — PHP, the tenth language

The bundled tree-sitter backend now indexes **PHP** (`.php`) — taking NeuralMind
to **ten languages** (Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby, PHP)
with **no external tooling**. It passes the same structural-parity gate as
Rust/Java/C/C++/C#/Ruby: **54/54 symbols (100% structural coverage) vs the
committed gold, zero dangling edges**.

```bash
neuralmind build /path/to/your/php/project   # bundled — nothing extra to install
```

## Why this one matters

Language breadth is the one place breadth-first indexers genuinely lead — and the
only competitive gap that doesn't touch NeuralMind's moat (Hebbian synapses,
semantic vector retrieval, L0–L3 progressive disclosure are all unaffected by
language count). PHP is the **third and final pick of the breadth tier (C# /
Ruby / PHP)** — so this release **completes that tier**. PHP maps almost 1:1 onto
the proven **Java** extractor plus a namespace layer (`class`/`interface`/`trait`/
`enum` → type nodes; `extends`/`implements` → `inherits`; `use` → `imports_from`,
resolved by class name exactly like Java imports), so it rides a proven shape at
the smallest risk — one language per PR, each clearing the parity gate in
isolation with its own docs/SEO pass.

## What it indexes

- **Types** — `class`, `interface`, `trait`, and `enum` declarations become type
  nodes (nested types recurse, contained by the outer type).
- **Methods** — `method` declarations and top-level `function` definitions become
  function nodes.
- **Properties, constants, enum cases** — `property` declarations (the leading
  `$` is **stripped from the label**), class `const` declarations, and `enum`
  cases become symbol nodes.
- **`use` → `imports_from` edges.** A `use` declaration's namespace import
  resolves against a class-name / FQN module table (the imported
  `Acme\Db\Connection` matches the file that declares it) — **exactly like Java
  imports** — and edges are emitted **only to existing file ids**, so they're
  dangling-free by construction.
- **Inheritance** — `extends` and `implements` (`base_clause` /
  `class_interface_clause`) produce `inherits` edges, resolved against the type
  table; external bases are synthesized so the edge never dangles (mirrors
  Java/TS).
- **`/** */` doc comments → the `rationale` layer.** PHPDoc block comments attach
  to the symbol they document (markers stripped), exactly like Javadoc / Rust
  `///`.
- **Calls** — `Class::method` (`scoped_call_expression`), `$obj->method`
  (`member_call_expression`), and bare calls (`function_call_expression`) are
  matched by method name, best-effort, same heuristic as the other languages; the
  opt-in **SCIP precision pass** remains the path to compiler-accurate edges.

## Honestly out of scope (disclosed, not hidden)

So you know exactly what you're getting:

- **Compiler-accurate call resolution isn't done** — `calls` stays bare-name
  best-effort; the `$obj->method` **receiver type isn't resolved**, so dynamic
  dispatch isn't pinned to a concrete class. The SCIP precision pass remains the
  exact path to compiler-accurate edges.
- **`require`/`include` path imports aren't modelled** — `use` (the namespace
  import, resolved by class name like Java) is the **only** `imports_from` edge
  source; a `require`/`include` of a path is not modelled.
- **Trait-`use`-inside-a-class-body isn't modelled as inheritance** — only
  `extends`/`implements` (`base_clause` / `class_interface_clause`) emit
  `inherits` edges; a `use TraitName;` in a class body, dynamic `$$var` access,
  and variadic/heredoc edge cases are out.

These are deliberate MVP boundaries, tracked as follow-ups. The structural-parity
gate proves the in-scope coverage is real, not aspirational.

## Per-agent expectations

| Agent | What changes in v0.37.0 |
|-------|--------------------------|
| **All** | `neuralmind build` now indexes PHP projects out of the box; retrieval, progressive disclosure, and the synapse layer work identically to the other nine languages. |
| **Claude Code / Cursor / Cline / generic MCP** | No config change — drop NeuralMind on a PHP repo and query it. `.php` files are picked up automatically. |

## What ships

- **`neuralmind/graphgen.py`** — a `php` extractor behind the existing
  `_SUFFIX_LANG` → `_EXTRACTORS` seam (a pass-1/pass-2 pair following the Java/C#
  shape), with `.php` registered in `SUPPORTED_SUFFIXES`.
- **`tree-sitter-php`** added to the runtime deps so the grammar is bundled.
- Fixture `tests/fixtures/sample_project_php` + a committed gold graph,
  registered in the parity gate (`evals/parity/run.py`) and `test_graphgen.py` /
  `test_polyglot_fixtures.py`.
- PRD: `docs/prd/php-extractor.md`.

## Upgrade

```bash
pip install --upgrade neuralmind
```

No migration. PHP files are picked up automatically on the next
`neuralmind build`.
