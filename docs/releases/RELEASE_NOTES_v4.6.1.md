# NeuralMind v4.6.1 — the role policy and the audit check do what the docs say

**Type:** Patch release | **Theme:** security controls

Three fixes to controls the [Security Guide](../SECURITY-GUIDE.md) describes:

1. **The MCP server applies `security.roles` and `security.rate_limit`.**
   v4.6.0 and earlier ignored both and always ran the default policy.
2. **A malformed or empty role policy refuses calls** instead of falling back
   to the default policy, which includes `admin`.
3. **`neuralmind audit verify` catches records without a hash at the end of
   the log.** v4.6.0 and earlier passed records edited or appended there with
   their hash removed.

## 1. The MCP server applies the role policy

`neuralmind-mcp` built its security manager without reading
`neuralmind-backend.yaml`, so every call got the default role policy and a
fixed limit of 60 calls per 60 seconds. A policy that left out `admin` didn't
stop a caller from declaring `admin`. Both settings now take effect, per
project.

## 2. A broken policy fails closed

- **`roles: {}` grants nothing.** An empty mapping used to count as unset, so
  the server substituted the default policy, `admin` included.
- **A malformed policy refuses every call.** If `security` or `security.roles`
  isn't a mapping, or `security.rate_limit` isn't a mapping, has a value that
  isn't a whole number, or sets `window_seconds` below 1, each MCP call returns
  `security_denied` with `reason: "config"`. These used to be ignored, crash,
  or switch the limit off.
- **`rate_limit: null` means the defaults**, 60 calls per 60 seconds.

## 3. `audit verify` catches records without a hash at the end of the log

`verify` treated any record without a `sha256` as a legacy line, written
before the hash chain existed (v0.46.2). It accepted such records anywhere,
and a missing hash mid-log was only caught because the next record's hash
stopped matching. So at the end of the log, two kinds of tampering passed:

- the last records edited, with their `sha256` removed
- forged records appended with no `sha256`

Now:

- **Once the chain has started, a record without a hash fails**, and the
  failure names the line and the reason. A legitimate record appended after it
  doesn't hide it.
- **Records before the chain are reported.** They're still accepted, because
  versions before v0.46.2 wrote them, but the output says how many there are
  and that the chain doesn't cover them. A log stripped of every hash still
  passes, as records outside the chain, so read that count.
- **A rotated log verifies, and is linked to its archive.** `AuditTrail.rotate()`
  hashed its continuation marker differently from every other record, so the
  new file failed at line 1. Its marker also chained to zeros instead of the
  archive's last hash, because the backward scan for the last line stopped on
  the archive's final newline. The marker now links to the archive and is
  hashed the same way as every other record. `verify` starts from it and checks
  it against the archive while the archive is still there. A malformed marker
  fails verification instead of raising. No CLI command rotates the log.
- **`--json` adds `unchained`, `continues_from`, `archive_checked` and
  `reason`.** The existing keys are unchanged.

Still not detected: records deleted from the end, and a chain recomputed by
anyone who can write the file, because the hash has no secret key. Keep an
exported copy off the host (`neuralmind audit export`). Risk
[R-07](../compliance/RISK_ASSESSMENT.md) stays MEDIUM for that reason.

Each tamper case has a test in `tests/test_audit_new.py`, including one that
pins truncation as undetected so the docs can't claim otherwise.

## What the agent actually sees post-install

| Agent | Before | After |
|---|---|---|
| **Claude Code** (MCP + hooks) | Every call ran the default policy, whatever `neuralmind-backend.yaml` said | The project's `security.roles` and `rate_limit` apply. A tool outside the caller's role returns `security_denied` with `reason: "rbac"` |
| **Cursor / Cline / Continue** (MCP) | Same as Claude Code | Same fix |
| **Generic MCP client** | Declaring `role: "admin"` reached every tool | Declaring `admin` reaches only what the policy grants it. A malformed policy returns `reason: "config"` |

`audit verify` is a CLI check, so agents see no change from fix 3.

## Upgrade notes

- `pip install -U neuralmind`. Configuration only needs a change in the two
  cases below.
- **If you set `security.roles`, it takes effect now.** Check that it grants
  the tools your agents call. Leaving `admin` out now really keeps callers away
  from admin-only tools.
- **If you set `roles: {}`**, every call is refused. Remove the key to use the
  default policy.
- **Run `neuralmind audit verify .` after upgrading.** A log that passed before
  can fail now if a record at its end has no hash. NeuralMind always hashes
  what it writes, so treat that as a record changed or added outside
  NeuralMind.

## Related

- [Security Guide: Audit Trail](../SECURITY-GUIDE.md#audit-trail)
- [Security Guide: Access Control](../SECURITY-GUIDE.md#access-control)
- [CLI Reference: audit verify](../wiki/CLI-Reference.md#audit-verify)
- [Risk Assessment](../compliance/RISK_ASSESSMENT.md)
