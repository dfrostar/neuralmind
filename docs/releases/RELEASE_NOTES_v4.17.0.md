# NeuralMind v4.17.0 — signed, anchored audit checkpoints: an audit log you can't silently shorten

**Type:** Minor release | **Theme:** NIST SP 800-171 / CMMC Level 2 hardening, part 2. The audit log's newest records can no longer be removed, or its chain recomputed, without `audit verify` failing

The audit log, `.neuralmind/audit_events.jsonl`, is hash-chained. `neuralmind
audit verify` catches a record changed or removed in the middle of the log, but
the chain has no secret. Anyone who can write the file could:
- delete the newest records, leaving a shorter chain that still verifies;
- edit any record and recompute every hash after it.

Until now the only answer was "forward the log to your SIEM". CMMC AU.L2-3.3.8
asks that audit information be protected from unauthorized modification and
deletion, and [docs/compliance/NIST.md](../compliance/NIST.md) listed checkpoints
as the next SP 800-171 item. This release ships them.

---

## What changed

### `neuralmind audit keygen`

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

### `neuralmind audit checkpoint`

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

### `neuralmind audit verify` checks the checkpoints

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

### `neuralmind doctor` gets an **Audit checkpoints** line

| Finding | Result |
|---|---|
| A checkpoint shows truncation, a rewrite or a bad signature | fail |
| Under `security.profile: cui`, no `audit_checkpoint_key` or no `audit_anchor_dir` | warn |
| A key is pinned (or the profile is on) but no checkpoint has been taken, or the newest is over 7 days old | warn |
| Otherwise | ok, naming the newest checkpoint, its age, and whether it is signed and anchored |

## What each part protects against

| Part | Without it |
|---|---|
| The signature, with the private key in another account | Someone who can write the log could rewrite it, then write a checkpoint to match |
| The anchored copy, in a directory only the administrator can write | Deleting the local checkpoint file along with the newest records would leave nothing to compare |
| A short checkpoint interval | Records written since the newest checkpoint are covered by the chain alone |

Unsigned checkpoints (no key pinned) still catch accidental truncation and a
careless rewrite, but not someone who recomputes the chain and writes a
matching checkpoint.

## What the agent actually sees

Nothing changes for an agent. Checkpoints are taken and checked by an
administrator, `doctor` and CI; MCP tools, hooks and query results are
unchanged. The only new record in the log is the `audit_checkpoint` event.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | Nothing at the agent; its MCP calls and hook events are what the checkpoints protect |
| Cursor / Cline / Continue (MCP) | Same |
| Hermes-Agent plugin | Same |
| Generic MCP client | Same |

## Upgrading

- **No change unless you take a checkpoint.** `audit verify` behaves as before
  until a checkpoint exists, and then adds a line about it.
- **Scripts that parse `audit verify --json`** get a new `checkpoints` object;
  the existing keys are unchanged.
- **A CUI project** (`security.profile: cui`) gets a `doctor` warning until the
  key and anchor directory are set. Follow step 5 of the
  [CUI enclave walkthrough](../use-cases/cmmc-cui-enclave.md#5-what-an-assessor-can-look-at).

## Not in this release

The last SP 800-171 item is live syslog forwarding, with an alert when audit
logging fails (AU.L2-3.3.4, 3.3.5). The project log's checkpoints don't cover
the Tier-2 team audit log yet. See [NIST.md §3](../compliance/NIST.md#3-whats-next).

## Reproduce

```bash
pytest tests/test_audit_checkpoint.py -v

# In a project whose audit log has a few records (any build or query writes one):
printf 'security:\n  audit_checkpoint_key: %s\n' "$(neuralmind audit keygen /tmp/ck.pem | tail -1 | awk '{print $2}')" > neuralmind-backend.yaml
neuralmind audit checkpoint . --key /tmp/ck.pem
head -n -3 .neuralmind/audit_events.jsonl > /tmp/short && cp /tmp/short .neuralmind/audit_events.jsonl
neuralmind audit verify .; echo "exit $?"     # … removed from the end … exit 1
```

## Related

- [CLI reference: audit verify, keygen, checkpoint](../wiki/CLI-Reference.md#audit-verify)
- [Security Guide: Checkpoints](../SECURITY-GUIDE.md#checkpoints-v4170)
- [Compliance Summary: CMMC 2.0](../COMPLIANCE-SUMMARY.md#cmmc-20--practice-evidence): AU.L2-3.3.8
- [Risk assessment](../compliance/RISK_ASSESSMENT.md): R-07
- [Use NeuralMind in a CMMC CUI enclave](../use-cases/cmmc-cui-enclave.md)
