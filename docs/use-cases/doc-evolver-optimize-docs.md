# How to optimize JSDoc for retrieval fitness

**Use case:** Evolutionary documentation — let the index tell you which JSDoc works.

---

## The problem

Undocumented code is invisible to retrieval. An agent searching for
"handle csv export" comes up empty when the method has no JSDoc — the
embedding text is just the method name, which ranks low against natural
language. The method exists, it works, but no agent can find it by
description.

Traditional fix: write JSDoc by hand, hope it helps. But there's no
feedback loop — you don't know whether your JSDoc actually improves
retrieval until an agent fails to find the method.

## The solution

`neuralmind optimize-docs` closes the loop. It finds undocumented
methods, generates JSDoc variants using mutation strategies, builds the
index, queries retrieval fitness, promotes the best variant, and repeats
for G generations. The winning JSDoc is the one that maximizes
Recall@1 — the same metric `neuralmind probe` uses.

## Existing use case: better JSDoc

You have a codebase with spotty documentation. Some methods have
JSDoc, some don't. You want to improve discoverability without
hand-writing hundreds of docstrings.

```bash
# Step 1: Find the blind spots
neuralmind probe . --json > spots.json

# Step 2: See what would change (dry-run)
neuralmind optimize-docs . --dry-run

# Step 3: Evolve JSDoc for the worst offenders
neuralmind optimize-docs . --blind-spots spots.json --generations 5

# Step 4: Verify improvement
neuralmind probe . --json > spots-after.json
```

## Potential new use case: data-driven doc optimization

You're building a documentation quality gate for CI. Instead of
linting for JSDoc presence (which says nothing about quality), you
measure whether each method's JSDoc actually retrieves the method
from a natural-language query. Methods that fail get flagged for
evolution.

```bash
# CI gate: fail if any method's JSDoc doesn't retrieve it
neuralmind optimize-docs . --dry-run --json | \
  jq '.blind_spots | length' | \
  xargs -I{} test {} -eq 0
```

## How it works

### Mutation strategies

The evolver generates variants using four strategies:

| Strategy | Variants |
|----------|----------|
| `LENGTH` | 1-line, 3-line, 5-line JSDoc |
| `STRUCTURE` | Args/Returns style, prose-only, mixed |
| `KEYWORD_DENSITY` | Method-name synonyms, generic description |
| `POSITION` | Above the function, inline (arrow functions) |

### Fitness function

```
fitness(variant) = 1 / rank_of_correct_file(query="humanized method name")
```

Score: 1.0 (rank #1), 0.5 (rank #2), 0.33 (rank #3), 0.0 (not found).

### Evolution loop

```
Generation 0:  ***** (random variants, fitness ~0.3-0.5)
Generation 1:  ****O (one promoted, fitness ~0.6)
Generation 2:  ***OO (mutations around the winner, fitness ~0.7)
...
Generation N:  OOOOO (converged, fitness ≥ 0.7)
```

### Hysteresis

A variant only promotes if it beats the incumbent by at least the
hysteresis margin (default 0.05). This prevents thrashing when two
variants score similarly.

## Cross-references

- **Source:** [`neuralmind/doc_evolver.py`](../../neuralmind/doc_evolver.py) — main module (1181 lines)
- **Tests:** [`tests/test_doc_evolver.py`](../../tests/test_doc_evolver.py) — 44 tests
- **CLI Reference:** [`docs/wiki/CLI-Reference.md`](../../docs/wiki/CLI-Reference.md#optimize-docs-v172)
- **Architecture:** [`docs/wiki/Architecture.md`](../../docs/wiki/Architecture.html#doc-evolver-v0530)
- **Release notes:** [`RELEASE_NOTES_v1.7.2.md`](../../RELEASE_NOTES_v1.7.2.md)

## What the agent actually sees

After running `neuralmind optimize-docs .`, the agent sees:

1. **Before:** Query "handle csv export" → no results (method undocumented)
2. **After:** Query "handle csv export" → `handle_csv_export()` surfaces at rank #1

The JSDoc that won is the one that made the method discoverable — not
the one that looks best to a human, the one that works for retrieval.

## Honest scope

- **Language:** Currently targets JavaScript/TS (JSDoc). Python docstrings planned for Phase 2.
- **Fitness is local:** The evolver optimizes per-method, not for global index coherence.
- **Dry-run first:** Always run `--dry-run` before committing to file changes.
- **Not a style guide:** The evolver doesn't enforce conventions — it optimizes for retrieval fitness. A 1-line JSDoc that retrieves beats a 10-line JSDoc that doesn't.
