# Tips & Tricks: Hermes pairing

**Audience:** anyone running NeuralMind with [Hermes Agent](https://github.com/NousResearch/hermes-agent)
**Applies to:** v4.21.0+ (the doctor Wiring section and `install-mcp --client hermes`); the rest from v4.9.0

NeuralMind pairs with Hermes in two ways. The **plugin**
(`neuralmind install-hermes-plugin`) adds related files, the code linked to
them, and recorded decisions to every Hermes turn, and the last session's
recap to a session's first, with no tool call. The **MCP entry**
(`neuralmind install-mcp --client hermes`) gives the agent NeuralMind's tools
(`neuralmind_query`, `neuralmind_search` and the rest) to call when it needs
the code itself. Either one connects Hermes to the index; the plugin is the
one that works without the model deciding to ask. The setup is in the
README's [Pairing: Hermes Agent via uv](https://github.com/dfrostar/neuralmind#pairing-hermes-agent-via-uv)
and the [Hermes walkthrough](../use-cases/hermes-agent.md).

## Verify the wiring

An index that nothing calls looks healthy: the graph and the vectors are fine,
so every core check passes. Check what's connected:

```bash
neuralmind daemon status       # "running (pid …, v…)", or "not running" with exit 3
neuralmind doctor .            # Wiring first: daemon, Git hooks, Hermes plugin, MCP per client
neuralmind benchmark .         # context per query against the measured size of your indexed code
neuralmind savings . --cost    # what the logged queries saved, priced for your model
```

- **`doctor`** prints a Wiring section before the other checks. Each line is
  `ok` or `warn`, never `fail`, and a warning carries the command that fixes
  it. When no agent host is wired (no Claude Code hooks, no enabled Hermes
  plugin, no MCP registration) its last line says *Installed but not wired*.
  It also warns when the plugin's copied code or the running daemon is older
  than the installed NeuralMind. `--json` puts the same lines under
  `wiring.checks`, and `wiring.state` (`inert`, `partial` or `wired`) for a
  script to gate on. The exit code still depends on the core checks only.
- **`benchmark`** measures how much context a query returns, not whether the
  right code was in it. For that, `neuralmind probe .` queries a sample of your
  indexed symbols and lists the ones it didn't find.
- **`savings`** counts queries logged by the CLI and the MCP tools. The
  plugin's per-turn recall isn't logged as a query, so a Hermes setup that uses
  only the plugin shows few or none here, however much recall it serves.
- In Hermes: `hermes plugins list` shows whether `neuralmind` is enabled, and
  `hermes mcp test neuralmind` checks the MCP entry. The plugin writes to
  Hermes's log only when it can't run NeuralMind, or NeuralMind is too old or
  times out: `hermes logs --level WARNING`.

## Which project a turn belongs to

The plugin serves the first of these that has been built
(`.neuralmind/build_status.json` exists), and does nothing if none has:

1. `NEURALMIND_PROJECT`, in the Hermes process's environment;
2. the project saved at install: `neuralmind install-hermes-plugin <path>`
   pins one, and a re-run without a path keeps it (`--unpin` clears it);
3. Hermes's terminal working directory, `TERMINAL_CWD`;
4. only when `TERMINAL_CWD` isn't set, the directory the Hermes process runs in.

A pin applies to every Hermes session that uses that Hermes home, in any
directory: each one is served and recorded as the pinned project. For several
projects, install without a path. `TERMINAL_CWD` matches the terminal CLI and
a standalone gateway; Hermes Desktop, ACP editor sessions and per-session
workspaces keep each session's directory where the plugin can't read it, so
with those, pin a project or set `NEURALMIND_PROJECT`. `doctor` warns when the
plugin is pinned to a different project from the one you're checking. More in
[Multi-Project Scoping](Multi-Project-Scoping.md).

The MCP tools take the project as an argument on each call, so the MCP entry
has no project of its own.

## Upgrading

```bash
uv tool upgrade neuralmind
neuralmind install-hermes-plugin   # the plugin is a copy: re-run to update it (keeps an earlier pin)
neuralmind daemon restart          # the running daemon keeps the old code until restarted
```

- The plugin runs NeuralMind through the interpreter recorded at install, so
  per-turn recall uses the upgraded package at once. Its own shim is a copy,
  updated by the re-run; for a plugin Hermes installed from a clone, run
  `hermes plugins update neuralmind` instead. `doctor` flags a copy from an
  older release.
- **A running MCP server keeps the code it started with** until its host
  restarts it. In Hermes, `/reload-mcp` restarts the MCP servers (and
  invalidates the provider's prompt cache, so the next message re-sends the
  whole prefix); restarting Hermes, and the gateway if one runs, does too.
  `doctor` can't see a running MCP server's version.
- Re-run `neuralmind doctor .` afterwards.

## Switches

Set these in the environment Hermes runs in; the plugin passes its environment
to each NeuralMind call.

| Variable | Default | Effect |
|----------|---------|--------|
| `NEURALMIND_BYPASS` | unset | `1` switches off every hook action, the plugin's included: no context added, nothing recorded |
| `NEURALMIND_SYNAPSE_INJECT` | `1` | `0` leaves the recall (related files, linked code, decisions) out of each turn |
| `NEURALMIND_SESSION_RECAP` | `1` | `0` stops recording prompts and edited files, and the first-turn recap |
| `NEURALMIND_HERMES_TIMEOUT` | `8` | Seconds each call to NeuralMind may take before the turn goes ahead without its context. A session's first turn makes two calls (recap, then recall), so keep twice this below Hermes's `plugins.hook_callback_timeout` (default 30 s) |
| `NEURALMIND_AUTO_INTENT_BOOST` | unset | `1` re-weights `query` results by the intent detected from the question's wording. Off by default: on the [retrieval eval](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/on-v4.12/report.md) it lost 3 questions and won none. It affects `query` (CLI and the MCP tool), not the plugin's per-turn recall |

The full list is in the [CLI Reference](CLI-Reference.md#environment-variables).

## Compliance: the same code path on either host

Each Hermes turn runs `neuralmind _hook <action>`, the entry point Claude
Code's hooks run, with the same payload, so the same code and the same
controls apply whichever agent is the host. A project with
`security.require_encrypted_storage` gets no hook writes until its volume is
verified. The audit records those processes write go to the same SHA-256
hash-chained log, which `neuralmind audit verify` checks, and the
[SP 800-53 hardening baseline](../compliance/SP800-53-HARDENING.md) that
`neuralmind hardening` checks covers the project and its host, not the agent.
What each control covers, and what stays yours, is in
[SP 800-53](../compliance/SP800-53.md).
