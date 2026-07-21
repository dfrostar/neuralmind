# Wave 14 — Free Customer End-to-End Journey Map

**Date:** 2026-07-22  
**Author:** Darren Frost (dfrostar)  
**Scope:** What happens when a stranger discovers NeuralMind, installs it, and (maybe) becomes a team customer.  
**Method:** Code-trace — every claim cites file:line against the live repo. No speculation.

---

## The Journey Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STRANGER discovers Neuralmind via Show HN / Reddit / search                 │
│       │                                                                     │
│       ▼                                                                     │
│  Homepage (neuralmind.uk) — CTA: "pip install neuralmind"                  │
│       │                                                                     │
│       ▼                                                                     │
│  pip install neuralmind → pip install                                       │
│       │                                                                     │
│       ▼                                                                     │
│  neuralmind wakeup .  (first run)                                           │
│       │                                                                     │
│       ├─► Index is built (✓ works)                                         │
│       ├─► NO license created          ◄── GAP #1 (HIGH)                   │
│       ├─► NO memory consent prompt    ◄── GAP #8 (LOW)                    │
│       ├─► NO "free tier" message      ◄── GAP #1 (HIGH)                   │
│       └─► NO upgrade CTA              ◄── GAP #3 (HIGH)                   │
│       │                                                                     │
│       ▼                                                                     │
│  neuralmind onboarding   ← only if user discovers it on their own            │
│       │                                                                     │
│       ├─► Writes free license to ~/.config/neuralmind/license.json           │
│       ├─► Prompts: scope, threshold, admin email                            │
│       └─► ✓ Working (verified end-to-end)                                   │
│       │                                                                     │
│       ▼                                                                     │
│  User runs: neuralmind team license status                                   │
│       │                                                                     │
│       ├─► If onboarding was run: shows license JSON (✓)                     │
│       └─► If NOT run + tier2.yaml has tier="team": BLOCKED    ◄── GAP #2  │
│             "License file missing. Run neuralmind team license activate"     │
│       │                                                                     │
│       ▼                                                                     │
│  OPERATOR (separate persona)                                                 │
│       │                                                                     │
│       ├─► autopilot web-admin --port 8765   (works, undocumented)           │
│       ├─► autopilot license issue --email ... (works, undocumented)         │
│       ├─► autopilot license portal --email ... (works, undocumented)         │
│       └─► autopilot key rotate              (works, undocumented)           │
│       │                                                                     │
│       ▼                                                                     │
│  CUSTOMER receives signed license file, runs:                                │
│       │                                                                     │
│       └─► neuralmind team license activate <signed.json>   (works)         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Findings (Ground-Truth)

### Stage 1: Discovery → Homepage CTA

- Homepage Hero has **three CTAs** (`site/src/components/sections/Hero.tsx:54-76`):
  1. `pip install neuralmind` (primary, href `#install`)
  2. `Source on GitHub` (href https://github.com/dfrostar/neuralmind)
  3. **`For teams →`** (href `/pricing`) ← the only paid-tier path
- Navbar and Footer now both include `/pricing` and `/team` links.
- **Verdict:** Discovery surface works. CTA exists.

### Stage 2: First Run (pip install → wakeup)

| Question | Answer | File:Line |
|----------|--------|-----------|
| (a) Free license auto-created? | **NO** | `neuralmind/cli.py:406` — `cmd_wakeup` calls `create_mind` only |
| (b) User prompted for anything? | **NO** (on wakeup) | `neuralmind/cli.py:388-402` — `_maybe_prompt_for_memory_opt_in()` only runs inside `cmd_query` |
| (c) Any "free tier" CTA? | **NO** | `grep -rn "upgrade\|free.*tier"` across `neuralmind/neuralmind/` — zero hits |
| (d) Where does license.json go? | Only if onboarding/team is run | `neuralmind/tier2/config.py:96` — default `~/.config/neuralmind/license.json` |
| (e) Default tier in fresh tier2.yaml? | **`"team"`** — LANDMINE | `neuralmind/tier2/config.py:95` |

**The wakeup path is functionally free-tier-blind.** A user can install, index, query, and never know tiers exist.

### Stage 3: Free Tier Behavior (Actual)

- `SeatManager.can_add_seat(license_limit, tier="free")` → returns `True` unconditionally (`neuralmind/tier2/seats.py:97-98`)
- `NeuralMind.build()`, `wakeup()`, `query()` have **zero tier-conditioned branches** — core engine is identical
- Free users are blocked only from `neuralmind team seats add/remove/sync`
- **Verdict:** Product works as free. User just has no identity.

### Stage 4: Conversion (Free → Paid)

| Check | Result |
|-------|--------|
| Any `upgrade` string in CLI code? | **0 hits** |
| Any link to `/pricing` from CLI? | **0 hits** |
| Any "contact sales" in code? | **0 hits** (only in Next.js site) |
| Onboarding → upgrade prompt? | Only if user says **no** to free tier |

**Verdict: There is no conversion funnel.** Free users never learn Team exists.

### Stage 5: Operator Side

- `autopilot web-admin` — functional, dark dashboard, issue/revoke licenses (`autopilot/web_admin.py`)
- `autopilot license issue/revoke/portal/list` — all work (`autopilot/cli.py:73-149`)
- All **undocumented** in wiki.
- Customer can self-check with `neuralmind team license status` **only if they first ran onboarding**

### Stage 6: Documentation Coverage

| Doc | Exists? | Gap |
|-----|---------|-----|
| `wiki/FAQ.md` — "Is NeuralMind free?" | ✅ | No next-step CTA |
| `wiki/CLI-Reference.md` — onboarding command | ❌ | Missing entirely |
| `wiki/CLI-Reference.md` — web-admin | ❌ | Missing entirely |
| `wiki/CLI-Reference.md` — autopilot license issue | ❌ | Missing entirely |
| `wiki/Tier2-Operator-Guide.md` | ❌ | Needed |
| `wiki/Free-Tier-Walkthrough.md` | ❌ | Needed |

---

## Gap Table (Severity-Ordered)

| # | Gap | Severity | Impact | Fix |
|---|-----|----------|--------|-----|
| 1 | **No free-license auto-provision on first run** | **HIGH** | User has zero identity in tier2 system until they discover `onboarding` | Issue free license in `cmd_wakeup` on first run; print activation message |
| 2 | **Default `tier="team"` blocks free auto-issue** | **HIGH** | User running `neuralmind team ...` before `onboarding` is told to buy, not told they have free tier | Change `Tier2Config.tier` default to `"free"`, or auto-issue free when `seats <= 1` and license missing |
| 3 | **No upgrade CTA anywhere in CLI** | **HIGH** | Zero conversion funnel — paid tier is invisible from inside the product | Print one-liner after N queries or when savings exceed threshold |
| 4 | **Operator `autopilot` + `web_admin.py` entirely undocumented** | **MEDIUM** | Operators must read source to deploy Tier 2 | Create `wiki/Tier2-Operator-Guide.md` |
| 5 | **`neuralmind onboarding` wizard undocumented** | **MEDIUM** | Users discover it only via `--help` | Add CLI-Reference entry with step walkthrough |
| 6 | **No customer-facing dashboard** | **MEDIUM** | Customers must use JSON CLI output; no self-serve portal | Add read-only `neuralmind team self-service serve` or expand `cmd_team_license portal` |
| 7 | **No free → team upgrade docs** | **MEDIUM** | Marketing draft references a command that doesn't exist | Ship `neuralmind team license provision` or document the real path |
| 8 | **Memory opt-in only on `query`, not `wakeup`** | **LOW** | Consent prompt deferred indefinitely | Call `_maybe_prompt_for_memory_opt_in()` from `cmd_wakeup` or `main()` |

---

## Remediation Plan

### Sprint 1 — Ship Blockers (HIGH only)

1. **Fix the default tier:** Change `Tier2Config.tier` default from `"team"` to `"free"` (`neuralmind/tier2/config.py:95`). This is a one-line change that unblocks every other fix.
2. **Auto-issue free license on first run:** In `cmd_wakeup` (or `cmd_build`), check if `~/.config/neuralmind/license.json` exists. If not, call `issue_free_license()` and print `"Free tier activated — run neuralmind onboarding to configure, neuralmind team license status to view."`
3. **Add upgrade CTA:** After every 10th `cmd_wakeup`/`cmd_query`, print a one-liner:  
   `NeuralMind Team: $29/user/mo — shared memory, governance, seat management. See neuralmind.uk/pricing or run neuralmind onboarding`

### Sprint 2 — Documentation (MEDIUM)

4. **`wiki/Tier2-Operator-Guide.md`:** Cover `autopilot` CLI, web-admin, license issuance, seat manifest flow, key rotation.
5. **`wiki/Free-Tier-Walkthrough.md`:** Walk through `pip install → wakeup → onboarding → team license status` with screenshots/CLI output examples.
6. **Update `CLI-Reference.md`:** Add `onboarding`, `autopilot web-admin`, `autopilot license issue/revoke/portal/list` entries.

### Sprint 3 — Customer Experience (MEDIUM)

7. **`wiki/Upgrade-Guide.md`:** Document real path: `autopilot license issue` → deliver signed file → customer runs `team license activate`. Delete references to nonexistent `neuralmind team license provision`.
8. **Customer self-serve:** Either extend `cmd_team_license portal` to print a URL or add a read-only dashboard.

### Sprint 4 — Polish (LOW)

9. Move `_maybe_prompt_for_memory_opt_in()` out of `cmd_query-only` — call it from `cmd_wakeup` or `main()` globally so consent is captured first-run regardless of command.

---

## What This Document Maps To

| Code | Procedure (this doc) |
|------|---------------------|
| `autopilot/web_admin.py` | Stage 5 — Operator dashboard |
| `autopilot/cli.py:73-149` | Stage 5 — License issue/portal CLI |
| `neuralmind/onboarding.py` | Stage 4 — Free → team bridge |
| `neuralmind/tier2/config.py:95` | GAP #2 — Default tier landmine |
| `neuralmind/tier2/license.py:397-431` | Stage 2 — Free tier auto-issue (exists but never triggered on `wakeup`) |
| `neuralmind/tier2/seats.py:97-98` | Stage 3 — Seat bypass for free tier |
| `docs/wiki/CLI-Reference.md` | Stage 6 — Missing onboarding + autopilot entries |
| `site/src/components/Navbar.tsx:15-16` | Stage 1 — Pricing/Team links |

---

## Honest Wave 14 State Summary

Wave 14 shipped the **surface layer** (UI, pages, wizard) atop the Wave 12-13 governance engine. The surface works in isolation — but **the moment you step back and trace what a stranger actually experiences**, three landmines emerge:

1. **No identity on first run** (no license created)
2. **Default config actively fights free tier** (default tier is "team")
3. **No funnel to discover the paid tier** (zero CTAs)

These are ship-blockers for any meaningful MVP launch. One sprint (1-3 above) closes them. The rest (4-9) closes the loop on documentation and customer experience so the surface isn't just functional but navigable.

---

*WAVE14-FREE-CUSTOMER-JOURNEY.md v1.0. Code-traced, not wishful.*
