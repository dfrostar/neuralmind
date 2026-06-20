# NeuralMind v0.35.0 — C# joins the bundled backend (eight languages)

**Release Date:** June 2026

## TL;DR

The bundled tree-sitter backend now indexes **C#** (`.cs`) — taking NeuralMind
to **eight languages** (Python, TypeScript, Go, Rust, Java, C, C++, C#) with **no
external tooling**. It passes the same structural-parity gate as Rust/Java/C/C++:
**52/52 symbols (100% structural coverage) vs the committed gold, zero dangling
edges**.

```bash
neuralmind build /path/to/your/csharp/project   # bundled — nothing extra to install
```

## Why this one matters

Language breadth is the one place breadth-first indexers genuinely lead — and the
only competitive gap that doesn't touch NeuralMind's moat (Hebbian synapses,
semantic vector retrieval, L0–L3 progressive disclosure are all unaffected by
language count). C# is the natural next pick: it maps almost 1:1 onto the proven
**Java** extractor (namespaces ≈ packages; class/interface/struct/record/enum →
type nodes; `base_list` → `inherits`; `using` → `imports_from`), so it rides a
proven shape at the smallest risk — one language per PR, each clearing the parity
gate in isolation with its own docs/SEO pass.

## What it indexes

- **Types** — `class`, `interface`, `struct`, `record`, and `enum` declarations
  become type nodes (nested types recurse, contained by the outer type).
- **Members** — `method`/`constructor` declarations become function nodes;
  `field`/`property` declarations and `enum` members become symbol nodes; a
  positional `record`'s parameters become symbol nodes too.
- **`using` → `imports_from` edges.** A `using` directive's namespace resolves
  against a namespace / type-name module table; edges are emitted **only to
  existing file ids**, so they're dangling-free by construction.
- **Inheritance** — `base_list` entries (`identifier` / `qualified_name` /
  `generic_name`) produce `inherits` edges, resolved against the type table;
  external bases are synthesized so the edge never dangles (mirrors Java/TS).
- **`///` doc comments → the `rationale` layer.** XML doc comments attach to the
  symbol they document, exactly like Javadoc / Rust `///`.
- **Calls** — bare-name best-effort, same heuristic as the other languages; the
  opt-in **SCIP precision pass** remains the path to compiler-accurate edges.

## Honestly out of scope (disclosed, not hidden)

So you know exactly what you're getting:

- **Compiler-accurate call/inherit resolution isn't done** — the bare-name
  `calls` resolver stays best-effort (SCIP precision pass remains the exact path).
- **Generics / partial-class merging and `using` aliases aren't resolved** — a
  generic type is emitted as one symbol; partial declarations aren't merged.
- **Top-level statements aren't synthesized** — `Program.cs`-style implicit
  `Main` (rare in libraries) isn't recovered.

These are deliberate MVP boundaries, tracked as follow-ups. The structural-parity
gate proves the in-scope coverage is real, not aspirational.

## Per-agent expectations

| Agent | What changes in v0.35.0 |
|-------|--------------------------|
| **All** | `neuralmind build` now indexes C# projects out of the box; retrieval, progressive disclosure, and the synapse layer work identically to the other seven languages. |
| **Claude Code / Cursor / Cline / generic MCP** | No config change — drop NeuralMind on a C# repo and query it. `.cs` files are picked up automatically. |

## What ships

- **`neuralmind/graphgen.py`** — a `csharp` extractor behind the existing
  `_SUFFIX_LANG` → `_EXTRACTORS` seam (a pass-1/pass-2 pair following the Java
  shape), with `.cs` registered in `SUPPORTED_SUFFIXES`.
- **`tree-sitter-c-sharp`** added to the runtime deps so the grammar is bundled.
- Fixture `tests/fixtures/sample_project_csharp` + a committed gold graph,
  registered in the parity gate (`evals/parity/run.py`) and `test_graphgen.py` /
  `test_polyglot_fixtures.py`.
- PRD: `docs/prd/csharp-extractor.md`.

## Upgrade

```bash
pip install --upgrade neuralmind
```

No migration. C# files are picked up automatically on the next
`neuralmind build`.
