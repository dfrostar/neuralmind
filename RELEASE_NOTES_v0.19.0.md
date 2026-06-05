# NeuralMind v0.19.0 — one-command MCP setup (Claude Code / Cursor / Cline / Claude Desktop)

**Release Date:** June 2026

## TL;DR

The static code graph is commoditizing; NeuralMind's durable edge is the
**learned synapse layer** plus **MCP distribution** — being the memory an agent
reaches for. v0.19.0 makes that distribution frictionless:

```bash
neuralmind install-mcp --all      # detect installed agents and register with each
```

One command auto-detects which MCP clients are installed — **Claude Code,
Cursor, Cline, Claude Desktop** — and merges a NeuralMind entry into each
client's config, without clobbering anything else you've configured.

## What the agent actually sees, post-install

After `install-mcp`, the agent's MCP client lists NeuralMind's tools (`wakeup`,
`query`, `search`, `skeleton`, `build`, `stats`, …) and can call them directly —
so an agent **onboards onto your codebase through NeuralMind** instead of
grepping cold. Every client reads the same `{"mcpServers": {...}}` shape; they
just keep it in different files, which the command knows:

| Client | Scope | Config file |
|--------|-------|-------------|
| Claude Code | project | `.mcp.json` |
| Cursor | project | `.cursor/mcp.json` |
| Claude Desktop | user | the app's `claude_desktop_config.json` |
| Cline | user | the VS Code extension's `cline_mcp_settings.json` |

```bash
neuralmind install-mcp                      # Claude Code (project .mcp.json), the default
neuralmind install-mcp --client cursor      # a specific client
neuralmind install-mcp --all                # every detected client
neuralmind install-mcp --print              # just print the snippet to paste by hand
```

### Per-agent expectations

| Agent | What changes in v0.19.0 |
|-------|--------------------------|
| **Claude Code** | `neuralmind install-mcp` writes `.mcp.json`; the agent gains NeuralMind's MCP tools. |
| **Cursor / Cline** | One command registers the server in the right config; restart to pick it up. |
| **Claude Desktop** | User-scoped registration via the platform config path. |
| **Contributors / CI** | Pure-stdlib `mcp_install` module with merge/detect tests. |

## How it works

`neuralmind/mcp_install.py` is pure standard library (json + pathlib):

- **Auto-detection.** A client is "detected" when its config file exists, or —
  for the user-scoped apps — when the app's config directory is present.
- **Non-destructive merge.** Your other MCP servers are preserved; re-running is
  idempotent (`already-present`), and a changed entry is updated in place.
- **The launch spec is trivial** — `{"command": "neuralmind-mcp"}` — because the
  MCP tools take a `project_path` argument per call, so there's nothing
  machine-specific to bake in.

## Why this matters — the moat

Research (and the competitive landscape) is clear: AST-derived code graphs are
becoming table stakes. What a static graph *can't* copy is **usage memory** —
NeuralMind's Hebbian synapse layer, which learns what you actually edit
together. The self-benchmark already measures that learned uplift directly
(Phase 3 — synapse-recall A/B: top-k hit rate **71.7% → 83.3%, +11.7 points**
with recall on, token-budget-neutral). v0.19.0 invests in the *other* half of
the moat — **distribution**: the easier NeuralMind is to plug into every agent,
the more usage it sees, the more it learns.

## Honest scope & caveats

- **It writes client config; it doesn't install the clients.** `--all` registers
  with agents that are already present.
- **User-scoped clients (Claude Desktop, Cline) are per-machine**; project-scoped
  ones (Claude Code, Cursor) write into the repo, so committing `.mcp.json` /
  `.cursor/mcp.json` shares the setup with your team.
- **Restart the client** to pick up a newly-registered server.

## What ships

- **`neuralmind/mcp_install.py`** — detect + non-destructive merge for four MCP
  clients (pure stdlib).
- **`neuralmind install-mcp`** CLI — `--client`, `--all`, `--print`.
- 11 stdlib tests (merge idempotency, other-server preservation, path
  resolution, detection with a fake HOME).

## What's next

- **E1.5 onboarding-lift eval** — formalise the cold-agent-plus-committed-team-
  baseline vs cold-agent-alone measurement (the self-benchmark's synapse A/B is
  the foundation) as the headline differentiator.

## Upgrade

```bash
pip install --upgrade neuralmind
neuralmind install-mcp --all
```

No migration, no behavior change to existing installs; `install-mcp` only writes
the MCP client config you point it at.
