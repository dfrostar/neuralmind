# Use NeuralMind in a CMMC CUI enclave

> Goal: run NeuralMind on source code that is Controlled Unclassified
> Information (CUI), inside an environment assessed against CMMC 2.0 Level 2,
> with each MCP role tied to a real OS account and the index refused on any
> disk that isn't encrypted.

CMMC assesses a defense contractor's environment, not a tool, so NeuralMind
itself has nothing to be assessed against. What matters is what NeuralMind does inside
your assessment scope and what evidence it leaves. This walkthrough sets up the
two controls added in v4.7.0 and shows what an assessor can check.

**Existing use case it improves:** [offline and regulated
environments](offline-regulated.md) and [air-gapped installs](air-gapped.md),
which keep NeuralMind's own traffic off the network but, before v4.7.0, still
trusted whatever role an MCP call declared.

**New use case it opens:** teams building for the defense industrial base,
such as compliance tooling or contractors' internal apps, can use an AI
coding agent with persistent codebase memory on CUI code. The MCP layer
enforces per-account roles, and the index can't land on an unencrypted laptop
disk.

## 1. Decide whether your code is CUI

Most application source code isn't CUI, even when the application handles CUI.
If yours isn't, NeuralMind is a developer tool outside the enclave and nothing
here is required. If it is, the index, synapse store, decision memory, audit
log and command-output cache that NeuralMind derives from it are CUI too, and
the steps below apply.

## 2. Install without network egress

Follow the [air-gapped walkthrough](air-gapped.md): install from a wheelhouse
and pre-seed the embedding model with `NEURALMIND_ONNX_MODEL_DIR`. Leave
`NEURALMIND_LLM_SEED` unset; it is the only path that sends text (README and
architecture-doc prose, never code) to a third party.

## 3. Write the policy

Have an administrator create `neuralmind-backend.yaml` in the project root,
owned by them and writable only by them:

```yaml
security:
  identity: os
  users:
    alice: builder
    bob: reader
  roles:
    builder: [neuralmind_wakeup, neuralmind_query, neuralmind_search, neuralmind_skeleton, neuralmind_build]
    reader: [neuralmind_wakeup, neuralmind_query, neuralmind_search, neuralmind_skeleton]
  require_encrypted_storage: true
```

```bash
chmod 644 neuralmind-backend.yaml
```

- `identity: os` takes each MCP caller's identity from the OS account the
  server runs as. Over the stdio transport that is the developer who launched
  the agent. The `role` a call declares is ignored and logged as a claim.
- `users` maps OS accounts to roles. An account that isn't listed is refused,
  unless you add `default_role`.
- `roles` without `admin` means no account can reach admin-only tools.
- `require_encrypted_storage` makes NeuralMind refuse to build, query, serve MCP
  tools or run hooks until it has verified FileVault, BitLocker or
  dm-crypt/LUKS on the project's volume.

Keep the MCP server on stdio. `identity: os` refuses the HTTP transport,
because over HTTP the server's account isn't the caller's.

## 4. Check it on each machine

```bash
neuralmind doctor .
```

```
  [ ok ] Security policy: identity: os; account 'alice' gets role 'builder'
  [ ok ] Storage encryption: /System/Volumes/Data: FileVault on (macOS has no FIPS mode switch; FileVault uses Apple corecrypto, whose validation is listed in Apple's CMVP certificates)
```

On Linux and Windows the storage line also reports whether the OS FIPS mode is
on. If it's off while encryption is required, `doctor` warns: CMMC asks for
FIPS-validated cryptography. A group-writable policy file is a warning too,
since anyone in the group could change roles.

## 5. What an assessor can look at

Everything lands in `.neuralmind/audit_events.jsonl`, hash-chained:

- a `storage_check` event per process, with the volume, method, FIPS mode and
  verdict;
- an `mcp_call` or `mcp_call_denied` event per tool call, whose actor is the OS
  account, with `claimed_role` / `claimed_actor` whenever a call declared
  something else;
- `mcp_call_denied` with `reason: identity` for any call the server couldn't
  attribute.

`neuralmind audit verify` walks the hash chain. It detects a changed or removed
record in the middle of the log, but not removal of the newest records or a
rewritten chain, so forward the log to your SIEM.

For the practice-by-practice mapping, with what NeuralMind provides and what
stays yours, see the [CMMC 2.0 table in the Compliance
Summary](../COMPLIANCE-SUMMARY.md).

## 6. What stays outside NeuralMind

- **The encryption itself.** NeuralMind verifies it; FileVault, BitLocker or
  LUKS (with the OS FIPS mode on) provides it.
- **OS accounts and their authentication.** `identity: os` is only as good as
  the logins behind it, and anyone who can run commands as an account can read
  that account's `.neuralmind/` directly.
- **Your agent's model provider.** NeuralMind hands code slices to the coding
  agent, and the agent sends them to its model. If that code is CUI, the
  provider must meet DFARS 252.204-7012 (FedRAMP Moderate or equivalent).
  NeuralMind reduces how much code goes out; it can't make a provider
  eligible.

## Related

- [v4.7.0 release notes](../releases/RELEASE_NOTES_v4.7.0.md)
- [Security Guide — Access Control](../SECURITY-GUIDE.md#access-control)
- [Security settings reference](../wiki/CLI-Reference.md)
