# NeuralMind v4.8.0 — `audit verify` checks the whole log

**Type:** Minor release | **Theme:** audit integrity

`neuralmind audit verify` passed logs it should have failed. In v4.7.0 and
earlier:

1. **A record without a hash passed at the end of the log.** The last records
   could be edited and their `sha256` removed, or forged records appended
   with none.
2. **A line it couldn't read was skipped, not reported.** Garbage, a JSON
   value that isn't an object, or an oversized line appended to a valid log
   left it passing. One invalid UTF-8 byte made it read no records at all and
   report `ok`.
3. **The stored `prev_sha256` was never compared.** The hash covers each
   record without its hash fields, so the link field could be changed or
   deleted freely.

All three now fail, each with the line number and the reason.

## `audit verify`, before and after

`verify` treated any record without a `sha256` as a legacy line, written
before the hash chain existed (v0.46.2). It accepted such records anywhere.
A missing hash mid-log was caught only because the next record's hash stopped
matching. And it read the log through the same tolerant parser that search
and export use, which skips what it can't parse.

Now:

- **Once the chain has started, a record without a hash fails.** A legitimate
  record appended after it doesn't hide it.
- **Every non-empty line must be a JSON object.** Bad UTF-8, bad JSON, a
  non-object value, or a line over 1 MB fails verification. Search and export
  still skip such lines, so a damaged log stays readable.
- **Each record's `prev_sha256` must match the hash of the record before it.**
- **Line numbers are lines in the file**, blank lines included, so the number
  in a failure is where to look.
- **Records before the chain are reported.** They're still accepted, because
  versions before v0.46.2 wrote them, but the output says how many there are
  and that the chain doesn't cover them. A log stripped of every hash still
  passes, as records outside the chain, so read that count.
- **A rotated log verifies, and is linked to its archive.**
  - `AuditTrail.rotate()` hashed its continuation marker differently from
    every other record, so the new file failed at line 1.
  - The marker also chained to zeros instead of the archive's last hash: the
    backward scan for the last line stopped on the archive's final newline.
  - The marker now links to the archive and is hashed like every other
    record. `verify` starts from it, and checks it against the archive while
    the archive is still there.
  - A malformed marker fails verification instead of raising.
  - No CLI command rotates the log.
- **`--json` adds `unchained`, `continues_from`, `archive_checked` and
  `reason`.** The existing keys are unchanged. When the file can't be read at
  all, `first_bad_line` is `null` and `reason` says why.

Still not detected: records deleted from the end, and a chain recomputed by
anyone who can write the file, because the hash has no secret key. Keep an
exported copy off the host (`neuralmind audit export`). Risk
[R-07](../compliance/RISK_ASSESSMENT.md) stays MEDIUM for that reason.

Each tamper case has a test in `tests/test_audit_new.py`, including one that
pins truncation as undetected so the docs can't claim otherwise.

## What the agent actually sees post-install

Nothing: `audit verify` is a CLI check, not an MCP tool.

## Upgrade notes

- `pip install -U neuralmind`. No configuration changes.
- **Run `neuralmind audit verify .` after upgrading.** A log that passed
  before can fail now. NeuralMind always hashes and links what it writes,
  and writes one JSON object per line. So treat a failure as a record changed,
  added or damaged outside NeuralMind, and look at the line it names.

## Related

- [Security Guide — Audit Trail](../SECURITY-GUIDE.md#audit-trail)
- [CLI Reference — audit verify](../wiki/CLI-Reference.md#audit-verify)
- [Risk Assessment](../compliance/RISK_ASSESSMENT.md)
