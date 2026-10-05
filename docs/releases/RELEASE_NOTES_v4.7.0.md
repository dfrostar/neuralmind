# NeuralMind v4.7.0 — MCP roles bound to OS accounts, and a check for encrypted storage

**Type:** Minor release | **Theme:** CMMC 2.0 readiness

Until this release, every MCP tool call named its own `actor` and `role`, and
nothing checked either: any caller could declare `admin`. NeuralMind also left
encryption at rest entirely to the host, with no way to confirm it was there.
Both gaps came up when mapping NeuralMind to CMMC 2.0 Level 2 for teams that
index source code containing Controlled Unclassified Information (CUI).

1. **`security.identity: os` ties MCP roles to OS accounts.** The server takes
   the caller's identity from the OS account it runs as — over the default
   stdio transport, the agent that launched it — and the role from
   `security.users`. What a call declares is ignored and kept in the audit log
   as a claim.
2. **`security.require_encrypted_storage: true` refuses unverified volumes.**
   NeuralMind checks for FileVault, BitLocker, or dm-crypt/LUKS and refuses to
   build, query, serve MCP tools, or run hooks until the check passes.
3. **`neuralmind doctor` reports both** as two new checks: *Security policy*
   and *Storage encryption*.

Nothing changes for a project that doesn't set these keys. Both build on
[v4.6.1](RELEASE_NOTES_v4.6.1.md), which made the MCP server apply
`security.roles` and `security.rate_limit` at all.

---

## 1. Identity from the OS, not from the call

```yaml
# neuralmind-backend.yaml
security:
  identity: os
  users:
    alice: builder
    bob: reader
  default_role: reader      # optional; unset refuses accounts missing from users
```

The account name comes from the OS: the passwd entry for the effective uid on
Linux and macOS, `GetUserNameW` on Windows. `LOGNAME`, `USER` and `USERNAME` are
not consulted, because the process that launches the server sets them.

NeuralMind refuses every MCP call, with `reason: identity`, when:

- the HTTP transport is in use (`NEURALMIND_MCP_TRANSPORT=streamable_http`):
  the server's OS account is not the remote caller's;
- the OS account can't be determined;
- the account isn't in `users` and `default_role` is unset;
- the policy file is world-writable (POSIX), since any local user could edit
  the role mapping;
- `identity` has a value other than `declared` or `os`, or `users` isn't a
  mapping.

A policy file that names `identity` or `require_encrypted_storage` but doesn't
parse is refused too. The general config loader treats a broken file as empty,
which would quietly switch enforcement off.

The rate limit keys on the OS account under `identity: os`, so a caller can't
reset its budget by declaring a different actor. Audit events written outside
MCP (CLI queries, builds) also take the OS account as their actor;
`NEURALMIND_ACTOR` is recorded as `claimed_actor` instead of being believed.

**What it does not do.** Anyone who can run commands as that OS account can
also read `.neuralmind/` directly and edit a policy file they own. `identity:
os` makes per-user roles and audit attribution trustworthy on a host where an
administrator owns the policy file and users have separate accounts. On a
single-user laptop its value is attribution: the agent can no longer write a
different name into the audit log.

## 2. Encrypted storage, verified

NeuralMind does not encrypt `.neuralmind/` itself. CMMC SC.L2-3.13.11 asks for
FIPS-validated cryptography, and the OpenSSL inside a pip-installed
`cryptography` wheel is not FIPS-validated, so in-process encryption would not
satisfy the control. The accepted answer is the OS's full-disk encryption, and
NeuralMind now verifies it:

| OS | What counts as encrypted | FIPS mode reported from |
|----|--------------------------|-------------------------|
| macOS | `diskutil` reports FileVault on for the volume. Apple silicon encrypts internal disks in hardware even with FileVault off, but then the key isn't protected by a password, so that doesn't count | Not reported: macOS has no FIPS switch. FileVault uses Apple corecrypto; check Apple's CMVP certificates for your macOS version |
| Linux | `lsblk` shows a `crypt` layer under the filesystem holding the project | `/proc/sys/crypto/fips_enabled` |
| Windows | BitLocker protection on for the drive | The `FipsAlgorithmPolicy` registry value |

The check covers every place NeuralMind's state can land: the project root,
`.neuralmind/` (following a symlink to wherever it points), and a custom vector
index location from `db_path`, whether passed in, configured, or set by a
backend switch. Anything short of a positive answer — a check that times out,
an overlay filesystem in a container, BitLocker suspended — counts as not
verified. Only an explicit `false` (or `0`, `no`, `off`) turns the setting off;
a blank `require_encrypted_storage:` counts as on. The
verdict is written to the audit log once per process as a `storage_check`
event, which gives an assessor a dated record.

With `require_encrypted_storage: true` and an unverified volume:

- `neuralmind build` and `neuralmind query` exit with the reason;
- MCP tools return `security_denied` with `reason: storage`;
- hooks write nothing (no output cache, no synapse transitions) and stay out of
  the agent's way;
- the decision store won't open.

## 3. Malformed policies under the new settings

v4.6.1 refuses a `security:` value of the wrong type with `reason: config`. In
v4.7.0 the MCP dispatcher checks for that before the storage check, so a broken
policy is reported as the cause rather than as a storage refusal it also
triggers. A file that names `identity` or `require_encrypted_storage` but
doesn't parse is refused too; other unparseable files still read as empty, as
in v4.6.1.

## What the agent actually sees post-install

Nothing, unless the project sets the new keys.

With `identity: os`, a tool call that declares `role: admin` runs with the role
`security.users` gives the OS account. A tool outside that role returns:

```json
{"error": "Access denied for role 'reader' on tool 'neuralmind_build'", "code": "security_denied", "reason": "rbac"}
```

An account with no role, or the HTTP transport, returns `reason: identity`.
With `require_encrypted_storage` on an unverified volume, every tool returns
`reason: storage`, with the check's detail in `error`.

| Agent | Transport | `identity: os` | `require_encrypted_storage` |
|-------|-----------|----------------|-----------------------------|
| Claude Code | stdio | Works: the server runs as the developer's account | MCP tools and hooks both refuse on an unverified volume |
| Cursor | stdio | Works | MCP tools refuse; Cursor runs no NeuralMind hooks |
| Cline | stdio | Works | MCP tools refuse |
| Generic MCP client | stdio | Works | MCP tools refuse |
| Any client over Streamable HTTP | HTTP | Refused: the server can't identify a remote caller | MCP tools refuse |

## Environment variables

None added. `NEURALMIND_MCP_TRANSPORT=streamable_http` is now refused under
`identity: os`. Under `identity: os`, `NEURALMIND_ACTOR` no longer sets the
audit actor; it is recorded as `claimed_actor`.

## Upgrade notes

- No action is needed if `neuralmind-backend.yaml` has no `security:` section.
- To adopt `identity: os`, list each OS account in `users`, make the file
  writable only by its owner (`chmod 644`), and run `neuralmind doctor` to see
  the role your account gets.
- To adopt `require_encrypted_storage`, run `neuralmind doctor` first. The
  *Storage encryption* line shows what the check sees on each machine,
  including CI runners, which usually aren't encrypted.

## Related

- [CMMC 2.0 practice mapping](../COMPLIANCE-SUMMARY.md) — what NeuralMind
  provides for each Level 2 practice, and what stays yours
- [Security settings reference](../wiki/CLI-Reference.md)
- [Use case: NeuralMind in a CMMC CUI enclave](../use-cases/cmmc-cui-enclave.md)
- [Security Guide — Access Control](../SECURITY-GUIDE.md#access-control)
