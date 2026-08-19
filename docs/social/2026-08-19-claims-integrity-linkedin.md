# LinkedIn post — week of 2026-08-19

Company-page post covering the site claims-integrity gate shipped in
PR #437 and hardened same-day in PR #440.

## Post text

This week we audited our own marketing site for the same failure mode NeuralMind exists to prevent in AI coding agents: a confident claim with nothing underneath it. The site failed its own audit.

We found a token-reduction figure attributed to a repo size that matches nothing in any of our benchmarks, a query-latency number with no measurement behind it anywhere in the codebase, and a "100% recall" claim our own public benchmark contradicts — the real mean across four test repos is 93.75%, with the weakest repo at 79%. None of it was deliberate. It was ordinary copy drift across many releases.

We corrected the numbers, then removed our ability to repeat the mistake. Every performance ratio on our main site pages is now checked against a manifest that names, for each figure: the exact repo it was measured on, its evidence level (CI-gated, reproducible on demand, a single field report, or a community submission), and the command to reproduce it. A number with no matching entry fails the build. We hardened the check the same day, so a ratio now has to match its repo and its evidence level, not just its value — one of the original errors was a real measurement, just attached to a codebase it was never run on.

93.75% mean, 79-100% per repo, is the number we publish now instead of the rounder one. Anyone can reproduce it from a clean clone (python -m evals.public.run).

If you're evaluating AI dev tooling for your organization, that's the standard worth asking every vendor for — us included. The manifest is public: github.com/dfrostar/neuralmind/blob/main/site/claims.json. Free tier: one seat, no signup, never expires, same code path as Enterprise — no feature gate, only a seat limit.

#AIagents #DeveloperTools #EngineeringCulture

## Image prompt (Gemini)

A dark, editorial tech-illustration on a near-black navy background (#070b15). At the center, a small glowing force-directed network of nodes and connecting lines — some connections thin and dim, one or two thick and bright — rendered in electric blue (#3b82f6 to #60a5fa) and violet-purple (#a855f7) tones, evoking a living, learning system. On the right side, the network's lines resolve into the clean, sharp edge of a torn paper receipt or ledger strip, as if the graph itself is printing an audit trail — same electric-blue linework, one small glowing checkmark or seal at the seam where graph meets receipt. A faint, softly glowing downward-curving line ghosted deep in the background suggests falling cost over time — barely visible, more mood than data. Generous negative space, minimal composition, moody and precise rather than busy. Style: high-end enterprise-software editorial illustration (think Stripe, Linear, or The Economist's tech covers) — not photorealistic, not cartoonish, no 3D render gloss. Absolutely no text, numbers, letters, human figures, robots, or circuit-board clichés anywhere in the image. Landscape orientation, 1.91:1 aspect ratio.

## Claim sources

| Claim in post | Source |
|---|---|
| Repo-size misattribution, unsupported latency, rounded-up recall | `tests/test_site_claims.py` docstring; `site/claims.json` `unsourced_do_not_use` |
| 93.75% mean / 79% floor | `site/claims.json` → `docs/benchmarks/public.md`, reproduced via `python -m evals.public.run` |
| Manifest + CI gate | PR #437, "fix(site): source every marketing number, gate the site against claim drift" (2026-08-18) |
| Same-day hardening (repo + evidence level, not just value) | PR #440, "fix(tests): bind site ratios to their repo and evidence level" (2026-08-18) |
| Free-tier terms | `commercial-terms.json` (canon; no trial language, per `do_not_market`) |

## Correction post — for the prior LinkedIn post

Standalone post to run alongside (or as a comment on) the earlier infographic post, explicitly naming what changed and why — per "Correct it, and say so."

### Post text

A correction to our last post.

Before: "Sub-second retrieval — 0.81s."
After: Retrieval is a local index lookup, not another model call.
Why: We couldn't find a benchmark anywhere in our repo that produces 0.81s. It didn't measure anything, so we removed it rather than requote it more carefully.

Before: "12–50x Average Token Reduction."
After: 12–50x token reduction on real repos — the low and high end of a range, not an average.
Why: 12 and 50 are real, field-reported numbers. Calling them an "average" implied a calculation that was never done.

Before: "Zero telemetry or code egress — your IP never leaves your machine."
After: No telemetry. No calls home. NeuralMind itself makes no network calls of its own.
Why: Your agent still sends its chosen context to its model — that hasn't changed. The absolute claim overstated what we actually control.

The same audit that caught these produced the CI gate in this week's post: every number on our site now has to name its source and evidence level before it ships. This is that same discipline, applied backward to our own back catalog.

#AIagents #DeveloperTools #EngineeringCulture

### Source check for each line

| Before → After | Source |
|---|---|
| 0.81s → "local index lookup, not another model call" | `site/claims.json`, `unsourced_do_not_use`: "No measurement anywhere in the repo produces this number... Speed claims must be mechanism-based." The replacement phrase is quoted directly from that entry. |
| "Average" 12-50x → "range, low/high end, not an average" | `site/claims.json` `ratios`, entries `value: 12` / `value: 50`, `evidence: "field-report"`, "Directional, not a guarantee." |
| "Never leaves your machine / zero code egress" → "no network calls of its own" | `tests/test_docs_claims.py` FORBIDDEN patterns (`egress`, `never leaves... machine`) and its prescribed replacement phrasing; `site/src/app/effectiveness/page.tsx`'s own "honesty gate" disclaims "zero code egress" as an overclaim. |
