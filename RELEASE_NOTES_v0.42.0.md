# NeuralMind v0.42.0 — One-command setup: `neuralmind quickstart`

**TL;DR:** Setup collapses from four commands to one. `neuralmind quickstart`
builds the index, registers the MCP server with every detected agent, installs
the Claude Code compression hooks, and runs `doctor` to prove the result —
with a numbered, step-by-step report of exactly what it did. Paired with a
docs pass that makes `uvx neuralmind` the zero-install try-it path.

```bash
pip install neuralmind
neuralmind quickstart .        # that's the whole setup
```

## What it does

Four steps, in order, each reported as it runs:

```
NeuralMind quickstart — /path/to/your-project

[1/4] Building the index
  ✓ 135 nodes, 14 communities (17.1s)

[2/4] Registering the MCP server with detected agents
  ✓ claude-code: installed → /path/to/your-project/.mcp.json

[3/4] Installing Claude Code compression hooks
  ✓ hooks installed at /path/to/your-project/.claude/settings.json

[4/4] Verifying the setup
  [ ok ] Code graph: 135 nodes …
  [ ok ] Semantic index: 135 nodes embedded (turbovec backend)
  [ ok ] MCP server: MCP SDK importable (neuralmind-mcp ready)
  [ ok ] Claude Code hooks: installed (project)

Quickstart complete. Restart your agent to pick up the MCP server —
it boots with NeuralMind's wakeup context and learns as you work.
```

Failure semantics are deliberate: only the **build** is fatal (nothing
downstream works without an index). MCP registration and hook installation
are per-agent conveniences — a failure there is reported and quickstart
carries on, and the closing `doctor` pass is the single source of truth for
what actually got set up. Its verdict is quickstart's exit code.

## Flags

| Flag | Effect |
|---|---|
| `--force` | Full index rebuild instead of incremental |
| `--global-hooks` | Claude Code hooks in `~/.claude/settings.json` instead of the project |
| `--skip-build` / `--skip-mcp` / `--skip-hooks` | Opt out of individual steps (the doctor pass always runs) |

Every step remains available as its own command (`build`, `install-mcp`,
`install-hooks`, `doctor`) — quickstart chains them, it doesn't replace them.

## What the agent actually sees post-install

After `quickstart` and a client restart, the agent's world has changed in
three ways — without the agent doing anything:

1. **MCP tools are live** — `neuralmind_wakeup`, `neuralmind_query`,
   `neuralmind_search`, `neuralmind_skeleton`, `neuralmind_feedback`,
   `neuralmind_review` are callable.
2. **Claude Code sessions boot warm** — the SessionStart hook injects the
   wakeup context, and `SYNAPSE_MEMORY.md` carries learned associations
   into every new session.
3. **Tool output shrinks silently** — the PostToolUse hooks compress
   `Read`/`Bash`/`Grep` results 88–91% before the model reads them, and the
   `edit-activity` hook feeds reuse signal back into the synapse layer.

### Per-agent expectations

| Agent | MCP registration | Hooks | What quickstart delivers |
|---|---|---|---|
| **Claude Code** | `.mcp.json` (project) | ✅ PostToolUse + SessionStart | The full package: tools + warm boot + compression + reuse feedback |
| **Cursor** | `.cursor/mcp.json` | — | MCP tools (wakeup/query/search/…); no hook layer, so no output compression |
| **Cline** | app settings file | — | MCP tools |
| **Generic MCP client** | via `install-mcp --print` snippet | — | MCP tools |

Hooks are a Claude Code mechanism; on other agents quickstart's hook step
simply doesn't apply (skip it with `--skip-hooks` to silence the step).
Client detection is best-effort — when nothing is detected, quickstart
points at `neuralmind install-mcp --print` for a paste-anywhere snippet.

## Zero-install: `uvx neuralmind`

The docs now lead with the ephemeral path — try NeuralMind on any repo
without installing anything permanent:

```bash
uvx neuralmind build .                     # index a repo, zero footprint
uvx neuralmind query . "how does auth work?"
uvx neuralmind quickstart .                # full setup from a cold machine
```

`uvx` (and `pipx run`) resolve prebuilt wheels on Linux, macOS arm64, and
Windows x64, so there is no compile step. See
[install paths](docs/use-cases/install-paths.md) for the trade-offs.

## Honest scope

- `quickstart` is a **convenience layer** — it chains four existing,
  individually-tested commands and adds no new capability.
- Hook installation is Claude-Code-specific by nature; other agents get the
  MCP server only.
- MCP client detection covers Claude Code, Cursor, Cline, Claude Desktop,
  and VS Code; anything else needs the `--print` snippet once.

## Upgrade

```bash
pip install -U neuralmind
neuralmind quickstart .        # idempotent: re-registers, re-verifies
```

Existing setups don't need to re-run anything — quickstart is for new
projects and fresh machines, and it's safe to run on a configured project
(steps report `already-present` instead of duplicating).
