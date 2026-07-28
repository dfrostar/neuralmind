# Release Notes — v1.7.2 (2026-07-27)

**Campaign:** DocEvolver Shipped  
**Tagline:** `neuralmind optimize-docs .` — evolutionary JSDoc that maximizes retrieval fitness, measured against your own index.

---

## What shipped

### DocEvolver — `neuralmind optimize-docs`

NeuralMind indexes markdown and JSDoc. Well-documented code is discoverable code. The DocEvolver closes the feedback loop: it finds methods that lack documentation (blind spots), generates JSDoc variants using four mutation strategies, and evolves them against a retrieval fitness function — the same Recall@1 metric `neuralmind probe` uses.

For each undocumented method, the evolver:

1. **Samples** — generates N JSDoc variants via four mutation strategies:
   `LENGTH` (1/3/5-line), `STRUCTURE` (Args/Returns vs prose-only vs mixed),
   `KEYWORD_DENSITY` (method-name synonyms vs generic description),
   `POSITION` (above vs inline for arrow functions).
2. **Evaluates** — patches each variant into the source, runs a
   natural-language query, and scores Recall@1 = 1/rank of the correct file.
3. **Promotes** — the best variant beats the incumbent by a hysteresis
   margin (0.05), then mutates around it for the next generation.
4. **Patches** — after G generations, the winning JSDoc is written back to
   the source file.

```bash
# Run full audit + evolution on a project
neuralmind optimize-docs .

# Dry-run (report only, no file changes)
neuralmind optimize-docs . --dry-run

# With pre-computed blind spots from probe
neuralmind probe . --json > spots.json
neuralmind optimize-docs . --blind-spots spots.json

# Custom evolution parameters
neuralmind optimize-docs . --population 10 --generations 8 --hysteresis 0.03
```

### Self-review JSDoc — 13 modules, 30 methods

A self-review pass applied DocEvolver principles to NeuralMind's own source.
Thirteen modules and thirty previously-undocumented methods now carry JSDoc,
improving discoverability for agents querying the NeuralMind codebase itself.

### synapses.py bugfix

Restored a missing `namespace` parameter in `synapses.py` that caused
`TypeError` on calls that omitted the optional namespace argument. The
signature now matches the documented API.

---

## Acceptance

| Criterion | Status |
|-----------|--------|
| `neuralmind optimize-docs . --dry-run` prints blind-spot report without modifying files | Pass |
| `neuralmind optimize-docs . --blind-spots spots.json` consumes probe JSON | Pass |
| `neuralmind optimize-docs . --population 5 --generations 3` evolves within bounds | Pass |
| `neuralmind optimize-docs . --json` emits structured JSON | Pass |
| 44/44 `test_doc_evolver.py` tests pass | Pass |
| `synapses.py` accepts calls without namespace arg | Pass |
| `pip install -e .` succeeds; `neuralmind --version` reports 1.7.2 | Pass |
| Ruff clean on `doc_evolver.py` | Pass |

---

## Missing (Phase 2, not blocking)

- Evolver-for-docs on 477 remaining undocumented symbols across the codebase
- `NEURALMIND_DOC_EVOLVER` env var to disable the optimize-docs command
- Wiki `DocEvolver-Guide.md` with fitness-function deep-dive
- Integration with `neuralmind probe` as a single-pass "find and fix" command

---

## Files changed

| File | Change |
|------|--------|
| `neuralmind/doc_evolver.py` | New module — evolutionary JSDoc optimizer (1181 lines) |
| `tests/test_doc_evolver.py` | 44 tests covering mutation, fitness, hysteresis, CLI |
| `neuralmind/cli.py` | `optimize-docs` subcommand wiring |
| `neuralmind/synapses.py` | Bugfix — restored missing `namespace` parameter |
| 13 modules | Self-review JSDoc on 30 methods |
| `.claude/settings.json` | Hooks installed |

---

## Marketing uses

- **LinkedIn About:** Add "DocEvolver — evolutionary JSDoc optimization" to differentiators
- **LinkedIn DMS:** 3-part sequence (undocumented code is invisible, fitness-driven doc optimization, measured retrieval lift)
- **README:** v1.7.2 section at top of release notes
- **Wiki:** v1.7.2 added to "What's New" + CLI Reference
- **Website Hero:** "DocEvolver — JSDoc that evolves for retrieval fitness" stat
- **Website Features:** "DocEvolver" card (v1.7.2 badge)
- **Website FAQ:** New entry explaining evolutionary documentation
- **Use case walkthrough:** `docs/use-cases/doc-evolver-optimize-docs.md`

---

*v1.7.2 — DocEvolver: evolutionary JSDoc for retrieval fitness. Documentation that proves itself against your own index.*
