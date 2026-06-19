# awesome-mcp-servers entry

A directory PR to the `awesome-mcp-servers` list (and any equivalent curated MCP
directories). Maker-submitted; these lists welcome maker submissions as long as
the entry is accurate and in the right category.

## The entry line

Place under the code/developer-tools (or "Knowledge & Memory") category,
alphabetically if the list is sorted:

```markdown
- [NeuralMind](https://github.com/dfrostar/neuralmind) 🐍 🏠 - Local semantic code-memory for AI agents: progressive context disclosure (40–70× fewer tokens on code questions) plus a Hebbian "synapse" layer that learns code associations from your usage. 100% on-device, no API key. Ships a reproducible public benchmark.
```

Legend reminder (use whatever symbols the target list defines):
- 🐍 Python
- 🏠 local / self-hosted
- (add the list's "open-source" / language marks as appropriate)

## PR title

```
Add NeuralMind — local semantic code-memory MCP server
```

## PR description

```
Adds NeuralMind, an open-source, 100%-local MCP server that gives AI coding
agents semantic memory of a codebase.

What it does:
- Progressive context disclosure (L0–L3) — assembles a compact structured
  context (project map → relevant symbols → call edges) instead of pasting files
  or dumping raw RAG chunks. ~40–70× fewer tokens on code questions.
- A Hebbian "synapse" layer that learns which code goes with what from how you
  actually use the codebase, and decays unused links.
- Runs on-device; the index needs no API key.

Why it belongs on the list: it's a working MCP server (tools for any MCP client —
Claude Code, Cursor, Cline, Continue), open-source, and ships a reproducible
public benchmark (cost + correctness reported together, gold-file recall with an
objective def-site oracle, no LLM judge):
https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md

Disclosure: I'm the author. Entry follows the list's format/category
conventions; happy to adjust placement or wording.
```
