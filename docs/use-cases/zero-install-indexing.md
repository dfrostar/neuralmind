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

- **Languages:** Python, TypeScript, and Go out of the box (v0.16.0+) — a
  mixed-language repo is indexed in one pass. More grammars register behind the
  same `SUPPORTED_SUFFIXES` seam.
- **Edge precision:** `calls`/`inherits` are best-effort by name (no type
  resolution). Whether that costs retrieval quality is **measured** by the
  backend parity gate, not guessed — and an optional LSP/SCIP precision pass
  is on the roadmap.

---

## Want graphify's richer graph instead?

Install it and it takes priority automatically — no flag needed:

```bash
pip install neuralmind graphifyy
graphify update .
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
