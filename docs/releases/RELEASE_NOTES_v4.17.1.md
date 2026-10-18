# NeuralMind v4.17.1 — three security fixes: a CUI profile a developer can't delete, roles off the MCP path, and an audit chain that survives concurrent writers

**Type:** Patch release | **Theme:** controls that hold when someone tests them. An audit of the compliance documents against the code found three controls that didn't do what the documents said

An assessor checks a control by trying it. Three of NeuralMind's failed that
test:

- **Deleting one file switched the CUI profile off.** `security.profile: cui`
  was read only from `neuralmind-backend.yaml` in the project root. Whoever owns
  that directory can delete the file, even one an administrator owns, and OS
  identity, the encrypted-storage check, and the listener and LLM-seeding
  refusals all switched off without a word.
- **Roles stopped at the MCP server.** Under `security.identity: os`, an OS
  account mapped to `reader` couldn't call `neuralmind_build` through MCP, but
  could build through the daemon's `/build` route or with `neuralmind build`.
- **The tamper-evident audit log reported tampering nobody did.** The MCP
  server, the hooks, the CLI and the daemon all append to
  `.neuralmind/audit_events.jsonl`, but only a per-process lock guarded each
  append. Four processes writing 200 records each produced a log that
  `neuralmind audit verify` called tampered. A log that flags honest writes
  can't tell an assessor anything.

---

## What changed

### A machine policy keeps the CUI profile on

An administrator can now write the profile where a project's owner can't
reach it:

```yaml
# /etc/neuralmind/policy.yaml          (POSIX: root:root, mode 0644, directory 0755)
# C:\ProgramData\NeuralMind\policy.yaml (Windows: Administrators full control, Users read)
security:
  profile: cui
```

- **It applies to every project on the machine and only tightens.** Each of
  `profile`, `identity` and `require_encrypted_storage` takes the stricter of
  the machine's value and the project's, so neither file can loosen the other.
  With the project file deleted, the profile stays on and, with no `users` left,
  every MCP call is refused.
- **It can't grant anything.** It holds only those three settings. Roles
  (`users`, `default_role`, `roles`) and the audit checkpoint settings stay in
  each project's file, so a user who manages to create the machine policy gains
  nothing.
- **A machine policy that can't be trusted holds everything to the strictest
  settings:** one that doesn't parse, names any other key, holds an invalid value (`identity: sometimes`), or on POSIX isn't
  owned by root and writable only by root (the file and its directory).
  `neuralmind doctor` fails its *Security policy* check with the reason.
- **Its location is fixed.** It isn't read from an environment variable, and on
  Windows it's found through the shell rather than `%ProgramData%`, which any
  user can change.

`neuralmind doctor` names the machine policy when one applies:

```
  [ ok ] Security profile: profile: cui (identity: os, encrypted storage required, servers on loopback with their token only, LLM seeding refused); OS FIPS mode on; machine policy /etc/neuralmind/policy.yaml applies
```

### Roles apply to the daemon and the CLI's writes

Under `security.identity: os` (which `profile: cui` forces), each daemon route
that acts on a project needs the role the MCP tool doing the same thing needs:

| Daemon route | Needs |
|---|---|
| `/query`, `/search`, `/stats`, `/savings` | `neuralmind_query`, `neuralmind_search`, `neuralmind_stats`, `neuralmind_savings` |
| `/build` | `neuralmind_build` |
| `/validate` | `neuralmind_health`, or `neuralmind_build` with `write: true` |

`neuralmind build` and `neuralmind validate --write` need `neuralmind_build`
too. A custom `security.roles` applies as it does to MCP calls, and a broken one
refuses. A refusal writes a `security`/`call_denied` audit record naming the
surface. The daemon answers `403` with `code: security_denied` and `reason`
`rbac`, `identity` or `config`; the CLI prints the reason and exits `1`:

```
neuralmind: refused: OS account 'bob' has role 'reader', which may not use neuralmind_build (cli)

Run `neuralmind doctor` to see the Security policy check.
```

With `identity: declared` (the default) nothing off the MCP path names a role,
so nothing is checked, as before. Other CLI commands and the hooks run with the
account's own file permissions, which stay the boundary against a local account
that owns the project's files.

### The audit chain survives concurrent writers

Each append now holds an OS lock on `.neuralmind/audit_events.lock` (`flock`
on POSIX, `msvcrt.locking` on Windows) while it reads the last record's hash
and writes the new record, and so does `audit rotate`. Without it, a rotation
could also send a record to the archive after its last hash was read, or
truncate it away when the continuation marker opened the new file.

A log written by an earlier version may still fail `verify` where two records
share a `prev_sha256` with timestamps within a second of each other. That was
this race, not an edit; a checkpoint (`neuralmind audit checkpoint`, v4.16.0)
taken since tells the two apart.

## What the agent actually sees

Nothing changes for an agent on a project with `identity: declared`.

On a project with `identity: os` or `profile: cui`, the MCP tools behave as
before. What changes is around them:

- **A git hook rebuild run by an account without `neuralmind_build`** is now
  refused, so the agent's next query carries v4.17.0's line: `Index may be
  stale: the last background rebuild failed (log: .neuralmind/hook-build.log)`.
  The log shows the refusal. Give the account a role that allows
  `neuralmind_build`.
- **A project whose `neuralmind-backend.yaml` was deleted**, on a machine with a
  CUI machine policy, refuses the agent's MCP calls (`reason: identity`, no
  role) instead of serving them without the profile.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | Under `identity: os`, the hook-triggered rebuild needs `neuralmind_build`; MCP calls unchanged |
| Cursor / Cline / Continue (MCP) | MCP calls unchanged; daemon clients get `403` for a route their role lacks |
| Hermes-Agent plugin | As Claude Code |
| Generic MCP client | As Cursor |

## Upgrading

- **CUI enclaves: add the machine policy.** Write
  `/etc/neuralmind/policy.yaml` as above on each machine, then run
  `neuralmind doctor .` in a project and check the *Security profile* line
  names it.
- **Under `identity: os`, check each account that builds.** The account the git
  hooks and `neuralmind build` run as needs a role allowing
  `neuralmind_build` (the default `builder` and `admin` do; `reader` doesn't).
  A daemon serving such a project needs the same for the routes it's asked to
  serve.
- **Scripts calling the daemon** can get a new `403` with `reason` `rbac`,
  `identity` or `config` on a project with `identity: os`.
- Nothing changes for projects with `identity: declared` and no machine policy.

## Reproduce

```bash
pytest tests/test_machine_policy.py -v       # deleting the project file keeps the profile; tighten-only; untrusted files
pytest tests/test_local_role_checks.py -v    # daemon routes and CLI writes need the role the MCP tool needs
pytest tests/test_audit_new.py -k "processes_appending or rotation_during" -v   # concurrent writers keep the chain
pytest tests/test_cli_exit_codes.py -k build-refused-by-role
```

## Related

- [Security guide: the machine policy](../SECURITY-GUIDE.md#the-machine-policy), [binding roles to OS accounts](../SECURITY-GUIDE.md#binding-roles-to-os-accounts-identity-os)
- [CUI enclave walkthrough](../use-cases/cmmc-cui-enclave.md): now with the machine policy
- [Access control policy](../compliance/ACCESS_CONTROL.md): where roles are enforced
- [v4.17.0 release notes](RELEASE_NOTES_v4.17.0.md): the freshness line a refused hook rebuild now shows up in
