# Use Case: Unified Context Engineering Stack (NeuralMind + Ponytail + Headroom)

## What you're solving for

You've hit the ceiling on single-tool token optimization. NeuralMind alone reduces retrieval
cost; Ponytail alone steers generation; Headroom alone compresses transport. But token waste
occurs at **every stage** — retrieval, transport, and generation — and a single tool only
addresses one of them. This walkthrough deploys all three as a coordinated pipeline.

## The three-stage model

| Stage | Tool | What it eliminates |
|---|---|---|
| Retrieval | NeuralMind | Irrelevant code flooding the context window |
| Transport | Headroom | Oversized tool results and unstable KV caches |
| Generation | Ponytail | Unnecessary custom code when native alternatives exist |

These are not competing tools. They intervene at different points and compose cleanly.

## Step 1 — Install NeuralMind (retrieval layer)

```bash
pip install neuralmind
neuralmind build .
neuralmind install-hooks .     # Claude Code users: PostToolUse compression + wakeup memory
neuralmind install-mcp --all   # registers with Claude Code / Cursor / Cline / Claude Desktop
```

Verify the index and hooks are working:

```bash
neuralmind doctor
neuralmind benchmark . --json  # should show ≥4× reduction on your repo
```

At this point your agent boots with `SYNAPSE_MEMORY.md` already in context, retrieves
~800 tokens of structured code context per query instead of whole files, and PostToolUse
hooks compress Read/Bash/Grep output before the model reads it.

## Step 2 — Install Headroom (transport layer)

Headroom is a local proxy that sits between your agent and the LLM endpoint. Install it
from [chopratejas/headroom](https://github.com/chopratejas/headroom) and point your agent
at the local proxy port instead of the provider directly.

What it handles that NeuralMind doesn't:

- KV cache prefix alignment — stabilizes the static prompt prefix so provider-side caches
  don't bust on dynamic metadata injected mid-payload.
- JSON/HTML payload compression — tool results that are structured data (API responses,
  build logs) shrink 70–95% before they reach the model.
- CCR reversibility — original payloads are cached locally in SQLite; the model can
  retrieve the full version via `headroom_retrieve` if it needs it.

NeuralMind's PostToolUse hooks and Headroom complement each other: hooks compress
*before* the agent's context is assembled; Headroom compresses the *assembled payload*
in transit. Both run; neither interferes with the other. As of **v0.41.0**, NeuralMind
also emits a **structured relevance sidecar** Headroom can read so it doesn't compress
away the exact spans that were the reason for retrieval — see
[Step 3.5](#step-35--close-the-seams-shared-relevance--reuse-feedback-v0410) below.

## Step 3 — Install Ponytail (generation layer)

Ponytail is a prompt-level behavioral steer that forces the model to exhaust native
options before writing custom logic. Install it from
[DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) and configure
the intensity profile in your agent's system prompt or MCP config.

Recommended profile by project phase:

| Phase | Profile | Why |
|---|---|---|
| Greenfield / MVP | `Full` (default) | Enforce native-first; skip custom boilerplate |
| Active feature dev | `Full` | Keeps the codebase lean while iterating fast |
| Production stabilization | `Lite` | Surfaces alternatives without blocking delivery |
| Architectural review | `Ultra` | Challenges necessity before any new abstraction lands |

On advanced reasoning models (GPT-5.5, o3, Claude Fable 5 extended thinking), prefer
`Full` over `Ultra`. The deliberation cost of `Ultra`'s YAGNI challenges can exceed the
output savings on models that use internal thinking tokens to evaluate the ladder.

## Step 3.5 — close the seams: shared relevance + reuse feedback *(v0.41.0+)*

The common objection to a *modular* stack is that the layers can't see each other:
Headroom compresses a span without knowing **why** NeuralMind fetched it (so it can
shrink away the load-bearing lines), and nothing feeds **what the agent reused vs.
rewrote** back into what's worth remembering. v0.41.0 closes NeuralMind's half of both
seams — without collapsing the layers into one black box.

### A shared relevance signal → Headroom

NeuralMind already computes, per retrieved node, a vector **score**, a learned
**synapse boost**, and a **recall flag**. It now exposes them as a machine-readable
sidecar that travels alongside the payload:

```bash
neuralmind query . "How does auth work?" --relevance --json
# → adds a `relevance` block: per-file, per-node {score, synapse_boost, recalled, lines}
```

(Over MCP: `neuralmind_query` with `include_relevance: true`.) A compressor downstream
reads `relevance.files[].nodes[].lines` and **protects the load-bearing spans** instead
of squeezing them — the exact failure mode a blind compressor hits. The block is
**versioned and stably keyed**, so a tool running *after* NeuralMind can re-associate the
signal regardless of pipeline order: the seam is order-independent by design, not a
function of which layer happens to run first.

### A feedback loop: reuse vs. rewrite → memory

NeuralMind's `install-hooks` now registers an **`Edit`/`Write`** PostToolUse hook. When
the agent's new code reaches for a symbol already defined elsewhere in the graph, that
**reuse** is fed back into the synapse layer — so future retrieval (and the generation
guardrail judging "reuse what exists") sees the helpers and modules the team actually
reuses, not just what scores well semantically. It's language-agnostic, best-effort, and
a pure side effect (emits nothing to the agent). Disable with
`NEURALMIND_REUSE_FEEDBACK=0`.

This is the loop that connects the **generation** stage back to **retrieval**: what the
agent did with the context becomes a signal about what context to surface next time.

## Step 4 — Verify the stack end-to-end

Run a representative agent session and measure:

```bash
# Retrieval layer
neuralmind benchmark . --json       # confirms NeuralMind reduction ratio

# Transport layer
headroom stats                      # shows per-session payload reduction (Headroom CLI)

# Generation layer
grep -r "ponytail:" . --include="*.py" --include="*.ts" | wc -l
# zero = model found native solutions; nonzero = deliberate shortcuts logged for /ponytail-debt
```

Expected combined outcome on a real codebase:

| Source | Typical reduction |
|---|---|
| NeuralMind retrieval | 5–10× vs naive file ingestion |
| Headroom transport | 2–5× on structured tool results |
| Ponytail generation | 42–77% fewer output tokens on task completion |

## Deployment recommendations by team type

### High-volume research / SRE incident debugging

Deploy **NeuralMind + Headroom**, skip Ponytail or use `Lite`.

The bottleneck is inbound data volume (logs, stack traces, API responses) and KV cache
stability across long incident threads. Ponytail's generation steering adds deliberation
overhead with minimal payoff when queries are investigative rather than generative.

```bash
# Prioritize: fast retrieval + compressed transport
neuralmind build . && neuralmind install-mcp --all
# configure Headroom proxy, set profile=lite in ponytail config
```

### Rapid feature development / MVP

Deploy **NeuralMind + Ponytail** with `Full` profile, add Headroom if API spend is a
concern.

The bottleneck is output token bloat — agents generating custom classes for things the
standard library handles. Ponytail's ladder eliminates this at the source.

```bash
neuralmind build . && neuralmind install-hooks .
# add Ponytail system prompt steer or MCP config, profile=full
```

### Enterprise-scale agentic fleet

Deploy all three. Key additions over single-tool setups:

- **Memory namespaces** (`neuralmind memory inspect`) — branch-isolated learning prevents
  feature-branch experiments from polluting `main`'s synapse graph.
- **Ponytail debt ledger** (`/ponytail-debt`) — harvests `ponytail:` annotations across
  the codebase into a tracked ledger for sprint planning.
- **Headroom CCR audit** — SQLite cache provides a local audit trail of every compressed
  payload, useful for regulated environments that require input traceability.
- **NeuralMind EXTRACTED/INFERRED tags** (`query --trace`) — every retrieved element is
  tagged as verbatim source or heuristically inferred, satisfying explainability
  requirements without a cloud dependency.

## Deliberation cost note for reasoning models

On models with extended thinking (Claude Fable 5, o3), Ponytail's `Ultra` profile can
trigger a net-cost regression. The model burns thinking tokens deliberating on the
YAGNI/Stdlib/Native ladder. The break-even is:

```
savings = (baseline_output_tokens - lazy_output_tokens) × output_price
cost    = rules_input_tokens × input_price + reasoning_tokens × think_price
```

If `cost > savings`, switch to `Full`. NeuralMind and Headroom are unaffected — they
operate on the data path, not the reasoning path, so they save tokens regardless of
thinking budget.

## What this doesn't replace

- **Output quality** — the stack optimizes token count, not correctness. Pair with
  evaluation (`neuralmind benchmark --quality`) to confirm retrieval quality doesn't
  degrade as you tune.
- **Security controls** — Ponytail explicitly excludes input validation, auth checks,
  and data-loss prevention from its simplification rules. Never compress those.
- **Model selection** — token savings scale with input price. If you're on a cheap
  model, absolute dollar savings are lower; the stack pays off most on frontier models.

---

[← Back to use-case index](./README.md) · [Context engineering stack guide](../comparisons/context-engineering-stack.md) · [Main README](../../README.md)
