# NeuralMind v4.19.0 — live audit forwarding to syslog, an alert when an audit record can't be written, SP 800-53: an OSCAL component definition and a hardening baseline that checks itself, and a demo that runs offline

**Type:** Minor release | **Theme:** NIST SP 800-171 / CMMC Level 2 hardening, the last audit item: AU.L2-3.3.4 (alert when audit logging fails) and AU.L2-3.3.5 (correlate audit records); and the SP 800-53 items: a machine-readable statement of NeuralMind's controls for an agency's System Security Plan, and a hardening baseline that `neuralmind hardening` checks

The audit log stayed on the host until someone ran `neuralmind audit export`.
A SIEM saw the records hours or days later, if at all, and a failed audit write
was noted only in `.neuralmind/`, where `neuralmind doctor` found it the next
time someone ran it. [docs/compliance/NIST.md](../compliance/NIST.md) listed
live forwarding, with an alert when audit logging fails, as the last SP 800-171
item. This release ships it.

---

## What changed

### `security.audit_syslog`: every record to syslog as it is written

Set it in `neuralmind-backend.yaml`:

```yaml
security:
  audit_syslog: /dev/log          # or udp://host[:port], tcp://host[:port]
  audit_syslog_facility: local0   # the default
```

- **Each record goes out right after it is written,** from the CLI, the MCP
  server, the hooks and the daemon alike. The message body is the record as
  JSON, `sha256` and `prev_sha256` included, so the SIEM can check the chain
  and correlate it with other systems' records (AU.L2-3.3.5).
- **Formats:** RFC 5424 over `udp://` and `tcp://` (octet-counted on TCP, so a
  record with newlines in it stays one message), timestamped with the record's
  own time; the traditional RFC 3164 form on a unix socket, which is what
  rsyslog, syslog-ng and journald read on `/dev/log`.
- **Severity follows the record:** `info` for an ordinary record, `warning`
  for a denied, refused or failed one, `err` for a gap record.
- **A record too big for one datagram** (8 KiB) is sent without its `details`
  and `target`, marked `truncated` with its original size. Its `sha256` still
  identifies it, and `audit export` still has the whole record. TCP and
  stream sockets send it whole.
- **Forwarding never blocks or fails the call.** It runs after the record is
  written and outside the log's lock, with a 2-second timeout. After a failed
  send, appends don't try again for 30 seconds, so a dead target doesn't add
  its timeout to every query and hook; `neuralmind audit forward` always tries.

### Delivery is tracked, not assumed

`.neuralmind/audit_forwarded.json` notes the last record sent. If the syslog
daemon is down, the records wait: each later append sends up to 200 of them,
and `neuralmind audit forward` sends the rest.

- **Across a rotation:** the progress note names its log by that log's first
  hash, which a rotation's rename doesn't change, so the archive's unsent tail
  goes out before the new log.
- **If the position is lost** (the log was replaced, or the archive holding it
  pruned), forwarding starts again from the oldest log still there, and says
  so with a `warning`-severity `audit_forward_restarted` message.
- **At least once:** after a failure part-way through a batch, some records
  may arrive twice. Deduplicate on `sha256`.
- **Turning it on for a project with history** sends the whole log, 200
  records per append; run `neuralmind audit forward` once to send it in one go.

### The AU.L2-3.3.4 alert

When an audit record can't be written (a full disk, an unwritable
`.neuralmind/`), NeuralMind sends an `alert`-severity `audit_write_failed`
message straight to syslog, naming the record and the error. It doesn't go
through the log, which is what failed, so it gets out when the local disk is
full. The failure is still noted in `.neuralmind/audit_write_failures.jsonl`
for `doctor` and `audit record-gap`, as in v4.18.0. Route `alert` to someone's
pager in your SIEM.

### Under `security.profile: cui`, the target must be on this machine

Audit records hold query text, which in a CUI enclave is CUI, and NeuralMind
doesn't encrypt the connection. So the profile refuses a target off this
machine: only a unix socket or a loopback address. `doctor` fails, nothing is
forwarded, and the fix is in the message:

```
security.profile: cui refuses security.audit_syslog tcp://siem.example:514: audit records can hold CUI and NeuralMind sends them unencrypted, so the target must be on this machine (/dev/log or a loopback address). Let the host's syslog daemon forward to the SIEM over TLS.
```

The host's syslog daemon then forwards over TLS, in the host's validated
cryptographic module. That keeps NeuralMind out of the cryptography part of an
assessment, as its other controls do. Outside the profile, a remote target is
accepted in plain text.

### `neuralmind audit forward`

```bash
neuralmind audit forward [project_path] [--json]
```

Sends every record not yet forwarded. Exits `0` when none is left, `1` when
`security.audit_syslog` isn't set or is refused, or when the target can't be
reached (the records stay waiting). `--json` prints `target`, `sent`,
`backlog`, `restarted` and `error`.

### `neuralmind doctor` gets an **Audit forwarding** line

| Finding | Result |
|---|---|
| `security.audit_syslog` malformed, or off this machine under the profile | fail |
| Records waiting to be sent (with the last error, if the last attempt failed) | warn |
| Under `security.profile: cui`, no `security.audit_syslog` | warn |
| Everything sent | ok, naming the target and the last send |
| Not configured, outside the profile | ok |

### Forwarded copies are a data location

Forwarded records are copies NeuralMind can't delete. `neuralmind
data-locations` lists them as *audit records forwarded to syslog*, outside the
project, once any have been sent, and the
[data deletion procedure](../compliance/DATA_DELETION.md) says to delete them
in the syslog daemon's files and the SIEM.

### An OSCAL component definition for SP 800-53

An agency that installs NeuralMind inside an authorized system has to say, in
its System Security Plan, how each SP 800-53 control is met, including by the
software it runs. Until now that meant reading the compliance docs and
retyping them.

[`security/neuralmind.oscal-component-definition.json`](https://github.com/dfrostar/neuralmind/blob/main/security/neuralmind.oscal-component-definition.json)
is an [OSCAL](https://pages.nist.gov/OSCAL/) 1.1.3 component definition: one
`software` component and the 21 SP 800-53 Rev. 5 controls it touches.

- **The controls:** AC-3, AC-6, IA-2, AU-2, AU-3, AU-4(1), AU-5, AU-6(3), AU-8,
  AU-9, AU-9(2), AU-9(3), AU-12, CM-6, CM-7, SC-8, SC-13, SC-28, SI-2, SI-7, SR-4.
- **Each requirement** says what NeuralMind provides in its `description`, and
  what stays yours in `remarks` ("Customer responsibility: …"). It names both
  roles: no control is met by NeuralMind alone.
- **GRC tools read it** straight into an SSP. Compliance Trestle loads it as
  is; the [readable version](../compliance/SP800-53.md) is the same content as
  a customer responsibility matrix.
- **It can't drift.** CI validates it against the OSCAL schema, checks every
  control ID against the Rev. 5 catalog, and checks that every setting and
  command it names exists and that its provider matches the commercial terms.
  release-please bumps its version with the package's.

### An SP 800-53 hardening baseline, and `neuralmind hardening` to check it

The component definition says what NeuralMind does for each control; an
assessor also asks how it is configured (CM-6), and wants evidence rather than
a screenshot of a YAML file. The
[hardening guide](../compliance/SP800-53-HARDENING.md) is that configuration:
17 rules, `NMH-01` to `NMH-17`, each mapped to the controls it supports.

| Area | Rules |
|---|---|
| Configuration | The `cui` profile on, set by the machine policy; identity from the OS account; no role beyond `reader` by default; settings file and `.neuralmind/` writable by their owner only |
| Host | Encrypted storage verified and required; the OS FIPS mode on; checkpoint signing in a FIPS-mode OpenSSL; no daemon beyond loopback or without its token |
| Audit | The hash chain verifies; no unrecorded write failure; checkpoints signed, anchored and under a week old; forwarding to a local syslog with nothing waiting |

```bash
neuralmind hardening [project_path] [--json]
```

- **Every rule is checked**, against what NeuralMind enforces (machine policy
  included) and what it can see of the host. A rule that can't be checked
  fails. Exits `0` when every rule passes, `1` when any fails; `--json` gives
  each rule's controls, status, detail and fix, to keep as evidence.
- **NMH-09 is new ground:** it asks the `cryptography` package whether the
  OpenSSL that signs checkpoints runs in FIPS mode. The prebuilt wheel's
  bundled OpenSSL doesn't, so on a FIPS host the rule fails until
  `cryptography` is rebuilt against the system OpenSSL, which the
  [NIST page](../compliance/NIST.md) has recommended since v4.16.0.
- **What it can't see** (clock sync, the syslog daemon's TLS, Windows ACLs)
  the guide lists as checked by you.
- **The component definition gains CM-6** (21 controls), naming the baseline
  and the command. CI checks that the guide lists exactly the rules and
  controls the code checks.

### `neuralmind demo` runs offline, straight after `pip install`

`neuralmind demo` asks three questions of a small sample project bundled with
the package. Its graph was bundled already, but its first run built the vector
index, which downloaded the embedding model (about 90 MB) into `~/.cache`, and
offline it failed with a traceback.

- **The sample's vector index ships in the package** (about 0.5 MB, in
  `neuralmind/demo_data/prebuilt/`), so the build finds every node already
  embedded.
- **So do the embeddings of the three questions,** made with the same model.
  When the model isn't on disk, the demo embeds its questions from those: the
  ranking is the model's, and nothing is downloaded. It says so in one line.
  The same run with the model on disk prints the same token counts.
- **A bundle this install can't use** (a turbovec release too old to read the
  index rebuilds it, which needs every node embedded) falls back to building
  with the model, downloading it once, as before. Offline, that ends in a
  message, not a traceback.
- **It can't drift.** `scripts/build_demo_index.py` regenerates the bundle; in
  CI, the self-benchmark job rebuilds it with the real model and fails if the
  committed copy is stale: changed nodes, changed question vectors, an index
  this turbovec can't read, or different top-5 results for the demo questions.
  Unit tests, which need no model, fail if the sample project would need
  anything embedded or the index doesn't load.

Your own code still needs the model: the first `neuralmind build` downloads it
once, as before. A new [`demo`](../wiki/CLI-Reference.md#demo) section in the
CLI reference documents the command.

## What the agent actually sees

Nothing changes for an agent. Forwarding runs after each audit record is
written and never fails the call; a dead target costs at most one 2-second
timeout every 30 seconds. MCP tools, hooks and query results are unchanged. What the agent does
now reaches your SIEM as it happens instead of at the next export.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | Nothing at the agent; its MCP calls and hook events are forwarded as they are recorded |
| Cursor / Cline / Continue (MCP) | Same |
| Hermes-Agent plugin | Same |
| Generic MCP client | Same |

## Upgrading

- **No change unless you set `security.audit_syslog`.** Without it nothing is
  sent and no new file is written.
- **A CUI project** gets a `doctor` warning until forwarding is set up. Point
  it at `/dev/log` and configure the host's syslog daemon to forward to the
  SIEM over TLS; step 5 of the
  [CUI enclave walkthrough](../use-cases/cmmc-cui-enclave.md#5-what-an-assessor-can-look-at)
  shows an rsyslog example.
- **Existing history** is sent too; run `neuralmind audit forward` once after
  turning it on.
- **Keep exporting.** Forwarding is how the SIEM sees records live; an
  `audit export` copy is still what you would restore the log from.
- **In an authorized system,** run `neuralmind hardening` on each host after
  upgrading and on a schedule; record any rule you deviate from in the SSP.

## Not in this release

The SP 800-171 audit items and the SP 800-53 items on the roadmap are done:
nothing is scheduled in [NIST.md §3](../compliance/NIST.md#3-whats-next). The
Tier-2 team audit log isn't forwarded, and `hardening` doesn't emit OSCAL
assessment results yet.

## Reproduce

```bash
pytest tests/test_audit_forward.py -v
pytest tests/test_cli_exit_codes.py -k audit-forward -v

# In a project whose audit log has a few records (any build or query writes one),
# a listener on this machine prints the first record forwarded to it:
python -c 'import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("127.0.0.1", 5514)); print(s.recv(65536).decode())' &
printf 'security:\n  audit_syslog: udp://127.0.0.1:5514\n' > neuralmind-backend.yaml
neuralmind audit forward .        # ✓ Forwarded N record(s) to udp://127.0.0.1:5514; none waiting.
neuralmind doctor .               # Audit forwarding: … nothing waiting

# The hardening baseline; a developer machine fails most rules, which is the point:
pytest tests/test_hardening.py -v
neuralmind hardening . ; echo "exit $?"

# The demo, offline, from a fresh install (no model on disk, no network):
pip install neuralmind && neuralmind demo
pytest tests/test_cli.py -k "TestCLIDemo" -v
```

## Related

- [CLI reference: audit forward](../wiki/CLI-Reference.md#audit-forward)
- [Security Guide: Forwarding to syslog](../SECURITY-GUIDE.md#forwarding-to-syslog-v4190)
- [Compliance Summary: CMMC 2.0](../COMPLIANCE-SUMMARY.md#cmmc-20--practice-evidence): AU.L2-3.3.4, AU.L2-3.3.5
- [NIST: what applies, where it stands, what's next](../compliance/NIST.md)
- [Use NeuralMind in a CMMC CUI enclave](../use-cases/cmmc-cui-enclave.md)
- [SP 800-53 hardening guide](../compliance/SP800-53-HARDENING.md) and [CLI reference: hardening](../wiki/CLI-Reference.md#hardening-v4190)
- [SP 800-53 controls and what stays yours](../compliance/SP800-53.md), and the [OSCAL component definition](https://github.com/dfrostar/neuralmind/blob/main/security/neuralmind.oscal-component-definition.json)
