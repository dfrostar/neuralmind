# Index any repo with just `pip` (no graphify)

**Best for:** anyone trying NeuralMind for the first time, CI jobs, and
fresh/locked-down machines where installing a second indexing tool is
friction or impossible.

**Primary goal:** go from nothing to a queryable index in one `pip install`
and one `build` — no external graph tool.

Before **v0.15.0** you had to install and run a separate tool (`graphify`)
before `neuralmind build` would do anything. That extra step was the #1
onboarding drop-off. NeuralMind now ships a **built-in tree-sitter graph
backend**, so the whole flow is two commands.

---

## The 30-second path

```bash
pip install neuralmind
cd /path/to/your-repo
neuralmind build .
```

On the first `build` with no `graphify-out/graph.json` present, NeuralMind
parses your code with the bundled tree-sitter backend and prints:

```
[neuralmind] generated code graph via the built-in tree-sitter backend → graphify-out/graph.json
```

Then query it like normal:

```bash
neuralmind query "how does authentication work?" .
neuralmind wakeup .          # ~400-token project orientation
```

That's it. No second install, no separate graph step.

---

## What you get (and what you don't)

The built-in backend produces a **graphify-compatible** graph — symbol-level
`code` nodes (files, classes, functions/methods), `contains` / `imports_from`
/ `inherits` / `calls` edges, and a docstring-derived `rationale` layer. The
entire retrieval pipeline downstream — progressive L0–L3 disclosure, the
synapse layer, the graph view, the MCP tools — works exactly the same. Only
the graph *producer* changed.

- **Languages:** Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby, and PHP out of
  the box (Rust added in v0.27.0, Java in v0.28.0, C/C++ in v0.32.0, C# in
  v0.35.0, Ruby in v0.36.0, PHP in v0.37.0)
  — a mixed-language repo is indexed in one pass. Rust structs, enums, traits,
  `impl` blocks, and `use`/`impl Trait` edges all map onto the same graph model;
  C/C++ functions, `struct`/`union`/`enum`s, C++ classes and namespace-qualified
  ids, local `#include "x.h"` → `imports_from` edges, inheritance, and
  header/impl pairing do too (macros, templates, and `#ifdef` are scoped out and
  disclosed — we index the parseable code at structural parity); C#
  classes/interfaces/structs/records/enums, methods/constructors, fields,
  properties and enum members, `base_list` → `inherits`, `using` →
  `imports_from`, and `///` doc comments → `rationale` map on the same way
  (`.cs` files are indexed zero-install — no .NET SDK or graphify needed); and
  Ruby `class`/`module` types, `def`/`def self.` methods, constant assignments
  (the symbol layer), `class Foo < Bar` → `inherits`, `require_relative` →
  `imports_from` (relative-path resolved), and `#` doc comments → `rationale`
  map the same way (`.rb` files are indexed zero-install — no Ruby toolchain or
  graphify needed; Ruby is dynamic, so calls are best-effort and mixins
  via `include`/`extend` aren't modelled as inheritance, disclosed honestly);
  and PHP `class`/`interface`/`trait`/`enum` types, methods/top-level functions,
  properties (the `$` stripped from the label)/class constants/enum cases (the
  symbol layer), `extends`/`implements` → `inherits`, `use` namespace imports →
  `imports_from` (resolved by class name, exactly like Java imports), and
  `/** */` doc comments → `rationale` map the same way (`.php` files are indexed
  zero-install — no PHP runtime or graphify needed; calls are best-effort with no
  `$obj->method` receiver-type resolution, and `require`/`include` path imports
  aren't modelled — `use` is the edge source — disclosed honestly).
  More grammars register behind the same `SUPPORTED_SUFFIXES` seam.
- **Edge precision:** `calls`/`inherits` are best-effort by name (no type
  resolution). Whether that costs retrieval quality is **measured** by the
  backend parity gate, not guessed — and an optional LSP/SCIP precision pass
  is on the roadmap.

---

## Want graphify's richer graph instead?

Install it and it takes priority automatically — no flag needed:

```bash
pip install neuralmind
neuralmind build .
```

Precedence rules:

- A real graphify graph **always wins** where present.
- `neuralmind build --force` only regenerates graphs *we* wrote — it never
  clobbers a graphify build.
- An empty / non-code project writes no graph, so you get honest "no graph"
  guidance instead of a silent 0-node "success".

You can switch either direction later without losing your `.neuralmind/`
state — it's on disk in the project, not in the install.

---

## Why trust the built-in backend?

Because the swap is **proven at parity, not asserted.** Every NeuralMind PR
runs a backend parity gate (`evals/parity/run.py`) that builds the reference
fixture with *both* graphify and the built-in backend, runs the faithfulness
eval and derives the token-reduction ratio on each, and fails the build if
the built-in backend drifts outside tolerance of graphify (within 25%
reduction, within 10 points faithfulness). If a backend change ever made
retrieval meaningfully worse, CI catches it before it ships.

Measure it on your own code in the same breath:

```bash
neuralmind benchmark .          # your actual reduction ratio + per-query tokens
```

---

## Related

- [Does it work on your code? (5-minute benchmark)](./benchmark-your-repo.md)
- [Install NeuralMind anywhere](./install-paths.md) — pip / pipx / uv / Docker / source
- [Claude Code user](./claude-code.md) — full two-phase optimization
- [CLI Reference → `build`](../wiki/CLI-Reference.md) — backend precedence + options
