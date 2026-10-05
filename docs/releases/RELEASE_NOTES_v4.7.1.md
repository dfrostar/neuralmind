# NeuralMind v4.7.1 — policy mistakes that meant the defaults now refuse

**Type:** Patch release | **Theme:** MCP access control

[v4.6.1](RELEASE_NOTES_v4.6.1.md) made the MCP server apply `security.roles`
and `security.rate_limit`, and refuse a `security:` value of the wrong type
with `reason: config`. Its release notes also listed two mistakes it still read
as "no policy", which applies the default policy. That policy gives `admin`
every tool, and any caller can declare `admin` unless
[`identity: os`](RELEASE_NOTES_v4.7.0.md) is set. v4.7.1 refuses both.

If `neuralmind-backend.yaml` has no `security:` section, nothing changes.

## What changed

- **A policy file that doesn't parse is refused** when its text, outside
  comments, names a security setting: `security`, `roles`, `rate_limit`,
  `identity` or `require_encrypted_storage`. Every MCP call returns
  `code: "security_denied"`, `reason: "config"`, and an error quoting the parse
  failure. v4.7.0 did this only for files naming `identity` or
  `require_encrypted_storage`, and counted a mention in a comment. Other
  unparseable files still read as empty, so a typo in backend tuning doesn't
  block the server.
- **A `security:` or `roles:` key left empty is refused.** YAML reads a key
  with nothing under it as `null`, which is what's left when every entry under
  it is commented out. The error says what to write instead: `roles: {}` to
  grant nothing, or no key at all to use the defaults. An empty `rate_limit:`
  still means the default limit, and a missing key still means the defaults.
- **`neuralmind doctor` reports it.** The *Security policy* check fails on any
  role-policy problem that makes the server refuse every call: these two, and
  the wrong-type values v4.6.1 already refused.

A misspelled key, such as `role:` for `roles:`, is still read as absent. After
writing a policy, call a tool you left out with `role: "admin"` and check that
it returns `security_denied`.

## What the agent actually sees post-install

Only in a project whose `neuralmind-backend.yaml` has one of these mistakes.
Every other project sees exactly what it saw in v4.7.0.

| Agent | Before | After |
|---|---|---|
| **Claude Code** (MCP + hooks) | The default policy: a call declaring `admin` reached every tool | Every MCP tool returns `security_denied` with `reason: "config"` and the setting to fix. Hooks don't go through the MCP role policy and are unaffected |
| **Cursor / Cline / Continue** (MCP) | Same as Claude Code | Same as Claude Code |
| **Generic MCP client** | Same as Claude Code | Same as Claude Code |

## Upgrade notes

- `pip install -U neuralmind`. No rebuild needed.
- If `neuralmind-backend.yaml` has a `security:` section, run
  `neuralmind doctor` before upgrading the MCP server. A failed
  *Security policy* check names the setting to fix.
- The server reads the policy once per process, so after fixing it, restart
  the MCP server (a new agent session, or reconnecting the server).

## Related

- [Security Guide: capping what a caller can claim](../SECURITY-GUIDE.md#capping-what-a-caller-can-claim)
- [Security settings reference](../wiki/CLI-Reference.md)
- Previous release: [v4.7.0](RELEASE_NOTES_v4.7.0.md)
