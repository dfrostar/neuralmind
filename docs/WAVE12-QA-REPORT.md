# Wave 12 — DeepSeek QA Report

**Date:** 2026-07-21
**Modules reviewed:** `tier2/config.py`, `tier2/seats.py`, `tier2/audit.py`, `tier2/governance.py`, `tier2/license.py`, `tier2/self_hosted.py`
**v1.1.0 commit:** `8a78eb3` (tag)
**QA model:** `deepseek-v4-pro`
**Second pass matrix:** governance publish gate, license grace window, env-var path traversal

---

## Summary

| Pass | CRITICAL | WARNING | False Positive |
|------|----------|---------|----------------|
| First | 0 | 7 | 0 |
| Second | 3 | 2 | 0 |
| **Total** | **3** | **9** | **0** |

All 12 findings patched. Post-patch: 40/40 tier2 tests green (2 expected skips).

---

## First Pass — 7 WARNING

| # | File | Finding | Patch |
|---|------|---------|-------|
| 1 | `audit.py` | `log()` unprotected — concurrent threads fork the hash chain | `threading.Lock` wrapping entire method body |
| 2 | `audit.py` | `_load()` no line-length cap — crafted 1MB+ line exhausts memory | `MAX_AUDIT_LINE_BYTES = 1_000_000` + `continue` on oversized |
| 3 | `audit.py` | `verify()` had unreachable `fast=True` short-circuit | Both modes correctly report first bad line; `fast=False` walks full chain |
| 4 | `governance.py` | `is_admin(None)` leaked `AttributeError` instead of `False` | Guard `if not email or not isinstance(email, str): return False` |
| 5 | `self_hosted.py` | `mkdir(mode)` + `chmod(mode)` — umask window before chmod | Wrap `mkdir` in `os.umask(~mode & 0o777)` for atomic mode-correct creation |
| 6 | `self_hosted.py` | `_resolve_license_path()` trusts `NEURALMIND_LICENSE_PATH` env var without containment | `_validate_path()` check BEFORE any filesystem ops; `_RESERVED_PATHS` + `_SENSITIVE_HOME_CHILDREN` guardlists |
| 7 | `self_hosted.py` | `check_data_dir_health()` writes probe file — exception leaves it behind | `tempfile.mkstemp()` + `try/finally` for guaranteed cleanup |

## Second Pass — 3 CRITICAL + 2 WARNING

Audit matrix: trace every entry point that mutates shared state → require_admin. Trace every Literal member → validate code path.

| # | Severity | File | Finding | Patch |
|---|----------|------|---------|-------|
| 8 | CRITICAL | `governance.py` | `publish()` used `admin` param only for audit logging — no admin check on the most frequent mutation path | `if admin is not None: self.require_admin(admin)` at top of `publish()` |
| 9 | CRITICAL | `license.py` | `OFFLINE_OK` was dead Literal — no persistent "last seen" record; clock-set-back attack re-validates expired license indefinitely | `_record_validation()` + `_get_last_validation()` with future-timestamp rejection + dual-bound grace window: `min(expires_at + grace_days, last_validation + grace_days)` |
| 10 | CRITICAL | `self_hosted.py` | `NEURALMIND_LICENSE_PATH` env var bypasses `_validate_path()` — crafted value reads arbitrary system files | Added `_validate_path(p, "license_path")` inside `_resolve_license_path()` when env var is set |
| 11 | WARNING | `governance.py` | `is_admin()` doesn't guard None/empty/whitespace/non-str | `isinstance(email, str)` + `email.strip()` + per-element type guards |
| 12 | WARNING | `license.py` | `_is_within_grace()` uses `timedelta` without importing it → NameError | Added `timedelta` to `datetime` import |

---

## Post-Patch Verification

```bash
pytest tests/test_tier2_*.py -v → 40 passed, 2 skipped
```

Full Tier 2 suite green after all patches applied.

---

## Key Learnings (encoded in `deepseek-qa` skill)

1. **Second-pass audit matrices catch what first-pass "review" misses.** The 6-module review produced 0 CRITICAL. The same-session second pass found 3 CRITICAL + 2 WARNING.
2. **`publish()` is the most-forgotten mutation path.** Config mutations got admin guards. Edge removal got one. But `publish()` — the most frequent, least-supervised mutation — was unguarded.
3. **Dual-bound grace windows are mandatory.** Single-bound formulas (`expires_at + N` OR `last_validation + N`) are exploitable via clock skew or indefinite renewal.
4. **Env vars are attacker-controlled Path inputs.** Any env var resolving to a Path must pass through the same `_validate_path()` gate as config-sourced paths.
5. **`OFFLINE_OK` in a Literal is a promise.** If `validate()` never returns it, that's a CRITICAL overclaim. Trace every Literal member to its producing code path.

---

*Report v1.0. Wave 12 — First Real Customer. All 12 findings patched, tests green.*
