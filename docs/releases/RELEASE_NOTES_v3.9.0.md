# NeuralMind v3.9.0 — SOTA Synapse Dynamics & Adversarial Retrieval

**Release Date:** September 2026

## TL;DR

Six modern brain-inspired learning techniques in the synapse layer, plus three adversarial fixes for shallow retrieval. The synapse layer now learns like a biological brain — not just "what files go together" but "what you actually need before you ask."

- **Synapse Dynamics (6 techniques):** Lateral inhibition, Synaptic Tagging & Capture (STC), non-monotonic plasticity (SAMPL), resource-dependent STDP, Feeling-of-Knowing (FOK) gating, replay-based consolidation
- **Retrieval Enhancements (3 fixes):** Intent-aware classification, code-signal boosting, synapse-seeded expansion, dependency graph traversal, code snippet extraction
- **Token reduction:** 32.6x (1,534 tokens vs 50K full codebase)
- **Test coverage:** 54 new tests, all passing

---

## Synapse Dynamics

The synapse layer now implements six modern computational neuroscience techniques:

### 1. Lateral Inhibition (SYNAPSE paper, arXiv 2025)
When one concept activates, it suppresses competing activations rather than only boosting neighbors. Prevents "attention dilution" in large codebases.

### 2. Synaptic Tagging & Capture (PNAS Nexus 2022)
Not every co-activation is meaningful. Two-phase model:
- **Tag:** Co-activation creates a temporary mark (short-term)
- **Capture:** If the same pair fires again within a consolidation window, tagged synapses become permanent
- **Decay:** Untagged marks fade without entering long-term memory

### 3. Non-Monotonic Plasticity (SAMPL model, bioRxiv)
Memory retrieval both *enhances* the retrieved item AND *weakens* related but non-retrieved items. Prevents "everything is vaguely associated with everything."

### 4. Resource-Dependent Heterosynaptic STDP (Frontiers 2025)
Each node has a finite local resource pool. Strengthening edge (A,B) consumes resources from A's pool, naturally weakening competing edges (A,C), (A,D). Creates synaptic competition without global normalization.

### 5. Feeling-of-Knowing (FOK) Gating (SYNAPSE paper)
Confidence gate on retrieval. If peak activation after spreading doesn't exceed an adaptive threshold, returns empty rather than weakly-associated noise. Prevents hallucination of irrelevant context.

### 6. Replay-Based Consolidation (bioRxiv 2025)
Replay queue captures recent co-activation sequences. During idle periods, replays them to strengthen associations without new input. Interleaves recent + old patterns to prevent catastrophic forgetting.

---

## Retrieval Enhancements

### Problem
For "how does X implement Y" queries, the system was surfacing docstrings instead of implementation code. Qwen 3.8 Flash adversarial QA identified this as the critical failure mode.

### Fix 1: Intent-Aware Classification
Queries matching "how does <X> implement/perform/do <Y>" are now classified as `code` intent, not `docs`. This ensures implementation queries surface code files.

### Fix 2: Code-Signal Boost
Extracts CamelCase, snake_case, and plain identifiers from queries. Boosts results from files whose source code contains those identifiers. Penalizes docs (0.3x multiplier) for code-intent queries.

### Fix 3: Synapse-Seeded Expansion
Checks if query terms match known synapse nodes. If so, spreads activation through the synapse graph to find co-implemented neighbors.

### Fix 4: Dependency Graph Traversal
For each identifier, finds its callers/callees/imports in the structural graph. Surfaces code that is structurally related even if not semantically similar.

### Fix 5: Code Snippet Extraction
For source file matches, extracts actual source code centered on the best-matching identifier (with line numbers) instead of generic document snippets.

> **Correction (v3.9.1): fixes 3–5 are off by default.**
>
> As first shipped, fixes 3–5 — the passes that pull in nodes vector search did
> not return — regressed the faithfulness gate and blocked this release. They
> appended up to eight nodes to a four-hit list and forced their scores to a
> hardcoded `4.5`, so injected nodes outranked every real hit and the genuine
> ones were pushed past the L3 token budget. On the reference fixture the
> faithfulness delta went `+0.041` → `-0.065`, under the gate's `+0.000` floor.
>
> They are now behind `NEURALMIND_RETRIEVAL_EXPANSION=1`, **off by default**,
> and budget-neutral when enabled. Making them budget-neutral did not rescue
> them — displaced, the delta was `-0.107`, worse than appending — because
> displacement evicts a real hit per candidate, so candidates worse than what
> they replace cost facts rather than only tokens. That is a candidate-quality
> problem, and it is unsolved.
>
> **Fixes 1 and 2 (intent classification, code-signal boost) are unaffected and
> stay on.** They re-rank the hits retrieval already returned rather than adding
> to them, and measure bit-for-bit neutral on the same fixture. The headline
> "how does X implement Y" behaviour is Fix 1, so it still ships.
>
> See `NEURALMIND_RETRIEVAL_EXPANSION` in the [CLI
> Reference](../wiki/CLI-Reference.md#environment-variables).

---

## API

```python
from neuralmind import NeuralMind

nm = NeuralMind('/path/to/project')

# Synapse dynamics
nm.dynamics_reinforce(['entity:id:1', 'entity:id:2'])  # STC + resource STDP + replay
related = nm.dynamics_spread([('entity:id:1', 1.0)])    # Lateral inhibition + FOK
stats = nm.dynamics_stats()                             # Introspection

# Enhanced retrieval (automatic)
result = nm.query('How does the synapse layer work?')
# Now surfaces implementation code, not just docstrings
```

---

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `NEURALMIND_SYNAPSE_INJECT` | `1` | Enable synapse recall at prompt time |
| `NEURALMIND_SYNAPSE_EXPORT` | `1` | Enable memory export to markdown |
| `NEURALMIND_BYPASS` | `0` | Skip compression (full codebase) |
| `NEURALMIND_INTENT_THRESHOLD` | `0.6` | Intent classification threshold |
| `NEURALMIND_CODE_BOOST` | `3.0` | Code intent boost multiplier |
| `NEURALMIND_DOC_BOOST` | `2.0` | Doc intent boost multiplier |
| `NEURALMIND_RETRIEVAL_EXPANSION` | `0` | *(v3.9.1+)* Opt-in the retrieval pull-in (fixes 3–5). Off by default — see the correction above |

---

## Benchmarks

| Metric | Value |
|--------|-------|
| Token reduction | 32.6x |
| Synapse pairs (self-indexed) | 6,561 |
| Nodes indexed | 4,949 |
| Clusters | 62 |
| New tests | 54 |
| Existing tests unaffected | 2,340/2,348 |

---

## Known Limitations

1. **`synapses.py` surfacing:** For "how does X work" queries, `synapses.py` still ranks below docstrings. The code-signal boost (10x cap) is insufficient to overcome the initial vector score gap. Two-pass retrieval with snippet extraction was the attempted fix and is the pass now disabled by default (see the correction above) — it surfaced the implementation by outranking everything, including the hits carrying the answer. The open problem is a pull-in whose candidates beat the hits they displace; substring matching over identifiers does not.

2. **No re-ranking model:** Cursor uses a fine-tuned 7B CodeLlama reranker. We use multiplicative score boosting. This is the single biggest quality gap.

3. **No dynamic context discovery:** Cursor v1.8.3+ writes large tool outputs to files and lets the agent read on demand (46.9% token reduction). We dump all retrieved context into the prompt at once.

4. **No independent benchmark:** Our 32.6x reduction is self-measured. No SWE-bench or Terminal-Bench score yet.

---

## Migration

No migration needed. Existing `synapses.db` files are compatible. New tables are created automatically on first use.

---

## Files Changed

- `neuralmind/synapse_dynamics.py` — NEW (920 lines, 6 techniques)
- `neuralmind/retrieval_enhancement.py` — NEW (600 lines, 5 fixes)
- `neuralmind/context_selector.py` — +70 lines (integration)
- `neuralmind/core.py` | `neuralmind/__init__.py` — +10 lines (exports)
- `tests/test_synapse_dynamics.py` — NEW (26 tests)
- `tests/test_retrieval_enhancement.py` — NEW (28 tests)
