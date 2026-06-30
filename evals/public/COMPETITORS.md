# Competitor benchmarks — what's reproducibly scorable, and what isn't

The recurring critique asks for scored head-to-heads vs Bloop, Sourcegraph Cody,
Continue/Cline, and Tejas Headroom. We run exactly one **live, scored** competitor
today (`codebase-memory-mcp`) and we're honest about why the others aren't here yet:
a fair, *reproducible* retrieval benchmark needs a competitor that can be driven
**headless, on a pinned repo, with no account**, and that returns ranked files we
can score on the **same** def-site / gold-patch oracle every NeuralMind backend uses.

This file is the durable record of that status. It is **not** a list of excuses —
where a tool *is* tractable (Bloop), the adapter seam is ready; where it isn't, the
exact blocker is named so a contributor knows what it would take.

## Status matrix

| Competitor | Status | What it is | Blocker / how to unblock |
|---|---|---|---|
| **codebase-memory-mcp** (DeusData) | ✅ **scored, live** | Local single-binary semantic code memory, headless CLI | None — see [`competitor.py`](competitor.py) + [`bench/public/competitor/`](../../bench/public/competitor/). Reproduce: `pip install codebase-memory-mcp==0.8.1 && python -m evals.public.competitor` |
| **Bloop** | ◐ **adaptable** | Local Rust code-search app (vector + keyword) | Adapter seam matches `competitor.py` (index → semantic query → ranked files → `BackendResult`). Needs a verified **headless** invocation against a pinned checkout; its current distribution is GUI/server-first. Contribution-ready. |
| **Sourcegraph Cody** | ✗ **account-gated** | Server-hosted, org-wide code context | Cody's context API requires a Sourcegraph instance + auth token; results depend on server-side indexing we can't pin per-commit. Not reproducible without an account, so any number would be unauditable. |
| **Continue / Cline** | ✗ **no headless retrieval** | IDE agent runtimes (VS Code / JetBrains extensions) | These are *agent runtimes* that consume a context layer; they expose no headless "retrieve files for this query" CLI to score in isolation. The honest comparison is architectural (see [`docs/comparisons/vs-continue-cline.md`](../../docs/comparisons/vs-continue-cline.md)), not a retrieval head-to-head. |
| **Tejas Headroom** | ✗ **wrong axis** | Universal context **compression** proxy | Headroom compresses what flows to the model; it is not a code *retriever* and returns no ranked file list, so gold-file recall doesn't apply. The right comparison is **compression ratio at fixed fidelity**, a different benchmark — tracked separately. See [`docs/comparisons/vs-headroom.md`](../../docs/comparisons/vs-headroom.md). |

## The fairness contract (any new competitor must meet it)

Lifted from the `codebase-memory-mcp` row so a new adapter is apples-to-apples:

1. **Headless + pinned.** Driven by CLI/API against a repo checked out at an exact
   commit — no GUI, no account, no server-side index we can't reproduce.
2. **Ranked files out.** Returns a ranked list of files (or chunks → files) we can
   cap at the shared retrieval depth (`SEM_LIMIT = 8`, matched to the vector-RAG
   baseline) and score with the **same** `neuralmind.quality` code.
3. **Most-favorable reproducible input.** If the interface differs (e.g. a keyword
   array vs free text), pick the *best-for-the-competitor* reproducible mapping and
   say so — no per-query hand-tuning.
4. **Pin the version, commit the raw traces.** Exact version, verbatim CLI, and
   per-query JSON traces committed under `bench/public/<competitor>/`.
5. **Fail closed.** Absent binary / errored call → clean skip, never a stale or
   fabricated result.

A new adapter that satisfies this drops in next to `run_competitor` and is scored
by the existing harness — no metric math is reinvented.

## Honest framing of the one live row

The `codebase-memory-mcp` head-to-head is **pure retrieval ranking** (no LLM agent
loop on either side — the same way we test NeuralMind's own `search`). We use the
competitor's *most-favorable* reproducible keyword mapping, and we cite its
*published* LLM-agent figures as-is rather than reproduce them. So the win is on
reproducible retrieval ranking, not on agent-driven published numbers.
