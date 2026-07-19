# Tier 2 (Team) — DeepSeek QA Plan

**Product:** NeuralMind
**Tier:** Team ($29/user/mo, annual)
**Version:** v0.52.0 → v1.0.0
**Author:** Darren Frost
**Date:** 2026-07-19

---

## 1. Executive summary

DeepSeek QA reviews all methodology-encoding work in Tier 2. Dispatch per-module, inline code, patch CRITICAL+WARNING. This plan defines what to review, how to dispatch, and the risk areas per module.

---

## 2. Modules to review (priority order)

| Module | File | Risk level | Why |
|--------|------|------------|-----|
| Audit log | `tier2/audit.py` | HIGH | Hash chain tamper detection is security methodology |
| License validation | `tier2/license.py` | HIGH | Ed25519 verification, offline grace logic |
| Governance | `tier2/governance.py` | MEDIUM | Edge weight comparison, no bypass paths |
| Seats | `tier2/seats.py` | MEDIUM | Seat limit enforcement |
| Config | `tier2/config.py` | LOW | Pydantic schema validation |
| Self-hosted | `tier2/self_hosted.py` | MEDIUM | Data dir creation, file permissions |

---

## 3. Dispatch shape (per validated pattern)

```
Per-module focused dispatch (leaf role)
+ provider pinned to deepseek-v4-pro
+ inline the critical code sections + tests in the prompt
+ explicit checklist of risk areas per module
+ ask DeepSeek to propose patch diffs, not just findings
→ Hermes patches → pytest → next module
→ After all modules patched, dispatch a final cross-module integration review
```

---

## 4. Per-module DeepSeek review checklist

### 4.1 Audit log (`tier2/audit.py`)

Review:
1. Hash chain: `SHA256(entry.data + entry.prev_hash)` — Genesis hash correct? First entry uses `SHA256("neuralmind-team-audit-v1")`?
2. Tamper detection: if record N is modified, does record N+1's hash mismatch?
3. Append-only: is there any code path that modifies or deletes an audit record?
4. Export: does `export_csv` / `export_json` handle unicode, escaping, null fields?
5. Index usage: does `idx_audit_ts` get used by the date-range query?

### 4.2 License validation (`tier2/license.py`)

Review:
1. Ed25519 verify: does `verify()` correctly handle malformed signatures (wrong length, trailing bytes)?
2. Offline grace: is the 30-day window calculated from `last_successful_validation` or from `license.issued_at`?
3. Clock skew: what happens if system clock is set back? Does it extend the grace period?
4. Machine ID binding: is `device_fingerprint` derived from something stable (MAC, machine-id) vs volatile (IP, hostname)?
5. Seat limit: does `can_add_seat()` re-check license seat count on every call (not cache)?

### 4.3 Governance (`tier2/governance.py`)

Review:
1. Weight comparison: is `>=` used (not `>`) for threshold check? Does `0.0` allow all?
2. Scope "personal": does it actually prevent any edge from entering shared namespace?
3. Admin check: is `is_admin()` enforced on every governance mutation (no bypass via direct DB write)?
4. Publish idempotency: does content-hash check prevent duplicate edges under concurrent publish attempts?

### 4.4 Seats (`tier2/seats.py`)

Review:
1. Seat limit: is the check atomic (read-license → check-count → add) or can a race condition add seat N+1?
2. Duplicate email: does `add_seat` on an existing active seat return success (not error)?
3. Removal: does `remove_seat` deactivate or hard-delete? Hard-delete orphans audit records?

### 4.5 Config (`tier2/config.py`)

Review:
1. Pydantic validators: does `weight_threshold` reject negative values? Does `half_life` reject zero?
2. Scope: does `publishing_scope` reject arbitrary strings (e.g., `"public"` instead of `"shared"`)?
3. YAML load: does `load_config` handle missing file → return defaults (not crash)?
4. Save directory: does `save_config` create parent dirs if missing?

### 4.6 Self-hosted (`tier2/self_hosted.py`)

Review:
1. Data dir: does `init_data_dir()` set 700 permissions?
2. License file path: does `init_license()` fail clearly if license.json is missing in self-hosted mode?
3. Docker compose: does bind_address default to `127.0.0.1` (not `0.0.0.0`)?

---

## 5. Cross-module integration review

After all 6 modules pass their per-module review, dispatch one final cross-module review:

**Question:** Does `audit.log()` get called from every code path that mutates state?
- Governance `remove_edge` → audit?
- Self-hosted `init_data_dir` → audit?
- Seat `add_seat` / `remove_seat` → audit?
- Config `save_config` → audit?
- License activation → audit?

**Question:** Is there any path from CLI `neuralmind team X` to `governance.py` that bypasses the admin check?

**Question:** Does the publish path `team_memory.publish()` check governance, audit the attempt, AND respect scope — in that order?

---

## 6. Acceptance gate

- 0 CRITICAL findings unpatched
- 0 WARNING findings unpatched
- All NICE-TO-HAVE findings documented (patch at discretion)
- All 48 tests pass after patching
- Post-patch integration review confirms no new findings

---

*DeepSeek QA plan complete. Next: Kickoff prompt.*
