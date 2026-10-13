# NeuralMind v4.16.0 — `security.profile: cui`: the CUI-enclave posture as one setting, enforced and checked as a unit

**Type:** Minor release | **Theme:** NIST SP 800-171 / CMMC Level 2 hardening, part 1. One setting switches on every control a CUI enclave needs, refuses what would weaken them, and leaves a record of each refusal

Running NeuralMind on CUI source code took four separate decisions, made by
hand and checked by hand:
- `identity: os`;
- `require_encrypted_storage: true`;
- keeping `neuralmind serve` on loopback with its token;
- leaving `NEURALMIND_LLM_SEED` unset.

Nothing stopped someone from starting the graph view on `0.0.0.0` for a demo,
or switching seeding on in a shell profile. Nothing told an assessor all four
were in force. [docs/compliance/NIST.md](../compliance/NIST.md) listed a single
hardened profile as the next SP 800-171 item; this release ships it.

---

## What changed

### `security.profile: cui`

Set it in `neuralmind-backend.yaml`:

```yaml
security:
  profile: cui
  users:
    alice: builder
```

- **Forces `identity: os` and `require_encrypted_storage: true`.** MCP callers
  are the OS account the server runs as, with the role from `users`. Nothing
  is built, queried, served or hooked until every volume holding the project's
  state is verified encrypted.
- **Refuses `serve` beyond loopback or without its token.** `neuralmind serve
  --host 0.0.0.0` (or any non-loopback address) and `--no-auth` stop before
  building or binding anything, with exit 1:
  ```
  serve refused: security.profile: cui refuses to serve this project because it listens on '0.0.0.0', beyond loopback. Serve it on 127.0.0.1 with its access token, and reach it from another machine through an SSH tunnel.
  ```
- **A daemon started that way refuses the project.** The daemon is one
  per-user process shared by every project, so the profile can't stop it from
  binding. A daemon listening beyond loopback or without its token instead
  answers every request for a CUI project with `403` (`code: security_denied`,
  `reason: profile`). The CLI then runs the command directly. Projects without
  the profile are served as before.
- **Refuses LLM documentation seeding,** even with `NEURALMIND_LLM_SEED=1` and
  an API key set, so no README or architecture prose goes to a model provider.
  `neuralmind ingest` says so instead of staying silent.
- **Every refusal is audited.** Each is written to
  `.neuralmind/audit_events.jsonl` as `security` / `profile_refused`, status
  `denied`. `target` names what was stopped (`serve`, `daemon`, `llm_seed`) and
  `details.reason` says why.

### It can't be loosened, and it fails closed

- `profile: cui` with `identity: declared` or `require_encrypted_storage:
  false` is a contradiction, not a choice. The profile stays in force, and
  every MCP call is refused until the file is fixed.
- A blank or misspelled profile (`profile:`, `profile: cuii`) is never read as
  "no profile". It is held to the strictest one, and MCP calls are refused.
- A `neuralmind-backend.yaml` that doesn't parse but names `profile` is also
  held to it.

### `neuralmind doctor` checks the profile as a unit

A new **Security profile** line covers what a project file can't enforce on its
own:

| Finding | Result |
|---|---|
| Profile contradicted or misspelled | fail |
| OS FIPS mode off (CMMC SC.L2-3.13.11) | fail. Without the profile this is a warning on the storage line |
| OS FIPS mode can't be read (macOS) | warn |
| `NEURALMIND_LLM_SEED=1` left set | warn: the profile refuses it, but it shouldn't be in the enclave's environment |
| Embedding model not on disk (default turbovec backend) | warn: the first build would download it |
| A running daemon listening beyond loopback or without its token | warn: it refuses this project |
| None of the above | ok, naming what the profile enforces |

Without a profile the line reports `ok` with "none". `doctor` exits 1 on any
failure, so the check can gate a provisioning script.

## What the agent actually sees

Nothing changes for an agent in a project without the profile.

Under `profile: cui`:
- MCP tool calls behave as they already did with `identity: os` and
  `require_encrypted_storage: true`: a call from an account without a role, or
  from a disk that isn't verified encrypted, comes back as `security_denied`.
- Query results, hook output and tool schemas are unchanged.
- The difference is around the agent: the graph view and the daemon won't
  expose the project's index to the network, and the agent's documentation
  can't be sent for LLM seeding.

## Per-agent expectations

| Agent | What changes under `profile: cui` |
|---|---|
| Claude Code (hooks + MCP) | MCP calls attributed to the OS account and refused without a role; hooks refuse on an unverified disk (fail-open: they inject nothing and exit 0) |
| Cursor / Cline / Continue (MCP) | Same MCP behaviour; keep the server on stdio, since `identity: os` refuses the HTTP transport |
| Hermes-Agent plugin | Same hook behaviour as Claude Code |
| Generic MCP client | Same as Cursor |

## Upgrading

- **No change unless you set the profile.**
- **If you already set `identity: os` and `require_encrypted_storage: true`:**
  replace them with `profile: cui`, or keep them alongside it, since they agree
  with it.
- **Check the profile:** run `neuralmind doctor .` and look at the Security
  profile line.
- **If a script runs `neuralmind serve --host 0.0.0.0` for a CUI project,**
  it now exits 1. Use an SSH tunnel to `127.0.0.1` instead.

## Not in this release

The rest of the SP 800-171 work, in order:
- audit-log checkpoints that detect removal of the newest records or a
  recomputed chain (AU.L2-3.3.8);
- live syslog forwarding with an alert when audit logging fails (AU.L2-3.3.4,
  3.3.5).

See [NIST.md §3](../compliance/NIST.md#3-whats-next).

## Reproduce

```bash
pytest tests/test_security_profile.py -v
pytest tests/test_cli_exit_codes.py -k serve-refused -v

printf 'security:\n  profile: cui\n' > neuralmind-backend.yaml
neuralmind serve . --host 0.0.0.0; echo "exit $?"   # serve refused … exit 1
neuralmind doctor .                                  # Security profile line
```

## Related

- [Use NeuralMind in a CMMC CUI enclave](../use-cases/cmmc-cui-enclave.md): the walkthrough, rewritten around the profile
- [Compliance Summary: CMMC 2.0](../COMPLIANCE-SUMMARY.md#cmmc-20--practice-evidence): AC.L2-3.1.1, AC.L2-3.1.20, CM.L2-3.4.7, SC.L2-3.13.8 (new row) and SC.L2-3.13.11
- [NIST: what applies, where it stands, what's next](../compliance/NIST.md)
- [Security settings reference](../wiki/CLI-Reference.md#security-settings-security-in-neuralmind-backendyaml)
- [Security Guide: In transit](../SECURITY-GUIDE.md#in-transit)
