# NeuralMind v4.16.0 — `security.profile: cui` and signed audit checkpoints: the CUI-enclave posture as one setting, and an audit log you can't silently shorten

**Type:** Minor release | **Theme:** NIST SP 800-171 / CMMC Level 2 hardening. One setting switches on every control a CUI enclave needs, refuses what would weaken them, and leaves a record of each refusal; and the audit log's newest records can no longer be removed, or its chain recomputed, without `audit verify` failing

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

The audit log, `.neuralmind/audit_events.jsonl`, is hash-chained. `neuralmind
audit verify` catches a record changed or removed in the middle of the log, but
the chain has no secret. Anyone who can write the file could:
- delete the newest records, leaving a shorter chain that still verifies;
- edit any record and recompute every hash after it.

Until now the only answer was "forward the log to your SIEM". CMMC AU.L2-3.3.8
asks that audit information be protected from unauthorized modification and
deletion, and [docs/compliance/NIST.md](../compliance/NIST.md) listed checkpoints
as the item after the profile. This release ships them too.

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

### Signed, anchored audit checkpoints (CMMC AU.L2-3.3.8)

#### `neuralmind audit keygen`

```bash
neuralmind audit keygen ~/.neuralmind-audit/checkpoint.pem
```

Creates an ECDSA P-256 private key (PEM, mode 0600) and prints the public key
to pin in `neuralmind-backend.yaml`:

```yaml
security:
  audit_checkpoint_key: MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE...
  audit_anchor_dir: /var/lib/neuralmind-anchor
```

Run it in an administrator account, which developers can't read. ECDSA P-256
(FIPS 186-5) is used rather than Ed25519 because every OpenSSL FIPS provider
offers it.

#### `neuralmind audit checkpoint`

```bash
neuralmind audit checkpoint /srv/app --key ~/.neuralmind-audit/checkpoint.pem
```

- **What a checkpoint records:** how many records the log holds, the hash of the
  first and the last, and the hash of the checkpoint before it. It is signed
  with the key.
- **Where it is written:** first to the anchor directory (one file per
  project), then to `.neuralmind/audit_checkpoints.jsonl`. If the anchored copy
  can't be written, nothing is written.
- **What it records in the log:** an `audit_checkpoint` event.
- **What it refuses:**
  - a log whose chain or existing checkpoints already fail, since a checkpoint
    must never vouch for a log that was already tampered with;
  - an unsigned checkpoint while a key is pinned;
  - a key that doesn't match the pinned one.
- **`--json`** prints the checkpoint as one line, ready for a SIEM.

Schedule it as the key's owner, for example daily from the administrator's
crontab.

#### `neuralmind audit verify` checks the checkpoints

After the hash chain, `verify` reads every checkpoint: the local file, the
anchored copy, and any `--checkpoint FILE` you name (for example a copy
exported from your SIEM). It exits 1 when:

| What happened | What `verify` says |
|---|---|
| Records a checkpoint covers were removed from the end | `2 record(s) removed from the end of the log since checkpoint 4 (…), which covers 120` |
| The chain was edited and recomputed | `record 120 no longer has the hash checkpoint 4 (…) recorded: the chain was rewritten` |
| The whole log was replaced, even behind a hand-written rotation marker | `neither the log nor a rotated archive begins with the record checkpoint 1 (…) starts from: the log was replaced or rewritten` |
| A checkpoint was forged, or edited and re-signed with another key | `checkpoint 4's signature doesn't verify with security.audit_checkpoint_key` |
| A checkpoint was deleted from every copy | `checkpoint 3 is missing from every copy (the next is 4)` |
| The local copy and the anchor disagree | `two different checkpoints claim seq 4` |
| A checkpoint setting is malformed | `checkpoint settings: …`, never a quietly weaker check |

On success, a last line says how many checkpoints hold, which records the
newest covers, and whether their signatures were verified. With no checkpoints,
it says what the chain alone can't see.

A checkpoint taken before the log was rotated is checked against the rotated
archive it covers. Only an older checkpoint whose archive has been pruned goes
unchecked (`archive_pruned` in `--json`); the newest must always be found.

#### `neuralmind doctor` gets an **Audit checkpoints** line

| Finding | Result |
|---|---|
| A checkpoint shows truncation, a rewrite or a bad signature | fail |
| Under `security.profile: cui`, no `audit_checkpoint_key` or no `audit_anchor_dir` | warn |
| A key is pinned (or the profile is on) but no checkpoint has been taken, or the newest is over 7 days old | warn |
| Otherwise | ok, naming the newest checkpoint, its age, and whether it is signed and anchored |

#### What each part protects against

| Part | Without it |
|---|---|
| The signature, with the private key in another account | Someone who can write the log could rewrite it, then write a checkpoint to match |
| The anchored copy, in a directory only the administrator can write | Deleting the local checkpoint file along with the newest records would leave nothing to compare |
| A short checkpoint interval | Records written since the newest checkpoint are covered by the chain alone |

Unsigned checkpoints (no key pinned) still catch accidental truncation and a
careless rewrite, but not someone who recomputes the chain and writes a
matching checkpoint.

### Also: `neuralmind team` and `onboarding` exit 1 when they fail

The `team` commands and `onboarding` work out their own exit code:
`team license activate` returns 1 when a license doesn't validate, `team seats
sync` returns 2 when it adds only some of a manifest's seats. But `neuralmind`
called each command and ignored what it returned. So
`neuralmind team license activate expired.json` printed
`License validation failed for expired.json: EXPIRED. Nothing was installed. …`
and exited 0, and so did every other `team` and `onboarding` failure. A
provisioning script under `set -e` carried on past a license that was never
installed. The CLI reference has said since v4.6.0 that a non-admin
`team governance remove-edge` exits 1; it never did. This is the same class of
bug v4.12.1 fixed in `doctor`: an exit code that was documented and tested
nowhere. Found on 2026-10-12 while activating an expired license.

- **A command's exit code reaches the shell.** When a command returns a
  non-zero integer, `neuralmind` now exits with it. Commands that call
  `sys.exit` themselves are unchanged, and a command that returns nothing
  still exits 0. All 81 subcommand handlers were checked: the five `team`
  command groups and `onboarding` return a code, and every other handler
  returns nothing, so no other command's exit status changes.

| Command | Now exits | When |
|---|---:|---|
| `team license activate FILE` | 1 | The file is missing, or it doesn't validate (`EXPIRED`, `INVALID`, …). Nothing is installed |
| `team governance …`, `team seats …`, `team audit …` | 1 | No usable license (a Team license file is missing, corrupted, or past its 30-day grace period), `--admin` isn't an admin, a seat limit, an unknown seat, or an invalid value |
| `team seats sync MANIFEST` | 1 | The manifest is missing, malformed, the wrong version, expired, or not signed by the issuer |
| `team seats sync MANIFEST` | 2 | Applied only in part: the license's seat limit refused some seats (listed under `failed` in its JSON report) |
| `team audit verify` | 1 | The audit log's hash chain is broken |
| `team self-hosted init` | 1 | The data dir is refused or can't be created |
| `onboarding` | 1 | The license agreement was declined, or the free license couldn't be written |

- **Still exit 0:** `team license status`, `team license portal`,
  `team self-hosted status` and `team self-hosted validate-license` report the
  license's state in their output whatever it is. To gate on the license
  itself, read the `status` field of `team license status`.
- **Tests:** `tests/test_cli_exit_codes.py` runs 15 failure cases and 2
  successes through the CLI's entry point, each in a throwaway config
  directory with its own signing key. All 15 failures exited 0 on v4.15.1.
- **Scripts and docs:** `scripts/e2e_team_tier.sh` (`set -euo pipefail`)
  added a second seat on the one-seat free license and carried on, because the
  refusal exited 0; it now requires that refusal to exit non-zero. The
  [CLI reference](../wiki/CLI-Reference.md#team-license-seats-audit-self-hosted)
  lists exit codes for `onboarding` and every `team` command, and its global
  table gains `seats sync`'s exit 2. The
  [Tier 2 operator guide](../wiki/Tier2-Operator-Guide.md) lists
  `team seats sync` and shows a provisioning script that stops on a refused
  license; the [team-memory governance walkthrough](../use-cases/govern-team-memory.md)
  alerts on a broken audit chain.

## What the agent actually sees

Without the profile, one thing changes: a `neuralmind team …` or
`neuralmind onboarding` command an agent runs as a shell command now exits 1
(2 for a partial `seats sync`) when it fails, with the same message as
before. Before, the tool call reported success while the output said
nothing was installed.

Under `profile: cui`:
- MCP tool calls behave as they already did with `identity: os` and
  `require_encrypted_storage: true`: a call from an account without a role, or
  from a disk that isn't verified encrypted, comes back as `security_denied`.
- Query results, hook output and tool schemas are unchanged.
- The difference is around the agent: the graph view and the daemon won't
  expose the project's index to the network, and the agent's documentation
  can't be sent for LLM seeding.

Audit checkpoints change nothing at the agent either. They are taken and
checked by an administrator, `doctor` and CI; the only new record in the log
is the `audit_checkpoint` event, and what the checkpoints protect is the
record of the agent's own MCP calls and hook events.

## Per-agent expectations

| Agent | What changes under `profile: cui` |
|---|---|
| Claude Code (hooks + MCP) | MCP calls attributed to the OS account and refused without a role; hooks refuse on an unverified disk (fail-open: they inject nothing and exit 0) |
| Cursor / Cline / Continue (MCP) | Same MCP behaviour; keep the server on stdio, since `identity: os` refuses the HTTP transport |
| Hermes-Agent plugin | Same hook behaviour as Claude Code |
| Generic MCP client | Same as Cursor |

Outside the profile, every agent sees only the `team` / `onboarding` exit
status above. No MCP tool or hook runs those commands.

## Upgrading

- **No change unless you set the profile**, except the `team` exit codes below.
- **`neuralmind team …` and `onboarding` can now exit non-zero.** A script
  that runs them under `set -e`, or reads their exit code, stops at a failure
  where it went on before. To keep going, append `|| true`. `team seats sync`
  exits 2 on a partial sync; if that's acceptable, allow it explicitly:
  `neuralmind team seats sync manifest.json --admin you@example.com || [ $? -eq 2 ]`.
- **If you already set `identity: os` and `require_encrypted_storage: true`:**
  replace them with `profile: cui`, or keep them alongside it, since they agree
  with it.
- **Check the profile:** run `neuralmind doctor .` and look at the Security
  profile line.
- **No change unless you take a checkpoint.** `audit verify` behaves as before
  until a checkpoint exists, and then adds a line about it.
- **Scripts that parse `audit verify --json`** get a new `checkpoints` object;
  the existing keys are unchanged.
- **A CUI project** (`security.profile: cui`) also gets a `doctor` Audit checkpoints
  warning until the key and anchor directory are set. Follow step 5 of the
  [CUI enclave walkthrough](../use-cases/cmmc-cui-enclave.md#5-what-an-assessor-can-look-at).
- **If a script runs `neuralmind serve --host 0.0.0.0` for a CUI project,**
  it now exits 1. Use an SSH tunnel to `127.0.0.1` instead.

## Not in this release

The last SP 800-171 item is live syslog forwarding, with an alert when audit
logging fails (AU.L2-3.3.4, 3.3.5). The project log's checkpoints don't cover
the Tier-2 team audit log yet.

See [NIST.md §3](../compliance/NIST.md#3-whats-next).

## Reproduce

```bash
pytest tests/test_security_profile.py -v
pytest tests/test_cli_exit_codes.py -k serve-refused -v
pytest tests/test_cli_exit_codes.py -k team_exit -v   # the team / onboarding rows

printf 'security:\n  profile: cui\n' > neuralmind-backend.yaml
neuralmind serve . --host 0.0.0.0; echo "exit $?"   # serve refused … exit 1
neuralmind doctor .                                  # Security profile line

pytest tests/test_audit_checkpoint.py -v

# In a project whose audit log has a few records (any build or query writes one):
printf 'security:\n  audit_checkpoint_key: %s\n' "$(neuralmind audit keygen /tmp/ck.pem | tail -1 | awk '{print $2}')" > neuralmind-backend.yaml
neuralmind audit checkpoint . --key /tmp/ck.pem
head -n -3 .neuralmind/audit_events.jsonl > /tmp/short && cp /tmp/short .neuralmind/audit_events.jsonl
neuralmind audit verify .; echo "exit $?"     # … removed from the end … exit 1
```

## Related

- [Use NeuralMind in a CMMC CUI enclave](../use-cases/cmmc-cui-enclave.md): the walkthrough, rewritten around the profile
- [Compliance Summary: CMMC 2.0](../COMPLIANCE-SUMMARY.md#cmmc-20--practice-evidence): AC.L2-3.1.1, AC.L2-3.1.20, CM.L2-3.4.7, SC.L2-3.13.8 (new row) and SC.L2-3.13.11
- [NIST: what applies, where it stands, what's next](../compliance/NIST.md)
- [Security settings reference](../wiki/CLI-Reference.md#security-settings-security-in-neuralmind-backendyaml)
- [Security Guide: In transit](../SECURITY-GUIDE.md#in-transit)
- [CLI reference: `team` exit codes](../wiki/CLI-Reference.md#team-license-seats-audit-self-hosted)
- [CLI reference: audit verify, keygen, checkpoint](../wiki/CLI-Reference.md#audit-verify)
- [Security Guide: Checkpoints](../SECURITY-GUIDE.md#checkpoints-v4160)
- [Compliance Summary: CMMC 2.0](../COMPLIANCE-SUMMARY.md#cmmc-20--practice-evidence): AU.L2-3.3.8
- [Risk assessment](../compliance/RISK_ASSESSMENT.md): R-07
