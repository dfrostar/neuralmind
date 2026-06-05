# NeuralMind v0.16.0 — multi-language: TypeScript + Go (no graphify)

**Release Date:** June 2026

## TL;DR

v0.15.0 made `neuralmind build .` work with no external graphify install — for
**Python**. v0.16.0 takes the built-in tree-sitter backend **multi-language**:

```bash
pip install neuralmind
neuralmind build .        # now indexes Python, TypeScript, and Go — bundled
```

TypeScript (`.ts`/`.tsx`) and Go (`.go`) extractors are registered behind the
same `SUPPORTED_SUFFIXES` seam, emitting the same graphify-compatible
`graph.json` the whole retrieval stack already consumes. Nothing downstream
changed — only the set of languages the *producer* understands.

And, as always, it's **proven at parity, not asserted**: the backend parity
gate now checks TypeScript and Go too.

## What the agent actually sees, post-install

On a TypeScript or Go repo with no `graphify-out/graph.json`, `neuralmind
build` now **succeeds on its own** and prints:

```
[neuralmind] generated code graph via the built-in tree-sitter backend → graphify-out/graph.json
```

The agent then gets the same L0–L3 progressive disclosure, synapse layer, graph
view, and MCP tools — now over a TS or Go codebase. A mixed-language repo
(Python + TS + Go) is indexed in one pass: each file is dispatched to its
language's extractor and merged into a single graph.

### Per-agent expectations

| Agent | What changes in v0.16.0 |
|-------|--------------------------|
| **Claude Code** | `neuralmind build` indexes TS/Go repos with no graphify; hooks/memory/predictions unchanged at runtime. |
| **Cursor / Cline** | Same MCP tools; first index now works on TypeScript and Go projects standalone. |
| **Generic MCP client** | `neuralmind_build` succeeds on TS/Go repos; no new tool, no contract change. |
| **Contributors / CI** | The parity gate now proves TS + Go structural parity per language. |

## How the language seam works

`neuralmind/graphgen.py` dispatches each file by suffix to a per-language
extractor (`_SUFFIX_LANG` → `_EXTRACTORS`). Each extractor maps its grammar's
node types onto the **same** node/edge model:

| | Python | TypeScript | Go |
|---|---|---|---|
| functions | `function_definition` | `function_declaration` | `function_declaration` |
| methods | class body `function_definition` | `method_definition` | `method_declaration` |
| types | `class_definition` | `class`/`interface_declaration` | `type_declaration` (struct/interface) |
| symbols | module/class assignments | `const`/`let` declarators | `const`/`var` + struct fields |
| imports | `import` / `from … import` | relative `import … from "…"` | `import` (by package dir) |
| inherits | `class Foo(Base)` | `extends` / `implements` | — (Go has no inheritance) |
| rationale | docstring (summary + body) | leading `/** … */` JSDoc | leading `// …` doc comment |

Every language emits the same `code` / `rationale` / `document` nodes and
`contains` / `imports_from` / `inherits` / `calls` / `rationale_for` edges, plus
the same balanced per-file communities. Adding the next grammar is registering
a pair of functions — no change to anything downstream of `graph.json`.

`tree-sitter-typescript` and `tree-sitter-go` are now **core dependencies**, so
the languages are bundled. A grammar that somehow isn't importable is skipped
per-file (Python stays the only hard requirement), so a build never fails for a
missing optional grammar.

## The parity gate, now per language

For Python the gate runs the full **faithfulness A/B + reduction** (a gold-fact
set exists). TypeScript and Go have no gold-fact set yet, so the gate proves
parity **structurally**: the built-in backend must recover at least **90%** of
the symbols graphify's committed graph found, with a valid, dangling-free
graph. On the reference fixtures it recovers **100%** of graphify's symbols for
both:

| Language | graphify symbols | built-in covers | dangling |
|---|---:|---:|---:|
| TypeScript | 54 | 54 (100%) | 0 |
| Go | 45 | 45 (100%) | 0 |

The floor is overridable via `NEURALMIND_PARITY_COVERAGE_FLOOR`.

## Honest scope & caveats

- **Structural parity for TS/Go.** Without a per-language gold-fact set, the gate
  proves the built-in *finds the same symbols* graphify does — not (yet) a
  faithfulness A/B. Per-language gold sets are a future increment.
- **Heuristic call/inherit edges**, as in Python — best-effort by name, no
  type/scope resolution. The optional LSP/SCIP precision pass (next on the
  roadmap) is where exact edges land.
- **graphify still takes priority** where present, in every language.

## What ships

- **`neuralmind/graphgen.py`** — refactored into a per-language seam
  (`_SUFFIX_LANG` / `_EXTRACTORS`) with **TypeScript** and **Go** extractors
  alongside Python (comment-based rationale, struct fields, package imports).
- **`evals/parity/run.py`** — multi-language structural-coverage parity check
  (TS + Go) wired into the CI gate, with `NEURALMIND_PARITY_COVERAGE_FLOOR`.
- `tree-sitter-typescript` + `tree-sitter-go` added as core dependencies.
- Tests: TS + Go graph extraction + the language seam (35 graphgen tests);
  language-coverage gate logic (13 parity-gate tests).

## What's next

- **Optional precision pass** — LSP/SCIP-backed exact `calls`/`inherits`,
  off by default, behind the same `graph.json` seam.
- **Incremental updates** — per-file re-parse wired to the watcher.
- **Lean into the moat** — MCP auto-detection + the learned-synapse uplift eval.

## Upgrade

```bash
pip install --upgrade neuralmind
```

No migration, no config changes. Existing Python and graphify setups are
unchanged. On a fresh TS or Go repo you can now skip graphify entirely:

```bash
pip install neuralmind
neuralmind build /path/to/your/ts-or-go-repo
neuralmind query "how does authentication work?" /path/to/your/ts-or-go-repo
```
