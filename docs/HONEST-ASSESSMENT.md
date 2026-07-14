# Honest Assessment — Where NeuralMind Is (and Isn't) Worth Installing

A direct, numbers-first answer to "should my team adopt this?" Every claim
here cites a specific version or a command you can run yourself. No
marketing.

For the ROI argument, see [BUSINESS-CASE.md](BUSINESS-CASE.md). For what's
shipping when, see [ROADMAP.md](../ROADMAP.md).

---

## Where it shines

**Persistent synapse learning** (v0.11+) — the brain layer learns *what you
edit next*, not just *what goes together*. On long-running projects this
directional signal compounds; teammates inherit it via committed team
memory (v0.30+). No competitor ships an equivalent learning loop today.

**Air-gapped** — zero outbound network at runtime. Verified via `unshare -n`
on Linux and reproducible on a firewalled box. When procurement says "code
never leaves the building," NeuralMind is the only tool in this class that
meets the bar without a custom enterprise deal.

**Agent-agnostic** — ships a bundled MCP server (default since v0.5.0) that
works with Claude Code, Cursor, Cline, and Continue today; Windsurf and Zed
are [Roadmap "Next" items](../ROADMAP.md). You're not locked to one agent
runtime.

## Where it's not worth it

- **Codebase under ~5K lines.** The naive baseline is already small; the
  40–70× ratio doesn't translate to meaningful dollar savings.
- **Free-tier or flat-rate LLM access.** No per-query token cost to reduce.
- **Inline-completion-only workflows.** NeuralMind is for agents, not
  keystroke completion — wrong layer of the stack.
- **Already-optimized stack** with prompt caching + long context. The
  marginal win shrinks. Measure on your workload before deciding.

## What we know works

- **Ten languages** shipped (v0.27–v0.41): Python, TypeScript/JavaScript,
  Rust, Java, C/C++, C#, Ruby, PHP, Go — all behind the tree-sitter seam.
- **40–70× retrieval-stage reduction** in CI on every PR, measured via
  `tiktoken` with the GPT-4o encoding. Community benchmarks on two external
  repos (cmmc20: 65.6×; mempalace: 46.0×) — n=2, so directional, not
  statistically significant. If you don't see ≥10× on your repo, the math
  doesn't pencil out.

## What we don't know yet

- **Answer quality lift.** Does the agent give *better* answers in fewer
  tokens, or just shorter ones? Currently anecdotal; a structured eval set
  is tracked on the roadmap under "Next."
- **End-to-end benchmark validation.** All headline numbers are retrieval
  stage only. The 3–10× end-to-end LLM-cost claim is derived from a
  sensitivity analysis, not observed end-to-end.
- **Enterprise SSO/admin status.** Listed on the roadmap as a commercial
  module, not shipped — see [ENTERPRISE.md](ENTERPRISE.md).

## Known gaps

| Gap | Status |
|-----|--------|
| Trust & transparency six (`--dry-run`, `--explain`, `review`, `savings`, etc.) | Shipped v0.41, lightly tested on real workloads. |
| CI-gated benchmarks on external repos | Fixture + 2 community repos only (n=2). Need n ≥ 10 for confidence. |
| Air-gapped install validation | Documented in v0.9.0; `tcpdump` verification of zero exfiltration still on the validation checklist. |

**Bottom line:** if you're paying for agent inference on a multi-thousand-line
repo, run `bash scripts/demo.sh`. If the ratio doesn't impress you in 30
seconds, nothing else on this page will.
