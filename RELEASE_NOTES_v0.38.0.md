# NeuralMind v0.38.0 — VS Code extension, hybrid search, explicit feedback, and CI auto-index

**Release Date:** June 2026

## What's in this release

v0.38.0 ships four changes: a **native VS Code extension** that closes the adoption gap for
non-Cline VS Code users, plus three retrieval-quality improvements that directly address gaps
vs. LlamaIndex and mem0. None of the retrieval changes touch the existing token-reduction
machinery — the Hebbian synapse layer, progressive disclosure, and team memory are unchanged.

| Change | What | Where |
|---|---|---|
| **VS Code extension** | Status bar, command palette, graph panel, hover cards — zero MCP config needed | `editors/vscode/` |
| **BM25 hybrid search** | RRF merge of vector + keyword results for code-exact queries | `neuralmind/bm25.py`, `neuralmind/context_selector.py`, `neuralmind/embedder.py` |
| **`neuralmind_feedback` MCP tool** | Explicit positive/negative signal to reinforce or soften synapse weights | `neuralmind/mcp_server.py`, `neuralmind/synapses.py` |
| **CI auto-index GitHub Action** | Auto-build the index and commit team memory on every push to main | `.github/workflows/neuralmind-autoindex.yml` |

---

## BM25 hybrid search — what the agent actually sees

### The problem

Pure vector search treats "UserService" as a semantic concept rather than an
exact identifier. When an agent asks "how does UserService authenticate users?",
vector search may rank semantically similar nodes — `AuthHandler`, `LoginService`,
`TokenValidator` — above the exact class node `UserService`. For code retrieval,
**textual identity matters**, and keyword search has always won here.

LlamaIndex's code-specific chunking addresses this at the chunking layer; NeuralMind
addresses it at the **retrieval layer**, where it can be applied after embedding
without rebuilding the index format.

### What changed

A new `BM25Index` (`neuralmind/bm25.py`) runs alongside the vector store:
- **Code-aware tokenisation:** `UserService` → `["user", "service"]`,
  `get_auth_token` → `["get", "auth", "token"]`, `auth.py` → `["auth", "py"]`.
  CamelCase, snake_case, dots, and hyphens are all split so identifier fragments
  match query fragments exactly.
- **Standard BM25 scoring** (k1=1.5, b=0.75 — the Atire formulation), with
  IDF computed at build time.
- **Persisted as JSON** in `<project>/.neuralmind/bm25_index.json` alongside
  the vector index so daemon restarts and MCP reconnects see a warm index without
  re-building. Built automatically at the end of every `neuralmind build`.

### What the agent sees differently

Results are merged via **Reciprocal Rank Fusion** (RRF, k=60 — the de-facto
standard):

```
rrf_score(node) = 1/(60 + rank_vec) + 1/(60 + rank_bm25)
```

This means a node that ranks well in *both* lists gets a strong combined score,
while a node that only ranks in one list gets approximately half the weight.
The merge is **budget-neutral**: the output length equals the vector-only result
count. No extra tokens are spent.

**Before v0.38.0** — query "UserService authentication":
```
1. AuthHandler (score: 0.87)
2. LoginService (score: 0.81)
3. UserService (score: 0.78)    ← ranked third by semantics
4. TokenValidator (score: 0.72)
```

**After v0.38.0** — same query, hybrid:
```
1. UserService (rrf: 0.97)     ← ranked first: top of BM25 AND top-3 of vector
2. AuthHandler (rrf: 0.82)
3. LoginService (rrf: 0.76)
4. TokenValidator (rrf: 0.61)
```

### Synapse co-activation applies on top

The existing synapse re-ranking (Hebbian co-activation boost) still applies
after RRF merging. Learned associations continue to nudge results the agent
has historically needed together, regardless of whether they ranked high in
vector search, keyword search, or both.

### How to control it

```bash
NEURALMIND_BM25=0 neuralmind query . "UserService authentication"
# disables keyword layer — pure vector search, identical to v0.37 and earlier
```

The kill switch follows the same `!= "0"` pattern as `NEURALMIND_SYNAPSE_INJECT`
— anything other than the literal string `"0"` leaves hybrid search on.

---

## `neuralmind_feedback` — closing the explicit feedback loop

### The problem

mem0 leads on persistent memory because it exposes **explicit signal**: the agent
(or user) can say "that was useful" or "that was wrong" and the memory adjusts
immediately. NeuralMind's implicit Hebbian signal (co-activation from co-editing)
is strong for long-term pattern learning but has a one-session lag. Explicit
feedback can correct bad results *now*, not at the next build.

### What changed

A new MCP tool `neuralmind_feedback` accepts explicit positive or negative signal
on a retrieved node:

```json
{
  "name": "neuralmind_feedback",
  "signal": "positive",
  "node_id": "auth_handlers.py::UserService",
  "context_node_ids": ["auth_handlers.py", "token_validator.py::validate_token"]
}
```

**Positive signal** (`signal="positive"`, requires `context_node_ids`):
- Calls `store.reinforce([node_id] + context_node_ids)` — Hebbian update with
  the default learning rate (0.15). This is identical to what happens when the
  agent naturally co-activates these nodes through a session, but fires
  immediately rather than at session end.
- Use this when a retrieved node was genuinely helpful and the agent wants to
  teach NeuralMind to surface it alongside those context nodes in future queries.

**Negative signal** (`signal="negative"`, `context_node_ids` optional):
- Calls `store.decay_node(node_id)` — applies one targeted decay tick to all
  synapse edges touching this node. LTP-protected edges (activation_count ≥ 5,
  weight ≥ 0.20) are never fully removed by a single negative signal, so a
  mis-click can't erase long-established associations.
- Use this when a retrieved node was irrelevant. The weight drifts down over
  time rather than being hard-removed.

### What the agent can do with it

An agent that implements a retrieval loop can now self-correct:

```
1. Call neuralmind_query(project_path, "how does auth work?")
2. Get back 4 results: [AuthHandler, LoginService, UserService, CacheLayer]
3. Use the context — determine CacheLayer was irrelevant
4. Call neuralmind_feedback(project_path, node_id="CacheLayer", signal="negative")
5. Call neuralmind_feedback(project_path, node_id="AuthHandler", signal="positive",
     context_node_ids=["LoginService", "UserService"])
6. Next time a similar query fires, CacheLayer ranks lower; AuthHandler/
   LoginService/UserService association is strengthened
```

This is a lightweight one-shot feedback loop — not a full RLHF system, but
closes the "thumbs up / thumbs down on results" gap that mem0 delivers.

### `decay_node` in `synapses.py`

A new `SynapseStore.decay_node(node_id)` method applies targeted per-node decay
without touching any other edge in the store. The same LTP protection and
PRUNE_THRESHOLD pruning as the global `decay()` tick applies, so the feedback
is always bounded.

---

## CI auto-index GitHub Action

### The problem

"CI/CD auto-index" is the number-one team-workflow gap: if each developer runs
`neuralmind build` manually, the team index drifts. An automated action that
re-indexes on every push means the team always has a current, warm index — and
the committed team memory stays up to date without manual `neuralmind memory publish` calls.

### What shipped

`.github/workflows/neuralmind-autoindex.yml` — a drop-in GitHub Action that:
1. Restores the `.neuralmind/` directory from GitHub's Actions cache (keyed to
   source file hashes so only a changed-file build fires a real re-embed).
2. Runs `neuralmind build .` — incremental-by-default; `--force` via
   `workflow_dispatch` input for manual full re-index.
3. Runs `neuralmind memory export --output .neuralmind-team-memory.json` to
   capture the current synapse state.
4. Uses `stefanzweifel/git-auto-commit-action` to commit
   `.neuralmind-team-memory.json` back when it changed, so every `git clone`
   starts with the team's earned synapse intuition.

The action runs on `push` to `main`/`master` and on `workflow_dispatch`.
No secrets are needed — NeuralMind is 100% local; nothing is sent externally.

### Per-agent expectations after install

| Agent | What changes |
|---|---|
| Claude Code | Inherits up-to-date team memory on next session start (SYNAPSE_MEMORY.md reflects new commit) |
| Cursor / Cline / Continue | Team memory bundle in `.neuralmind-team-memory.json` imported on next `neuralmind build` |
| Generic MCP | `neuralmind_wakeup` returns context reflecting the fresh index |

---

## VS Code Extension (native, zero-config)

### The gap

VS Code users who don't run Cline had to hand-wire NeuralMind via a `tasks.json` keybinding
or skip it entirely. The extension closes that gap: every NeuralMind affordance — context
retrieval, index management, graph view, and MCP registration — is now accessible directly
from the editor, with no task runner involved.

### What ships

The extension (`editors/vscode/`) is a thin TypeScript orchestrator over the existing Python
CLI and HTTP server. No new retrieval logic; no new Python dependencies.

**Status bar** — always visible at the bottom left:

| State | Display |
|---|---|
| Index built, fresh | `✓ NeuralMind · 2.1k nodes` (green) |
| Index built, stale | `⚠ NeuralMind · 2.1k nodes` (yellow) |
| Index not built / error | `⊘ NeuralMind` (red) |

Clicking the status bar opens the graph panel. Staleness is measured against
`graphify-out/graph.json` mtime vs. the `neuralmind.autoBuildThresholdHours` setting (default 24 h).

**Command palette** — `Ctrl+Shift+P` → `NeuralMind`:

| Command | What it does |
|---|---|
| `NeuralMind: Query` | Prompt for a question; prints retrieved context to the Output panel |
| `NeuralMind: Wakeup` | Runs `neuralmind wakeup` and prints the context summary |
| `NeuralMind: Skeleton` | Prints the structural skeleton for the active file |
| `NeuralMind: Build Index` | Runs `neuralmind build` with a progress notification |
| `NeuralMind: Probe Retrieval` | Runs `neuralmind probe` and shows answerability / MRR / recall@k |
| `NeuralMind: Open Graph View` | Opens the `neuralmind serve` UI in a WebView panel |
| `NeuralMind: Setup Cline MCP` | Runs `neuralmind install-mcp --client cline` |
| `NeuralMind: Setup VS Code MCP` | Runs `neuralmind install-mcp --client vscode` |

**Graph panel** — `neuralmind serve` UI embedded via `<iframe>` in a VS Code WebView. Reuses
all existing frontend JS/CSS untouched. The panel retains its layout when hidden
(`retainContextWhenHidden: true`).

**Hover cards** (opt-in) — when `neuralmind.enableHover: true`, hovering any symbol fetches
the file's structural skeleton and shows it inline. LRU-cached (50 entries, 60 s TTL).

**Auto-build prompt** — on activation, if the index is older than `autoBuildThresholdHours`
or not built, the extension prompts "Index is stale — Build now?" with a one-click "Build" action.

### Install

```bash
cd editors/vscode
npm install
npm run compile         # produces out/extension.js
# Then press F5 in VS Code to launch an Extension Development Host,
# or run `vsce package` to build a .vsix for local install.
```

**Settings** (`neuralmind.*` in VS Code settings):

| Setting | Default | Description |
|---|---|---|
| `neuralmind.pythonPath` | `"python"` | Path to the Python executable with NeuralMind installed |
| `neuralmind.enableHover` | `false` | Opt-in hover cards (skeleton on symbol hover) |
| `neuralmind.autoBuildThresholdHours` | `24` | Hours before a stale-index prompt fires |

### MCP auto-registration

`neuralmind install-mcp --client vscode` now writes the MCP server entry to
`Code/User/settings.json` under the `"mcp.servers"` key (VS Code 1.99+ native MCP format).
If `settings.json` uses JSONC (comments or trailing commas), the command prints the entry
to paste manually rather than clobbering the file.

### Per-editor expectations after install

| Editor | What changes after extension install |
|---|---|
| **VS Code (extension)** | Status bar shows index state; palette commands work immediately; graph panel opens `neuralmind serve` embedded |
| Claude Code | MCP server registered via `install-mcp --client claude-code`; wakeup/query tools active |
| Cursor | MCP server registered via `install-mcp --client cursor`; wakeup/query tools active |
| Cline | Extension's "Setup Cline MCP" command registers the server; tools active in next Cline session |
| Generic MCP | `neuralmind-mcp` command; `neuralmind_wakeup`, `neuralmind_query`, `neuralmind_feedback` tools |

---

## What the agent actually sees post-install

### v0.38.0 vs v0.37.0 — warm path diff

| Layer | v0.37.0 | v0.38.0 |
|---|---|---|
| L3 search | pure vector, synapse boost | **hybrid (vector + BM25 via RRF), synapse boost** |
| MCP tools | 12 tools | **13 tools** (+ `neuralmind_feedback`) |
| Retrieval feedback | implicit only (co-activation) | implicit + **explicit positive/negative** |
| CI integration | manual `neuralmind build` | **automated via `.github/workflows/neuralmind-autoindex.yml`** |

### Cold path (first session, no learned associations)

Hybrid search improves cold-path retrieval quality immediately — no warm-up
needed. The BM25 index is built during `neuralmind build`, so it's ready on
session one.

---

## Honest scope: what's still not here

- **Re-ranking with a learned ranker model** — BM25 + RRF is a strong baseline
  that adds zero dependencies. A cross-encoder re-ranker (e.g. bge-reranker-v2)
  would add ~200MB and an inference step; not in scope unless retrieval quality
  evals show it's needed.
- **JetBrains native plugin** — VS Code ships in this release (see above);
  JetBrains is the remaining gap. MCP server wiring via the integration guide
  (`docs/wiki/Integration-Guide.md`) is the current path for IntelliJ/Rider users.
- **Cross-repo memory** — synapses are still per-project. The team memory bundle
  mechanism (`neuralmind memory export/import`) is the current path for sharing
  between repos; a federated graph query is a larger architectural change.
- **Query expansion / reformulation** — still one query → one retrieval round.
  Agentic multi-step retrieval is out of scope for the core; agents can
  implement it by chaining `neuralmind_query` calls.
