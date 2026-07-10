# LinkedIn post draft — Fable pricing / context-quantity levers

Genre-matched to the Headroom owner's 2026-07-09 Fable-pricing post:
news hook → concrete levers for enterprises running Claude Code → soft
CTA. His levers tune the **price** of context; this post owns the
**quantity** lever. Written partner-to-partner — it compliments the
price-tuning advice without naming or countering him.

## ⚠️ Before posting — verify these two things

1. **Pricing.** Verified against Anthropic's published models table on
   2026-07-09: **Claude Fable 5 = $10 / 1M input, $50 / 1M output**
   (Opus 4.8 = $5/$25, Sonnet 5 = $3/$15). **The Headroom owner's post
   said $30/1M output — that figure is wrong per Anthropic's docs.**
   This post uses the correct $50. The held reply comment to his post
   was checked against the 2026-07-09 session transcript: it cites only
   the $10/1M input figure, so it's safe to post as-is.
2. **v0.42.0 status.** PR #315 is still DRAFT/unmerged (latest tag:
   v0.41.0). Do **not** include the optional v0.42.0 paragraph below
   until release-please has tagged v0.42.0. Post works fine without it.

---

## The post

> Anthropic put Claude Fable 5 on standard API pricing: **$10 per 1M
> input tokens, $50 per 1M output.** That's 2× Opus 4.8 on both meters
> — for the most capable model they ship.
>
> If your team runs Claude Code, most of that spend is one thing:
> **context.** A single "how does our auth flow work?" that loads whole
> files into the window is ~50K input tokens. On Fable that's $0.50 —
> per question, per session, per engineer. Nobody notices $0.50.
> Everybody notices it multiplied by questions/day × engineers ×
> workdays, re-paid every session for code the agent already read
> yesterday.
>
> There's good advice going around on tuning the *price* of those
> tokens — model pinning, compaction thresholds, longer cache TTLs. Do
> all of it. Then pull the other lever family: shrink the *quantity*.
> Four things that work today:
>
> 1️⃣ **Answer code questions from a graph, not from pasted files.**
> Graph-backed retrieval answers the same question in ~800 tokens
> instead of 50K+. On our public benchmark (real pinned OSS repos, no
> LLM judge): 100% gold-file recall at **38–85× fewer tokens** than
> pasting files.
>
> 2️⃣ **Compress tool output before the model reads it.** A test run
> dumps 800 lines; the model needs the errors, the repeated-failure
> patterns, and the last 3 lines. Hook-level compression makes
> Read/Bash/Grep output **88–91% smaller**, with the raw output cached
> for recovery — no re-running commands.
>
> 3️⃣ **Stop paying the cold-start tax.** Every fresh session re-reads
> the same context. A learned memory file loaded at session start means
> the agent boots already knowing your code's shape — and committing
> team memory to the repo gives every teammate's agent that head start
> (**+6.5 pts** measured onboarding lift).
>
> 4️⃣ **Measure on your repo, not our benchmark.** `neuralmind
> benchmark .` runs the methodology on your own code; `neuralmind
> savings` reads your real usage log and shows cumulative tokens saved.
> Run your own multiplication.
>
> Honest scope: 40–70× is the *retrieval* line item. A full agent
> workload nets out **~5–10× cheaper end-to-end**, because retrieval is
> one slice of spend. Both numbers scale with whatever per-token price
> you're paying — price levers and quantity levers multiply.
>
> If you tuned your rates last month, tune your volume this month.
>
> Free, MIT, 100% local — your code never leaves your machine.
> Reproduce the numbers in 30 seconds on a fresh clone:
> github.com/dfrostar/neuralmind
>
> #ClaudeCode #AIEngineering #LLMOptimization

---

## Optional v0.42.0 paragraph — insert after lever 3️⃣ ONLY once v0.42.0 tags

> (New this week in v0.42.0: `neuralmind mine-history` pre-warms that
> learned layer from your git history — directional "what gets edited
> after what" transitions mined from actual commits — so the map starts
> warm on day one. And the index stops going stale: watch re-indexes by
> default, plus an incremental git hook.)

## Posting notes

- Genre-match is deliberate: his format is news hook → 3–4 levers →
  soft pitch. Numbered-emoji levers, numbers first, no fluff.
- Don't cite his post or correct his $30 figure publicly — partner
  courtesy. The correct number stands on its own.
- Tuesday/Wednesday morning posting window, per prior drafts.
- Best-effort visual: the token-bar graphic from the landing page
  (50,000 vs ~800, drawn to scale) or a `neuralmind savings` terminal
  screenshot. Post works without one.
