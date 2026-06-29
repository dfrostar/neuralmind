# NeuralMind v0.40.0 — Trust, transparency, and quality gaps closed

**The headline:** five developer-experience improvements that make NeuralMind measurably more useful in the workflows where it lives — before you build the index, after you query it, while your files change, and before you push a commit.

## What changed

### Gap 1: `neuralmind build --dry-run` — see savings before you commit

Installing NeuralMind used to require a leap of faith. Now you can scan any project and get a concrete token-savings estimate *before* building the index:

```
$ neuralmind build . --dry-run
NeuralMind dry run — my-project
  Files scanned : 142
  Lines of code : 18,342
  Languages     : 89 Python, 53 TypeScript

  Estimated nodes       : 1,420
  Est. full-codebase    : ~458,550 tokens
  Est. wake-up context  : ~1,420 tokens
  Est. query context    : ~2,840 tokens
  Est. token reduction  : ~161x per query

No index was built. Run `neuralmind build .` to activate these savings.
```

Auto-detects Python, TypeScript, Go, Rust, Java, C/C++, C#, Ruby, PHP, and more. `--json` emits structured output for CI/CD or onboarding scripts.

**What the agent sees:** teams can add this to their README or onboarding script to show the expected savings for their specific codebase before asking developers to install anything.

### Gap 2: File deletion → faster synapse decay

When you delete or rename a file during refactoring, its synapse associations were previously left at full weight and took several decay cycles to fade. That meant a deleted `middleware.py` could still surface in spreading-activation recall for days.

The `neuralmind watch` daemon now detects deletions and immediately applies a targeted decay tick to every graph node that lived in the removed file — one tick is enough to sink non-LTP edges below the prune threshold within 1–2 normal decay cycles, while heavily-established LTP edges (activation count ≥ 5) fade gracefully over weeks.

Under the hood:

- **watchdog path:** `on_deleted` events fire `_record_deletion()` immediately (no debounce — the file is gone).
- **polling path:** the poll loop now tracks which keys it saw last cycle; missing ones trigger the deletion callback.
- **core:** new `NeuralMind.deactivate_files(paths)` calls `decay_node()` once per node per deleted file.
- **watch daemon:** wires `deletion_callback=on_deleted` — no flag needed, automatic.

**What the agent sees:** stale memory about deleted files stops surfacing in context. Refactors don't leave ghost associations.

### Gap 3: `neuralmind query --explain` — why this context?

`--trace` gives you raw retrieval events for debugging. `--explain` gives you a human-readable answer to "why did NeuralMind select this context?":

```
$ neuralmind query . "auth flow" --explain
...
Why this context?

  Token budget breakdown:
    L0 identity   :    142 tokens
    L1 summary    :    513 tokens
    L2 communities:    800 tokens
    L3 search     :    980 tokens
    Total used    :  2,435 tokens
    Est. saved    : 47,565 tokens  (20.5x reduction)

  Layers activated : L0, L1, L2, L3
  Communities loaded: [0, 2]

  Top search hits (L3, 4 nodes):
    0.912  authenticate  (auth/handlers.py)
    0.887  JWTMiddleware  (auth/middleware.py)
    0.831  verify_token   (auth/tokens.py)

  Synapses that fired (2 events):
    ...
```

Implies `--trace` automatically so synapse attribution is always available. `--explain` answers the most common dev question ("what is this tool actually doing?") without requiring them to parse raw trace JSON.

### Gap 4: `neuralmind review` — diff-aware co-break warnings

Before pushing a commit, find the files you probably forgot to update:

```
$ neuralmind review . --base HEAD~1
NeuralMind review — my-project  (diff against: HEAD~1)

Changed files (3):
  • auth/middleware.py
  • auth/handlers.py
  • tests/test_auth.py

Co-break candidates — files NOT in diff but strongly associated (4):
  0.782 ████████  auth/tokens.py
  0.654 ██████    auth/models.py
  0.431 ████      config/settings.py
  0.198 ██        docs/auth.md
```

Uses `git diff --name-only` to find changed files, runs spreading activation seeded at their graph nodes, and surfaces files that have historically co-evolved with them. Requires the synapse graph to have accumulated edges (grows automatically from `neuralmind watch` and agent queries).

Also available as the **`neuralmind_review` MCP tool** — agents can call it directly before proposing a change:

```json
{"tool": "neuralmind_review", "project_path": ".", "changed_files": ["auth/middleware.py"]}
```

### Gap 5: `neuralmind savings` — cumulative token savings dashboard

Verifies the 40-70x claim against your own real usage:

```
$ neuralmind savings .
NeuralMind token savings — my-project

  Queries logged    : 47
  Wakeups logged    : 12
  Avg reduction     : 38.2x

  Tokens actually used :     83,140
  Est. cost without NM : 2,950,000  (at 50,000 tokens/query)
  Tokens saved         : 2,866,860

  Most recent queries:
    2025-06-29  [ 1482 tok / 33.7x]  How does authentication work?
    2025-06-29  [ 2103 tok / 23.8x]  What database ORM do we use?
```

Reads from the opt-in JSONL memory log (same one the self-improvement engine uses). `--global` shows savings across all projects. `--json` emits structured output for dashboards.

Memory logging must be enabled (answer yes at the opt-in prompt, or set `NEURALMIND_MEMORY=1`).

---

## Per-agent expectations

| Agent | Changes visible |
|-------|-----------------|
| **Claude Code** | All 5 improvements. `--dry-run` useful in onboarding scripts. `review` surfaces in the agent's tool calls via MCP. Deletion-aware decay improves memory quality after refactors. |
| **Cursor** | `neuralmind_review` MCP tool available for pre-commit checks. |
| **Cline** | Same as Cursor. |
| **Generic MCP** | `neuralmind_review` + all existing tools. |

---

## Upgrade notes

No index rebuild required. No config changes. All changes are additive:

- `--dry-run` and `--explain` are new flags with no effect when absent.
- `deletion_callback` defaults to `None` — existing `FileActivityWatcher` callers are unaffected.
- `deactivate_files()` on `NeuralMind` is a new method; existing callers are unaffected.
- `neuralmind_review` is a new MCP tool; existing tool handlers are unchanged.
- `neuralmind savings` is a new CLI subcommand.
