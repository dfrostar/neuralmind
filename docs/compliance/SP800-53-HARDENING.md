# NIST SP 800-53 hardening guide

**Date:** 2026-10-20
**Version:** 1.0
**Check it:** `neuralmind hardening [project_path] [--json]` *(v4.19.0+)*

---

## 1. What this is

[SP800-53.md](SP800-53.md) says which SP 800-53 Rev. 5 controls NeuralMind
touches and what stays yours. This page is the configuration that goes with
it: 17 rules, each tied to the controls it supports, that together put
NeuralMind in its hardened state on one host. It is your CM-6 baseline for
NeuralMind; adopt it as is, or record each deviation in your System Security
Plan.

Every rule is checked automatically. `neuralmind hardening` reads the settings
as NeuralMind enforces them (the machine policy included), the volume and the
OS FIPS mode, the audit log and its checkpoints, forwarding, and the running
daemon, and reports each rule:

```
$ neuralmind hardening /srv/app
NeuralMind SP 800-53 hardening baseline — /srv/app
============================================================
  [pass] NMH-01 The hardened profile is on (CM-6, CM-7, SC-8)
         security.profile: cui
  ...
  [FAIL] NMH-09 Checkpoint signing runs in a FIPS-mode OpenSSL (SC-13, AU-9(3))
         checkpoint signing runs in OpenSSL 3.5.4 without FIPS mode; ...
         -> pip install --force-reinstall --no-cache-dir --no-binary cryptography cryptography, ...
============================================================
16 of 17 rule(s) pass; 1 fail.
```

- **Exit codes:** `0` when every rule passes (or doesn't apply on this
  platform: the permission rules on Windows, the OS FIPS mode on macOS),
  `1` when any fails.
- **A rule that can't be checked fails.** An OS FIPS mode that can't be
  read, or a volume whose encryption can't be verified, is not a pass.
- **`--json`** prints the baseline name, the NeuralMind version, the project,
  pass/fail counts and each rule's `id`, `title`, `controls` (OSCAL control
  IDs such as `au-9.3`), `status` (`pass`, `fail`, `n/a`), `detail` and `fix`.
  Keep it as assessment evidence.
- **Run it as the account that runs NeuralMind,** on each host, on a schedule
  (CA-7), and after each upgrade. It reads and writes nothing in the project.

`neuralmind doctor` already reports most of these, as warnings sized for a
developer. `hardening` is the stricter baseline for an authorized system:
every rule here must pass.

## 2. The baseline

| Rule | Title | Controls | How to meet it |
|---|---|---|---|
| **NMH-01** | The hardened profile is on | CM-6, CM-7, SC-8 | `security.profile: cui`. It forces `identity: os` and encrypted storage, refuses listeners beyond loopback or without their token, and refuses LLM documentation seeding. The name comes from CMMC; it is the hardened posture for any authorized system, CUI or not |
| **NMH-02** | The machine policy sets it | CM-5, CM-6 | The profile in `/etc/neuralmind/policy.yaml` (`C:\ProgramData\NeuralMind\policy.yaml`), owned by root and writable only by root. Otherwise whoever owns the project directory can delete the project file and switch it off |
| **NMH-03** | Identity comes from the OS account | IA-2, AC-3 | `security.identity: os` (the profile sets it), and a valid `security.roles` and `rate_limit` if you set them |
| **NMH-04** | No role beyond reader by default | AC-6 | Leave `security.default_role` unset, or set it to `reader`; name each account that needs more in `security.users` |
| **NMH-05** | The project's settings file is writable by its owner only | AC-3, CM-5 | `chmod go-w neuralmind-backend.yaml`, since it holds `security.users`. `n/a` on Windows: restrict it with an ACL |
| **NMH-06** | The state directory is writable by its owner only | AU-9 | `chmod go-w .neuralmind`: it holds the audit log. `n/a` on Windows: restrict it with an ACL |
| **NMH-07** | Encrypted storage is verified and required | SC-28 | FileVault, BitLocker or LUKS on every volume holding the project's state (the project, `.neuralmind/` through a symlink, and a configured `db_path`), verified by NeuralMind as at run time, and `security.require_encrypted_storage: true` (the profile sets it) |
| **NMH-08** | The OS FIPS mode is on | SC-13 | `fips-mode-setup --enable` (RHEL), the FIPS policy on Windows. `n/a` on macOS, which has no FIPS mode switch to read |
| **NMH-09** | Checkpoint signing runs in a FIPS-mode OpenSSL | SC-13, AU-9(3) | Rebuild `cryptography` against the system OpenSSL: `pip install --force-reinstall --no-cache-dir --no-binary cryptography cryptography`. The prebuilt wheel bundles its own OpenSSL, which isn't FIPS-validated |
| **NMH-10** | No daemon serves beyond loopback or without its token | CM-7, SC-8 | `neuralmind daemon restart` on 127.0.0.1 with its token; reach it from elsewhere through an SSH tunnel. A daemon discovery file that can't be read fails, since it may describe a running daemon |
| **NMH-11** | The audit log's hash chain verifies | AU-9 | Nothing to set: a failure means the log was changed. Investigate with `neuralmind audit verify` |
| **NMH-12** | No audit write failure is unrecorded | AU-5 | Fix the cause, then `neuralmind audit record-gap` |
| **NMH-13** | Checkpoints are signed and verify | AU-9, AU-9(3) | `neuralmind audit keygen` in an administrator account, and its public key in `security.audit_checkpoint_key` |
| **NMH-14** | Checkpoints are anchored outside the project | AU-9(2) | `security.audit_anchor_dir`: an existing directory outside the project, not writable by group or others (on POSIX), that only the administrator can write, ideally on another system |
| **NMH-15** | The newest checkpoint is under a week old | AU-9 | `neuralmind audit checkpoint` daily, from the key owner's account (cron, a systemd timer, Task Scheduler) |
| **NMH-16** | Audit records are forwarded to a local syslog | AU-4(1), AU-6(3), SC-8 | `security.audit_syslog: /dev/log` (or a loopback address), with the host's syslog daemon forwarding to the SIEM over TLS |
| **NMH-17** | No audit record is waiting to be forwarded | AU-4(1), AU-5 | A reachable syslog daemon; `neuralmind audit forward` sends a backlog |

## 3. Setting it up

On a Linux host, as root, then as the administrator who holds the checkpoint
key. The [CUI enclave walkthrough](../use-cases/cmmc-cui-enclave.md) has the
same steps with more on each, and Windows equivalents.

```bash
# NMH-01, NMH-02: the profile, machine-wide
sudo mkdir -p /etc/neuralmind
printf 'security:\n  profile: cui\n' | sudo tee /etc/neuralmind/policy.yaml
sudo chmod 755 /etc/neuralmind && sudo chmod 644 /etc/neuralmind/policy.yaml

# NMH-08: the OS FIPS mode (RHEL 9; reboot after)
sudo fips-mode-setup --enable

# NMH-09: checkpoint signing in the system OpenSSL
pip install --force-reinstall --no-cache-dir --no-binary cryptography cryptography

# NMH-13, NMH-14: the checkpoint key and the anchor directory (administrator)
neuralmind audit keygen /home/admin/.neuralmind/audit-key.pem   # prints the public key
sudo install -d -o admin -m 755 /var/lib/neuralmind-anchor
```

The project file, writable by its owner only (NMH-05):

```yaml
# neuralmind-backend.yaml
security:
  profile: cui
  users:
    alice: builder
    bob: reader
  audit_checkpoint_key: MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE...   # from audit keygen
  audit_anchor_dir: /var/lib/neuralmind-anchor
  audit_syslog: /dev/log
```

Then point the host's syslog daemon at the SIEM over TLS (the rsyslog example
is in the [security guide](../SECURITY-GUIDE.md#forwarding-to-syslog-v4190)),
schedule `neuralmind audit checkpoint /srv/app --key
/home/admin/.neuralmind/audit-key.pem` daily from the administrator's account,
and run `neuralmind hardening /srv/app`.

## 4. Checked by you

These are part of the hardened state, and NeuralMind can't see them, so
`hardening` doesn't check them:

| Control | What to check |
|---|---|
| AU-8 | The host clock is synchronized to an authoritative time source; audit timestamps come from it |
| AU-5, AU-6(3) | Your syslog daemon routes the `alert` severity to a person, and the SIEM receives NeuralMind's records |
| SC-8 | The syslog daemon's connection to the SIEM uses TLS, in the host's validated module |
| AU-9(3) | The checkpoint's private key is readable only by the administrator's account, not a developer's |
| SI-7, SR-4 | The release you installed was verified: its signature and build-provenance attestations ([SSDF.md §2](SSDF.md)) |
| SC-13 | On macOS, that the FileVault and corecrypto version in use is covered by Apple's CMVP certificates (NMH-08 reports `n/a` there) |
| AC-3, AU-9 | On Windows, the ACLs on the machine policy, `neuralmind-backend.yaml` and `.neuralmind/` (NMH-05 and NMH-06 report `n/a` there) |
| AU-11 | `audit export` copies are kept for your retention period: they are what you would restore the log from |

## Related

- [SP 800-53 controls and what stays yours](SP800-53.md), and the [OSCAL component definition](https://github.com/dfrostar/neuralmind/blob/main/security/neuralmind.oscal-component-definition.json)
- [NIST: what applies, where it stands, what's next](NIST.md)
- [Security guide](../SECURITY-GUIDE.md)
- [CLI reference: hardening](../wiki/CLI-Reference.md#hardening-v4190)
- [Use NeuralMind in a CMMC CUI enclave](../use-cases/cmmc-cui-enclave.md)
