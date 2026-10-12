# Use NeuralMind in a CMMC CUI enclave

> Goal: run NeuralMind on source code that is Controlled Unclassified
> Information (CUI), inside an environment assessed against CMMC 2.0 Level 2,
> with each MCP role tied to a real OS account, the index refused on any
> disk that isn't encrypted, and *(v4.16.0+)* the whole posture switched on and
> checked as one setting, `security.profile: cui`.

CMMC assesses a defense contractor's environment, not a tool, so NeuralMind
itself has nothing to be assessed against. What matters is what NeuralMind does inside
your assessment scope and what evidence it leaves. This walkthrough sets up the
controls added in v4.7.0, turns them on together with the CUI profile added in
v4.16.0, and shows what an assessor can check.

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
  profile: cui            # v4.16.0+
  users:
    alice: builder
    bob: reader
  roles:
    builder: [neuralmind_wakeup, neuralmind_query, neuralmind_search, neuralmind_skeleton, neuralmind_build]
    reader: [neuralmind_wakeup, neuralmind_query, neuralmind_search, neuralmind_skeleton]
```

```bash
chmod 644 neuralmind-backend.yaml
```

`profile: cui` switches on every setting below as one unit. Each is enforced at
run time, and a refusal is written to the audit log:

- **`identity: os`.** Each MCP caller's identity comes from the OS account the
  server runs as. Over the stdio transport that is the developer who launched
  the agent. The `role` a call declares is ignored and logged as a claim.
  `users` maps OS accounts to roles; an account that isn't listed is refused,
  unless you add `default_role`. `roles` without `admin` means no account can
  reach admin-only tools.
- **`require_encrypted_storage: true`.** NeuralMind refuses to build, query,
  serve MCP tools or run hooks until it has verified FileVault, BitLocker or
  dm-crypt/LUKS on every volume holding the project's state.
- **Local listeners only.** `neuralmind serve` refuses to start on an address
  other than loopback, or with `--no-auth`. A shared `neuralmind daemon`
  started that way refuses this project's requests, while still serving
  projects without the profile. Reach the graph view from another machine
  through an SSH tunnel.
- **No LLM documentation seeding.** It is refused even with
  `NEURALMIND_LLM_SEED=1` set, so no README or architecture prose goes to a
  model provider.

The profile can't be loosened from the same file. `profile: cui` with
`identity: declared` or `require_encrypted_storage: false` is a contradiction,
and so is a misspelled or blank profile. NeuralMind then refuses every MCP call
and holds the project to the profile until the file is fixed. Before v4.16.0,
set `identity: os` and `require_encrypted_storage: true` yourself; there was no
listener or seeding refusal.

Keep the MCP server on stdio. `identity: os` refuses the HTTP transport,
because over HTTP the server's account isn't the caller's.

## 4. Check it on each machine

```bash
neuralmind doctor .
```

```
  [ ok ] Security policy: identity: os; account 'alice' gets role 'builder'
  [ ok ] Storage encryption: /dev/mapper/luks-root: dm-crypt layer present; OS FIPS mode on
  [ ok ] Security profile: profile: cui (identity: os, encrypted storage required, servers on loopback with their token only, LLM seeding refused); OS FIPS mode on
```

The **Security profile** line *(v4.16.0+)* checks what the project file can't
enforce on its own:

- **OS FIPS mode off:** a failure. CMMC SC.L2-3.13.11 asks for FIPS-validated
  cryptography protecting CUI. Without the profile this is only a warning on
  the storage line.
- **FIPS mode that can't be read** (macOS has no FIPS mode switch; FileVault
  uses Apple corecrypto, listed in Apple's CMVP certificates): a warning to
  confirm by hand.
- **`NEURALMIND_LLM_SEED=1` left set:** a warning. The profile refuses it, but
  it shouldn't be in the enclave's environment.
- **Embedding model not on disk:** a warning, because the first build would
  download it. Pre-seed it as in step 2.
- **A running daemon listening beyond loopback or without its token:** a
  warning, because it refuses this project.

`doctor` exits 1 on any failure, so the check can gate a provisioning script. NeuralMind's own hash calls work with the FIPS
mode on *(v4.13.0+; before that, `neuralmind ingest` crashed there)*. A
group-writable policy file is a warning too, since anyone in the group could
change roles.

## 5. What an assessor can look at

Everything lands in `.neuralmind/audit_events.jsonl`, hash-chained:

- a `storage_check` event per process, with the volume, method, FIPS mode and
  verdict;
- an `mcp_call` or `mcp_call_denied` event per tool call, whose actor is the OS
  account, with `claimed_role` / `claimed_actor` whenever a call declared
  something else;
- `mcp_call_denied` with `reason: identity` for any call the server couldn't
  attribute;
- *(v4.16.0+)* a `profile_refused` event, status `denied`, each time the CUI
  profile stops something: `target` names what it stopped (`serve`, `daemon`
  or `llm_seed`) and `details.reason` says why.

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

- [v4.16.0 release notes](../releases/RELEASE_NOTES_v4.16.0.md): the CUI profile
- [v4.7.0 release notes](../releases/RELEASE_NOTES_v4.7.0.md)
- [NIST: what applies, where it stands, what's next](../compliance/NIST.md)
- [Security Guide — Access Control](../SECURITY-GUIDE.md#access-control)
- [Security settings reference](../wiki/CLI-Reference.md)
