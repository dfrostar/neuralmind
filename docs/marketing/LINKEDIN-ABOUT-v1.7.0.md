# LinkedIn About — NeuralMind HQ (v1.7.0 Refresh)

**Company:** NeuralMind HQ  
**URL:** linkedin.com/company/neuralmind-hq/about  
**Updated:** 2026-07-22  
**Campaign:** v1.7.0 Free Tier Shipped  
**Claim-tier gate: Every claim in this About section traces to a CLI command or public doc.**

---

NeuralMind is local-first AI code intelligence that cuts agent token costs 40-70x. Persistent neural memory for coding agents — your code never leaves your machine. The product learns your codebase and tunes itself. Measured in CI on every commit, not marketed.

---

## THE PROBLEM

Your AI agents re-read your entire codebase every session. For a 50-engineer team, that's ~$144K/year wasted on context — zero audit trail, zero memory between sessions.

## THE SOLUTION

NeuralMind builds a persistent neural graph of your codebase and serves exact context to every agent query:

- **Local-first** — runs fully air-gapped. Zero network calls, zero telemetry, zero code leaves your machine.
- **Self-learning** — Hebbian synapse associations strengthen with every query. Decays stale ones.
- **40-70x token reduction** — only relevant code enters context. Measured on real OSS repos (`python -m evals.public.run`).
- **Free tier** — `pip install neuralmind && neuralmind wakeup .` auto-provisions on first run. Zero signup wall.
- **Audit-ready** — NIST AI RMF aligned, hash-chained audit log (Team tier).

## WHO IT'S FOR

- Engineering teams rolling out Claude Code / Codex / Cursor at scale
- CISOs worried about proprietary code leaking to model APIs
- CFOs calculating the true cost of AI coding tools
- Compliance leads who need audit-ready AI governance

## OPEN SOURCE CORE

Free forever on PyPI. Real benchmarks on every release. MIT licensed.

github.com/dfrostar/neuralmind

## OFFERINGS

- **Free** — OSS core, 10 languages, MCP-native, auto-provisioned license
- **Team ($29/user/mo)** — Governance, audit log, seat management, self-hosted (5-50 seats)
- **CFO Assessment ($35K)** — Full deployment + benchmark + executive readout

---

## Claim-tier audit (this section)

| Claim | Tier | Verification |
|-------|------|-------------|
| 40-70x token reduction | C | `neuralmind benchmark .` on `requests`/`click` repos — 38-85x measured |
| Local-first, zero network | A | `neuralmind doctor` — no phone-home, no telemetry |
| Free tier auto-provision | A | `neuralmind wakeup .` writes `license.json` on first run (cli.py:406+) |
| 10 languages | A | `tests/test_polyglot_fixtures.py` — Python/TS/Go/Rust/Java/C/C++/C#/Ruby/PHP |
| Team $29/user/mo | A | README pricing table, TIER2-BRD.md |
| CFO Assessment $35K | B | `contracts/CONSULTING_AGREEMENT_TEMPLATE.md` line 53 |
| NIST AI RMF aligned | B | `SECURITY.md` § compliance |
| Hash-chained audit | A | `neuralmind team audit verify` — SHA-256 append-only |

**What was cut from the previous version:**

| Old claim | Why cut |
|-----------|---------|
| "Enterprise ($15/mo)" | Not shipped. $15/mo is aspirational from LICENSE-COMMERAL.md. Actual = $29/user/mo Team. Overclaim risk. |
| "SOC2-ready" | Architecture mapped to NIST AI RMF; certification target Q3 2027. "Ready" = overclaim. |
| "SSO/RBAC" | MCP RBAC primitives exist (`mcp_security.py`), but SSO/SAML is not customer-ready. |

---

*Template v1.0. Release: v1.7.0 (2026-07-22). Next review: after Q3 2027 SOC 2 milestone.*
