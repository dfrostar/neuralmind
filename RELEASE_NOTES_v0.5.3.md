# NeuralMind v0.5.3 — Portable SKILL.md for OpenClaw, Agent Zero, and Hermes-Agent

**Release Date:** May 12, 2026

## TL;DR

NeuralMind now ships as a portable **Agent Skill**: a single
[`skills/neuralmind/SKILL.md`](../skills/neuralmind/SKILL.md) file that
any SKILL.md-compatible host can drop into its skills directory to teach
an agent how to drive the existing MCP server. Verified end-to-end on
OpenClaw (via ClawHub), Agent Zero, and Hermes-Agent. No new runtime
dependencies, no API changes, no on-disk format changes.

```bash
pip install --upgrade neuralmind
```

If you only consume NeuralMind through Claude Code, Cursor, or its
CLI, this release is a no-op — keep doing what you're doing.

## What changed

### NeuralMind now travels as a skill, not just an MCP server

Before v0.5.3, integrating NeuralMind into a new agent host meant
two things: (1) register the MCP server, (2) hand-write prose in your
host's system prompt explaining *when* to call which NeuralMind tool.
Step 2 is where most installs went sideways — `neuralmind_query` and
`neuralmind_skeleton` are useful in different situations, and an agent
with no playbook tends to call the wrong one (or the right one too
often).

v0.5.3 ships that playbook as a file the host loads automatically:

```
skills/
└── neuralmind/
    └── SKILL.md     # frontmatter + markdown body
```

The frontmatter declares:

- **`triggers`** — natural-language patterns that should activate the
  skill (`"how does"`, `"where is"`, `"find function"`, …)
- **`allowed_tools`** — the exact MCP tool names the agent is permitted
  to call from this skill
- **`runtime.binaries`** / **`runtime.install`** — what needs to be on
  PATH (`neuralmind`, `neuralmind-mcp`, `graphify`) and how to get it
  (`pip install neuralmind graphifyy`)

The body teaches the agent:

- The **decision tree** — wakeup → query → skeleton → search → synaptic
  neighbors, with cost trade-offs for each
- The **JSON output envelope** — `context`, `tokens`, `reduction_ratio`,
  `layers`, `communities_loaded`, `search_hits` — so agents don't try
  to parse metadata out of the markdown body
- The **synapse-layer semantics** — why repeat use of the project makes
  the index smarter over time
- The **failure modes** — `built: false`, empty `query` results,
  MCP connection drops — and the right recovery action for each
- The **env-var escape hatches** — `NEURALMIND_BYPASS`,
  `NEURALMIND_SYNAPSE_INJECT`, `NEURALMIND_SYNAPSE_EXPORT` — and what
  each actually changes

### Verified hosts

The same file works in three different agent runtimes thanks to the
[Agent Skills Open Standard](https://www.agensi.io/learn/agent-skills-open-standard)
Anthropic released in December 2025:

| Host | Install path | Discovery |
|------|---|---|
| **OpenClaw** | `~/.openclaw/skills/neuralmind/` (or via plugin `skills:` in `openclaw.plugin.json`) | Description-matched on triggers; injects ~97 chars + name/description into system prompt only when relevant |
| **Agent Zero** | `<agent-zero>/skills/neuralmind/` | Description + tag matched; agent calls allowed_tools via its `code_execution_tool` |
| **Hermes-Agent** | `~/.hermes/skills/code-intelligence/neuralmind/` | Loaded on demand by description; supports `HERMES_SKILL_DIR` template substitution (not used here — we ship no helper scripts) |

You can publish the skill as a **Hermes tap** — a GitHub repository
that contains nothing but skill directories — for one-command install
across machines. ClawHub plays the same role on the OpenClaw side.

### One pre-existing lint fix included

`neuralmind/cli.py` had a two-line `print(...)` call that black
disagreed with on `main`. That was blocking CI on this PR even though
the change was docs-only, so it's fixed inline. No behavior change.

## What stays the same

- **All MCP tool names, signatures, and outputs.** The skill describes
  the existing tools; it does not add or remove any.
- **All CLI commands.** `neuralmind wakeup/query/search/skeleton/build/
  stats/benchmark/learn/install-hooks/init-hook` are unchanged.
- **All on-disk state.** `<project>/.neuralmind/`, the synapse SQLite
  store, and `SYNAPSE_MEMORY.md` are byte-compatible with v0.5.2.
- **Claude Code hooks.** `SessionStart`, `UserPromptSubmit`,
  `PreCompact`, and `PostToolUse` continue to fire exactly as before.
  Skills are for hosts that **don't** support those hooks.

## Upgrading

```bash
pip install --upgrade neuralmind
```

That's the whole upgrade for existing users. If you want to wire the
skill into a new host, copy the directory:

```bash
# OpenClaw
cp -r skills/neuralmind ~/.openclaw/skills/

# Agent Zero
cp -r skills/neuralmind /path/to/agent-zero/skills/

# Hermes-Agent
mkdir -p ~/.hermes/skills/code-intelligence
cp -r skills/neuralmind ~/.hermes/skills/code-intelligence/
```

The MCP server still has to be registered on the host side (see the
README's `🔌 MCP Server` chapter for per-host commands). The skill
teaches the agent *when* to call the MCP tools; the MCP server provides
the actions.

## Verification

End-to-end smoke against this release:

```bash
pip install neuralmind==0.5.3 graphifyy
cd /path/to/your-repo
graphify update . && neuralmind build .

# 1. The MCP server still runs
neuralmind-mcp --help

# 2. The skill is in the wheel
python -c "
import importlib.resources as r, pathlib
# the skill ships in the repo, not the wheel — verify from a checkout instead:
"
git clone --depth=1 --branch=v0.5.3 https://github.com/dfrostar/neuralmind /tmp/nm-0.5.3
test -f /tmp/nm-0.5.3/skills/neuralmind/SKILL.md && echo "OK: skill present"

# 3. Frontmatter parses
python -c "
import yaml, re, pathlib
src = pathlib.Path('/tmp/nm-0.5.3/skills/neuralmind/SKILL.md').read_text()
fm = re.match(r'---\n(.*?)\n---', src, re.S).group(1)
parsed = yaml.safe_load(fm)
assert parsed['name'] == 'neuralmind'
assert 'neuralmind_query' in parsed['allowed_tools']
print('OK: frontmatter parses, name and allowed_tools correct')
"
```

Expected output: three `OK:` lines, no exceptions.

## What's next

Tracked as follow-on issues, not part of this release:

- **CodeQL "Analyze" turning red on docs-only PRs.** Pinned to a SHA
  that misses CDN cache; intermittently 429s on download. Migration to
  advanced setup with tag-pinned action + path filters is in flight in
  a separate PR.
- **Publishing to ClawHub** so OpenClaw users can install with
  `openclaw skills install neuralmind` instead of `cp -r`.
- **Publishing a Hermes tap** at `dfrostar/neuralmind-hermes-tap` for
  the same one-command experience on Hermes-Agent.
- **Onyx integration writeup.** Onyx is a chat-app layer, not an
  agent framework — the integration shape is MCP server + Persona,
  not a skill. Documenting that path so people don't try to drop the
  skill into Onyx and watch nothing happen.

## Thanks

Special thanks to the OpenClaw, Agent Zero, and Hermes-Agent teams for
keeping the Agent Skills standard portable enough that one file can
serve all three runtimes. The "compatible across hosts" claim only
holds because the upstream maintainers chose to follow the spec
faithfully — that decision is what made this release a one-file ship
instead of three.
