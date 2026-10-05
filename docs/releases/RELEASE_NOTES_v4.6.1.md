# NeuralMind v4.6.1 — the MCP server applies your security settings

**Type:** Patch release | **Theme:** MCP access control

`security.roles` and `security.rate_limit` in `neuralmind-backend.yaml` now
apply to the MCP server. Through v4.6.0 the server built its security manager
without reading that file, so every call got the default role policy and a
limit of 60 calls a minute, whatever the YAML said. A caller could declare
`admin` and reach every tool, even in a project whose policy left `admin` out,
as the [Security Guide](../SECURITY-GUIDE.md#capping-what-a-caller-can-claim)
recommends.

If your project has no `security:` block in `neuralmind-backend.yaml`, nothing
changes: no NeuralMind command writes one, and the defaults are the same as in
v4.6.0.

## What changed

- **`security.roles` replaces the default policy.** Each role gets exactly the
  tools listed for it (or `"*"` for all of them), and a role the policy doesn't
  list gets none. Callers still declare their own role, so leaving `admin` out
  of the policy is what caps what any caller can reach. A refused call returns
  `code: "security_denied"` with `reason: "rbac"`.
- **`security.rate_limit` sets the limiter** (`max_calls` per
  `window_seconds`, default 60 per 60). It still counts per declared actor, so
  it stops a runaway agent, not a caller that changes its actor name. A call
  over the limit returns `reason: "rate_limit"`. Every denial is written to
  `.neuralmind/audit_events.jsonl`, with its reason.
- **A policy that is empty or malformed fails closed.** `roles: {}` grants
  nothing, instead of falling back to the defaults. If the `security:`
  section, `roles` or `rate_limit` isn't a mapping, or a limit isn't a whole
  number (or `window_seconds` is under 1), the server refuses every MCP call
  with `code: "security_denied"`, `reason: "config"`, and an error naming the
  setting, instead of guessing at a looser policy. A role whose value is
  neither a list nor `"*"` gets no tools. `rate_limit: null` means the
  defaults.
- **The docs describe it as working.** `SECURITY.md`, the Security Guide, the
  Deployment Guide, the FAQ and risk R-03 had warned that these settings were
  ignored; they now show how to use them. The v4.5.1 release notes said a
  `security.roles` policy replaced the defaults; through the MCP server it
  didn't until this release.

Example, from the Security Guide:

```yaml
# neuralmind-backend.yaml, in the project root
security:
  roles:
    builder: [neuralmind_wakeup, neuralmind_query, neuralmind_search, neuralmind_skeleton, neuralmind_build]
    reader: [neuralmind_wakeup, neuralmind_query, neuralmind_search, neuralmind_skeleton]
  rate_limit:
    max_calls: 60
    window_seconds: 60
```

## What the agent actually sees post-install

Only in a project whose `neuralmind-backend.yaml` has a `security:` block.
Without one, every agent sees exactly what it saw in v4.6.0.

| Agent | Before | After |
|---|---|---|
| **Claude Code** (MCP + hooks) | Every MCP tool the default policy grants, whatever `security.roles` said; 60 calls a minute | Only the tools `security.roles` grants the role it calls with (`builder` when it names none); a tool outside that returns `security_denied` with `reason: "rbac"`, and every tool returns `reason: "config"` while the `security:` section is malformed. Hooks don't go through the MCP server and are unaffected |
| **Cursor / Cline / Continue** (MCP) | Same as Claude Code | Same as Claude Code |
| **Generic MCP client** | `role: "admin"` reached every tool | `role: "admin"` reaches only what the policy grants `admin`; nothing, if the policy doesn't list it |

## Upgrade notes

- `pip install -U neuralmind`. No rebuild needed.
- **If your `neuralmind-backend.yaml` sets `security.roles`, check it before
  upgrading.** It now takes effect, and it replaces the defaults rather than
  adding to them:
  - An agent that names no role is `builder`. If the policy doesn't list
    `builder`, that agent gets no tools at all.
  - A tool you don't list for a role is denied to that role, including tools
    the default policy granted, such as `neuralmind_memory_search`,
    `neuralmind_memory_timeline` and `neuralmind_memory_get`. The default
    policy is `DEFAULT_ROLE_POLICY` in `neuralmind/mcp_security.py`; copy from
    it.
- **If it sets `security.rate_limit`,** that limit now applies instead of 60
  calls a minute.
- **If every MCP call comes back with `reason: "config"`,** the `security:`
  section is malformed; the error names the setting to fix. v4.6.0 ignored the
  section, so a mistake in it went unnoticed until now.
- To get v4.6.0's behaviour back, delete the `security:` block.

## Related

- [Security Guide: capping what a caller can claim](../SECURITY-GUIDE.md#capping-what-a-caller-can-claim) ·
  [access control](../SECURITY-GUIDE.md#access-control)
- [Deployment Guide](../DEPLOYMENT-GUIDE.md) · [FAQ](../wiki/FAQ.md)
- Previous release: [v4.6.0](RELEASE_NOTES_v4.6.0.md)
