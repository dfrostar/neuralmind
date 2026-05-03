# NeuralMind v0.5.0 — MCP server bundled by default

**Release Date:** May 3, 2026

## TL;DR

`pip install neuralmind` now includes the MCP server out of the box.
You no longer need `[mcp]`, `[all]`, or any other extra to run
`neuralmind-mcp` against Claude Desktop, Claude Code, Cursor, Cline,
Continue, Hermes-Agent, OpenClaw, or any other MCP-compatible client.

Old `pip install "neuralmind[mcp]"` commands still work — the extra
is preserved as an empty no-op. No breaking changes.

## What changed

### The "Connection closed" footgun is gone

For everyone who hit this — installed NeuralMind, wired up an MCP
host, and got a cryptic "Connection closed" or "Server failed to
start" error within five seconds — the cause was always the same:
`neuralmind-mcp` was crashing on `import mcp` because the SDK lived
behind an optional extra that the README Quick Start never mentioned.

Shipping a binary entry point (`neuralmind-mcp`) that immediately
exits on import failure is a footgun by design. v0.5.0 fixes it at
the source. The `mcp>=1.23.0` package is now a hard dependency of
NeuralMind, not an opt-in extra.

### The tradeoff

CLI-only users now also pull in the MCP SDK (and its Pydantic stack)
on `pip install`. That's roughly 5MB of additional disk space. We
think this is the right call:

- Every MCP integration the project documents (six clients and
  counting) requires this dependency.
- The default install now matches the default expectation. Users who
  read "NeuralMind ships an MCP server" no longer have to discover
  that "ships" meant "ships, but not really, unless you knew to add
  `[mcp]`."
- The MCP SDK is small, pure-Python, and pulls cleanly across
  3.10/3.11/3.12. No native code, no platform gotchas.

### What stays the same

- `pip install "neuralmind[mcp]"` — still works. The `[mcp]` extra is
  preserved as an empty list in `pyproject.toml`, so existing install
  commands in your blog posts, READMEs, Dockerfiles, and CI configs
  resolve cleanly with no warnings.
- `pip install neuralmind[all]` — still works. The `[all]` extra
  resolves through `[mcp,dev]`; the empty `[mcp]` is a no-op, `[dev]`
  installs the dev tools.
- All public APIs, CLI commands, MCP tools, hooks, and on-disk state
  formats are unchanged from v0.4.0. This is purely a packaging change.

## Upgrading

```bash
pip install --upgrade neuralmind
```

That's the entire upgrade. If you previously installed with `[mcp]`,
the upgrade is a no-op (you already had `mcp` installed); the only
difference is that the package metadata now considers it a base
dependency rather than an extra.

If you were on v0.4.0 with the plain `pip install neuralmind` (no
extra) and were hitting the "Connection closed" error when wiring up
MCP, the upgrade fixes it transparently — no other changes needed.

## What's next

Follow-on work tracked as GitHub issues:

- **[#78](https://github.com/dfrostar/neuralmind/issues/78)** —
  Auto-launch `neuralmind watch` from the Claude Code `SessionStart`
  hook, so the synapse layer learns continuously without anyone
  having to start a daemon manually. Closes the "self-learning once
  installed" gap from the v0.4.0 release notes.
- **[#79](https://github.com/dfrostar/neuralmind/issues/79)** —
  Synapse weight import/export so a team can share a learned brain.
  Round-trippable JSON, schema-versioned, optional merge mode that
  averages weights across two graphs.
- **[#80](https://github.com/dfrostar/neuralmind/issues/80)** —
  Quality benchmark suite measuring retrieval recall@K, precision@K,
  and MRR with synapses on vs off. Runs in CI on PRs touching the
  synapse or selector code.
- **[#81](https://github.com/dfrostar/neuralmind/issues/81)** —
  One-time GitHub repo setting fix so release-please can finally
  open Release PRs automatically, instead of requiring a manual
  cut via the GitHub UI Releases form for every minor.

## Verification

End-to-end smoke against this release:

```bash
pip install neuralmind==0.5.0 graphifyy
cd /tmp && mkdir smoke && cd smoke && git init -q
graphify update . && neuralmind build .
neuralmind-mcp --help        # binary on PATH
python -c "import mcp; print(mcp.__version__)"   # SDK present
```

Expected: `neuralmind-mcp --help` prints usage; `import mcp` succeeds.
That's the full footgun-fix verification.

## Thanks

Special thanks to the Hermes-Agent and OpenClaw maintainers for the
v0.4.0 end-to-end verification work that surfaced the "Connection
closed" trap clearly enough to act on.
