# Wave 12 — DeepSeek QA Final Sweep

**Date:** 2026-07-23
**Modules reviewed:** `tier2/governance.py`, `tier2/license.py`
**Scope:** Verify patches applied after WAVE12-QA-REPORT.md gap closure
**DeepSeek dispatches:** 2 (governance + license, parallel)

---

## Summary

| Dispatch | CRITICAL | WARNING | Result |
|----------|----------|---------|--------|
| governance.py | 1 | 4 | All patched |
| license.py | 0 | 1 | Patched |
| **Total** | **1** | **5** | **All fixed** |

All 74/74 tier2 tests pass post-patch.

---

## Findings + Patches Applied

### governance.py — 1 CRITICAL + 4 WARNING

| # | Severity | Finding | Patch |
|---|----------|---------|-------|
| 1 | CRITICAL | `publish()` `admin=None` default bypasses `require_admin()` — unprivileged callers publish with no credentials | Changed to `admin: str` (required, no default). Matches other 4 admin-gated methods |
| 2 | WARNING | No negative test for publish() admin gate | Added `test_governance_non_admin_cannot_publish` |
| 3 | WARNING | Docstring claimed "Dedup" step that doesn't exist | Removed phantom dedup line from docstring |
| 4 | WARNING | Docstring claimed "fast-fail all-or-nothing" but code processes individually | Changed to "per-edge weight threshold" |
| 5 | WARNING | Docstring said `admin` "defaults to 'system'" but actual default was `None` (silent bypass) | Updated to "Required. Email of the admin performing the action" |

### license.py — 0 CRITICAL + 1 WARNING

| # | Severity | Finding | Patch |
|---|----------|---------|-------|
| 6 | WARNING | `_record_validation()` uses non-atomic `write_text()` — concurrent multi-process reads could hit partial write | Switched to `tempfile.mkstemp()` + `Path.replace()` for atomic writes |

Plus cleanup:
- Replaced `__import__("datetime").timedelta` with proper `from datetime import timedelta` import
- Moved `tempfile` to stdlib import group

---

## Post-Patch Verification

```bash
pytest tests/test_tier2_*.py -v → 74 passed, 0 skipped
```

All grace tests pass:
- Within grace → OFFLINE_OK
- Beyond grace → EXPIRED
- No record → EXPIRED
- Clock-skew (future sidecar) → EXPIRED
- Malformed expires_at → EXPIRED (fail-closed)

---

## Key Lessons (encoded in `deepseek-qa` skill)

1. **`admin=None` default is a silent bypass.** If a method should require admin verification, make the parameter required — never optional with a default that skips the check.
2. **Docstring overclaims are real verbosity.** Describing features that don't exist (dedup, fast-fail) creates false security impressions and wastes auditor time.
3. **Non-atomic writes in concurrency-sensitive paths matter.** `write_text()` looks safe but corrupts under multi-process access. Use `tempfile.mkstemp()` + `rename()`.

---

*Report v1.0. Wave 12 — First Real Customer. DeepSeek QA complete.*
