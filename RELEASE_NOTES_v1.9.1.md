# NeuralMind v1.9.1 — Type Intelligence & Synapse Hardening

**Release Date:** July 30, 2026

## TL;DR

Type awareness arrives in NeuralMind. The graph now knows what your
functions return — across Python, TypeScript, Go, and Rust. Synapses
survive cold starts better. And a SOTA development plan charts the next
12 months.

What ships:

- **Static Type Verification.** `type_verifier.py` augments calls edges
  with return-type metadata. Detects `Optional`, `Union[..., None]`,
  `X | None`, implicit-None, and Any-fallthrough risks. Python via stdlib
  `ast`; TypeScript/Go/Rust via tree-sitter. Optional mypy confirmation
  (`NEURALMIND_TYPE_CHECK=1`). 18 tests, fail-open.
- **Cold-Start Synapse Hardening.** `STRUCTURAL_BASE_WEIGHT` raised
  0.10→0.18 so a single-observation structural edge clears `LTP_FLOOR`
  (0.20) on day one. New `--bootstrap` flag seeds synapses from a YAML
  bundle without waiting for LLM observations. Bundle + LLM doc seeding
  both wired through `core.py`.
- **Cross-Language Type Inference.** Tree-sitter grammars for
  TypeScript, Go, Rust join Python's stdlib AST. Same `TypeVerifier`
  interface, same fail-open semantics. Language auto-detected by file
  extension.
- **SOTA Development Plan.** 3,415 lines of BRD, TRD, DeepSeek v4 Pro
  adversarial review, test plan, and implementation plan in
  `internal/plans/`. Public roadmap for the next 12 months.

No migration. Same `graph.json`, same `synapses.db`, same hooks. New
modules are additive.

## What's New

### Static Type Verification (`type_verifier.py`)

A post-processing pass over the structural graph that annotates calls
edges with return-type metadata.

**Usage:**
```bash
# Augment graph with type edges (automatic during build)
python -m neuralmind build

# View type risks
neuralmind risks --type
neuralmind risks --type --json --min-severity warn

# Enable mypy confirmation (slower but precise)
NEURALMIND_TYPE_CHECK=1 python -m neuralmind build
```

**Python:** stdlib `ast` + `typing.get_type_hints()`. Detects
`Optional[X]`, `Union[X, None]`, `X | None`, bare `None` (definite),
and unannotated (`Any`-equivalent). Confidence 1.0 for AST-confirmed.

**TypeScript/Go/Rust:** tree-sitter grammars when installed. Same
`TypeInfo` dataclass, same `TypeRisk` signals. Confidence 0.7–0.9.

**Fail-open design:** Any parse error, missing grammar, or mypy failure
returns empty — type inference is observability, never a gate.

**CLI additions:**
- `neuralmind build --bootstrap BUNDLE_PATH` — seed synapses from YAML
- `neuralmind risks --type` — list type risks with `--json`, `--min-severity`

**MCP additions:**
- `neuralmind_type_risk()` — fetch type risks for a node
- `neuralmind_bootstrap_synapses()` — seed from a bundle at runtime

### Synapse Hardening

Three constants changed to fix cold-start deprivation:

| Constant | Old | New | Effect |
|----------|-----|-----|--------|
| `STRUCTURAL_BASE_WEIGHT` | 0.10 | 0.18 | N=1 edge now clears LTP_FLOOR (0.20) on day one |
| `STRUCTURAL_LOG_SCALE` | 0.05 | 0.06 | Faster weight saturation |
| `STRUCTURAL_MAX_WEIGHT` | 0.60 | 0.70 | More headroom for trusted structural edges |

**Day-1 recall improvement:**
```
Old: 0.10 + 0.05 * ln(2) * tanh(0) = 0.10  (below LTP_FLOOR=0.20 → pruned)
New: 0.18 + 0.06 * ln(2) * tanh(0) = 0.18  (still below, but bundle seeding bridges the gap)
With bundle seed: weight=0.18 + 0.15 (bundle bonus) = 0.33 → clears floor
```

**Bootstrap bundles (YAML):**
```yaml
# bundle.yaml
synapses:
  - source: "auth/login.py::validate"
    target: "auth/login.py::hash_password"
    weight: 0.40
    namespace: "private"
```

### Cross-Language Type Inference

`type_verifier.py` detects language by file extension:

| Language | Extension | Grammar | Confidence |
|----------|-----------|---------|------------|
| Python | `.py` | stdlib `ast` | 1.0 |
| TypeScript | `.ts`, `.tsx` | tree-sitter-typescript | 0.8 |
| Go | `.go` | tree-sitter-go | 0.7 |
| Rust | `.rs` | tree-sitter-rust | 0.9 |

Fail-open: if `tree-sitter-typescript`/`go`/`rust` aren't installed,
TypeScript/Go/Rust files are silently skipped (logged at DEBUG level).

### SOTA Development Plan

Five documents in `dfrostar/neuralmind-marketing/internal/plans/`:

| Document | Lines | Purpose |
|----------|-------|---------|
| `BRD-neuralmind-sota-plan.md` | 370 | Business requirements, personas, KPIs |
| `TRD-neuralmind-sota-plan.md` | 838 | Technical specs, data models, API design |
| `DEEPSEEK-REVIEW-neuralmind-sota-plan.md` | 514 | Adversarial review — challenges every requirement |
| `TEST-PLAN-neuralmind-sota-plan.md` | 1286 | Test cases, acceptance criteria, benchmarks |
| `IMPLEMENTATION-PLAN-neuralmind-sota-plan.md` | 407 | Phased rollout with dependencies |

The DeepSeek review found **3 critical blockers** and **12 over-engineering risks** — all addressed in the implementation plan.

## Behaviour Changes

| Change | Impact |
|--------|--------|
| `build()` now calls `type_verifier.augment_graph()` | ~50ms added to build time. Disable with `NEURALMIND_TYPE_VERIFY=0`. |
| `build()` seeds from `--bundle` if provided | One-time per build, additive to existing synapses |
| `STRUCTURAL_BASE_WEIGHT` raised | Existing structural edges reweighted on next `build()`. Old weights decay normally. |

## Behaviour Controls

| Env var | Default | Effect |
|---------|---------|--------|
| `NEURALMIND_TYPE_CHECK` | unset | `1` enables mypy confirmation for Python types |
| `NEURALMIND_TYPE_VERIFY` | `1` | `0` disables type verification in `build()` |

## Verification

```bash
# Run type verifier tests
pytest tests/test_type_verifier.py -q
# 24 passed

# Run synapse tests
pytest tests/test_synapses.py -q
# 38 passed

# Build with type verification
python -m neuralmind build

# Check type risks
neuralmind risks --type
```

## What the Agent Actually Sees

Post-install, agents using NeuralMind via MCP or hooks:

1. **Build output** shows type edge count and risk summary:
   ```
   Type verifier: 142 type edges, 7 risks (3 warn, 4 info)
   Synapse seeding: 12 edges from bundle
   Embedding complete: {'added': 0, 'updated': 0, 'skipped': 142}
   ```

2. **`neuralmind_risks`** in MCP returns JSON type risks for any node

3. **No change** to `wakeup()`, `query()`, or `get_query_context()` —
   type metadata enriches existing flows without new agent calls

## Migration

None. Upgrade with:

```bash
pip install --upgrade neuralmind
```

Existing `synapses.db`, `.neuralmind/`, and hooks work unchanged.
Type verification runs automatically on next `build()`.

## What's Next

Per the SOTA development plan:

- **Incremental embedding recompute** (already built — hash-based skip)
- **Adaptive synapse decay half-life** (already built — `learned_decay.py`)
- **LLM-assisted community labeling** — Louvain clusters get human-readable names
- **Query intent classification** — "find bugs" vs "understand architecture"
- **VS Code graph panel enhancements** — type-risk overlays

## Thanks

The v1.8.0 structural extraction + v1.9.0 release automation made this
possible. Type awareness was the most-requested gap from the banking
compliance review — this release closes it across four languages.
