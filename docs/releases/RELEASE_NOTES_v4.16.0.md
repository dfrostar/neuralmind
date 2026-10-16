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

### Also: a `Decision:` trailer can be retracted, and goes STALE with its code

Each prompt (Claude Code's `UserPromptSubmit` hook, the Hermes plugin's
`pre_llm_call`) gets the `Decision:` git trailers whose subjects it mentions.
A trailer is committed history, so it couldn't be changed: a decision that was
later reversed kept arriving with every matching prompt, for as long as its
commit stayed in the last 300, and nothing could retract it. The decision
store (`neuralmind decisions`) had ACTIVE, STALE and INVALIDATED, but the
prompt hooks never read it.

- **`neuralmind decisions scan` imports trailers into the decision store.**
  The post-commit hook from `neuralmind init-hook` runs it after every commit
  in a project with a decision store and, in a built project without one, on
  the first commit that carries a trailer (a `git log` + `grep` check, so
  other commits start no Python). Each trailer in the same 300 commits is
  recorded once, tagged `trailer`, anchored to its commit, naming the files
  its commit changed (diffed against the first parent, as the scan diffs
  HEAD). It is judged against the code its own commit stored, not your
  working tree: one whose files changed after its commit comes in STALE,
  with the files named; the rest come in ACTIVE. Its id is derived from the
  rationale, so a rebase that rewrites the commit keeps the same decision,
  and amending the trailer's commit, or committing the same rationale again,
  re-anchors it to the new commit instead of marking it STALE. `--json` gains
  an `imported` list.
- **The prompt hooks and `neuralmind why` read the store's status.** An
  INVALIDATED trailer is left out. A STALE one is still shown, marked
  `[STALE: its code changed after this was decided; check it still holds]`.
  A trailer the store doesn't hold is shown as before. The hooks only read
  the store; they never create one.
- **So a trailer has the same lifecycle as a recorded decision:**
  `decisions invalidate <id> --reason R` retracts it, a later commit that
  changes its files marks it STALE, `decisions restore <id>` brings it back,
  and the `PreToolUse` stale-decision guard names it before an edit. Find the
  id with `neuralmind decisions query <words> --status ALL`, which now prints
  each decision's `ID:` (without `--status`, query lists only ACTIVE
  decisions). Importing again never revives an invalidated trailer.
- **The status is local to your clone.** It lives in `.neuralmind/memory.db`,
  which isn't committed: a teammate, a fresh clone or CI still gets a trailer
  you invalidated, and STALE follows the commits made in this working tree,
  whatever the branch.
- **Windows: non-ASCII rationales and paths are read correctly.** git's
  output was decoded with the locale encoding (cp1252 on Windows), which
  garbled a non-ASCII `Decision:` rationale, and with it the id derived from
  it, and garbled non-ASCII paths, so a decision naming such a file never went
  STALE, imported or recorded. Both are now read as UTF-8, which is what git
  writes; Linux and macOS, whose locale is UTF-8, see no change.
- **Tests:** `tests/memory/test_trailer_lifecycle.py` drives a real git
  repository through import, invalidate, a later commit, restore and `why`;
  `tests/test_provenance.py` covers the status rules.

## What the agent actually sees

Without the profile, two things change:
- A `neuralmind team …` or `neuralmind onboarding` command an agent runs as a
  shell command now exits 1 (2 for a partial `seats sync`) when it fails, with
  the same message as before. Before, the tool call reported success while the
  output said nothing was installed.
- The `## NeuralMind decision provenance` block a prompt gets leaves out the
  trailers you invalidated and marks the STALE ones:

```
## NeuralMind decision provenance

- `upload_with_retry`: keeps retries in the uploader, not the HTTP client. (see commit 3f9c2ab) [STALE: its code changed after this was decided; check it still holds]
```

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

Outside the profile, every agent sees the `team` / `onboarding` exit status
above (no MCP tool or hook runs those commands), and Claude Code and the
Hermes plugin see the decision lifecycle in each prompt's decision block.
Cursor, Cline, Continue and generic MCP clients get no decision block from
NeuralMind's hooks, so nothing changes for them there.

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
- **If a script runs `neuralmind serve --host 0.0.0.0` for a CUI project,**
  it now exits 1. Use an SSH tunnel to `127.0.0.1` instead.
- **`neuralmind decisions scan` creates `.neuralmind/memory.db` in a project
  whose recent commits carry `Decision:` trailers,** where it used to skip a
  project without a store. A project with neither is still left alone, and
  `NEURALMIND_DECISION_SCAN=0` still skips the scan, imports included. Run
  `neuralmind decisions scan .` once to import the trailers already in your
  history.
- **Re-run `neuralmind init-hook .`** to get the new post-commit hook. A hook
  installed before v4.16.0 runs the scan only where a decision store already
  exists, so in a project without one, new trailers wait until you run
  `neuralmind decisions scan .` yourself.

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
pytest tests/test_cli_exit_codes.py -k team_exit -v   # the team / onboarding rows
pytest tests/memory/test_trailer_lifecycle.py tests/test_provenance.py -v   # trailer lifecycle

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
- [CLI reference: `team` exit codes](../wiki/CLI-Reference.md#team-license-seats-audit-self-hosted)
