# NeuralMind v4.17.2 — a misspelled encryption setting in the machine policy holds every project to the strictest settings

**Type:** Patch release | **Theme:** the machine policy fails closed on every invalid value, as v4.17.1 said it did

v4.17.1's machine policy (`/etc/neuralmind/policy.yaml`) holds every project to
the strictest settings when it can't be trusted, including when it "holds an
invalid value". One kind of invalid value slipped through. A
`require_encrypted_storage` that is neither true nor false, such as `flase`, a
blank value, or `2`, was read the way a project file reads it: as on. The
encryption check switched on, but the CUI profile and OS identity didn't, so a
machine meant to be locked down by a broken policy wasn't.

Nothing got looser than the policy's author wrote. A misspelling still turned
the encryption check on, and each setting still took the stricter of the
machine's and the project's value. What was missing was the rest of "strictest".

Codex found it reviewing the v4.17.1 fix that added invalid values to the
strictest rule (#674), after that fix had merged.

---

## What changed

A machine policy whose `require_encrypted_storage` isn't `true` or `false` (or
`yes`/`no`, `on`/`off`, `1`/`0`) now holds every project to the strictest
settings, as for an invalid `identity` or `profile`. `neuralmind doctor` fails
its *Security policy* check with the reason:

```
  [FAIL] Security policy: MCP calls are refused: machine policy /etc/neuralmind/policy.yaml is invalid: security.require_encrypted_storage must be true or false, not 'flase'
```

A project's `neuralmind-backend.yaml` is unchanged: a misspelled
`require_encrypted_storage` there still counts as on.

## What the agent actually sees

Nothing, unless the machine policy holds a misspelled
`require_encrypted_storage`. Then every MCP call on that machine is refused
(`reason: identity`, as for any untrusted machine policy) until the
administrator fixes the file.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | Refused under a machine policy with a misspelled `require_encrypted_storage`; otherwise nothing |
| Cursor / Cline / Continue (MCP) | As Claude Code |
| Hermes-Agent plugin | As Claude Code |
| Generic MCP client | As Claude Code |

## Upgrading

Run `neuralmind doctor .` on each machine with a machine policy. A *Security
policy* failure naming `require_encrypted_storage` means the file needs
`true` or `false` there.

## Reproduce

```bash
pytest tests/test_machine_policy.py -v -k "malformed or spelling_out"
```

## Related

- [v4.17.1 release notes](RELEASE_NOTES_v4.17.1.md): the machine policy
- [Security guide: the machine policy](../SECURITY-GUIDE.md#the-machine-policy)
- [CUI enclave walkthrough](../use-cases/cmmc-cui-enclave.md)
