# NeuralMind v0.39.0 — Trust, transparency, and quality

**The headline:** six improvements that make NeuralMind measurably more trustworthy and transparent in the workflows where it lives — before you build the index, after you query it, while your files change, before you push a commit, and when evaluating the index itself.

## What changed

### 1. `neuralmind build --dry-run` — see savings before you commit

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
  Est. query context    : ~3,200 tokens
  Est. reduction ratio  : ~6.4×

No index files were read or written.
```

Pass `--json` for machine-readable output (useful in CI onboarding scripts). Supports 10+ languages auto-detected by extension. The index is never touched.

### 2. Faster synapse decay on file deletion

`neuralmind watch` now detects when source files are removed and immediately fires `NeuralMind.deactivate_files()` — applying a `decay_node()` tick on every graph node belonging to that file. Previously, deleted-file associations faded only gradually over many sessions. Now they're pruned in real time.

- Watchdog backend: uses `on_deleted` event (event-driven, no polling delay)
- Poll backend: detects deletions by set-difference on the mtime map
- Deletion callbacks fire without the normal debounce delay

The `deletion_callback` parameter is optional and defaults to `None`, so existing callers are unaffected.

### 3. `neuralmind query --explain` — why was this context selected?

Add `--explain` to any query to get a structured trace of how the budget was spent:

```
$ neuralmind query . "How does authentication flow through middleware?" --explain

[... normal context output ...]

  Token budget breakdown:
    L0 (identity):     42 tok
    L1 (summary):     180 tok
    L2 (communities): 410 tok  [auth, middleware, session]
    L3 (search):      268 tok  [handlers.py:authenticate, session.py:validate_token]
  Synapse recall: +3 edges injected
  Reduction ratio: 6.1×
```

The trace is the primary tool for diagnosing a retrieval that felt wrong or incomplete. It shows exactly which clusters loaded and which search hits scored — so you know where to look, not just what the agent saw.

### 4. `neuralmind review` — catch co-breaks before you push

Before opening a PR:

```
$ neuralmind review .
```

NeuralMind reads `git diff --name-only main`, maps each changed file to its graph nodes, runs spreading activation (depth 2, configurable top-*k*), and surfaces the nodes most strongly associated with your changes that you haven't touched yet:

```
Co-break candidates for 3 changed files:
  1. src/session/store.py          (weight 0.84, 12 activations)
  2. tests/test_auth_middleware.py (weight 0.71,  8 activations)
  3. src/auth/token_validator.py   (weight 0.58,  6 activations)
```

Also available as the `neuralmind_review` MCP tool — agents can call it automatically after editing a file. Handles cold (unbuilt) graphs gracefully.

### 5. `neuralmind savings` — cumulative token savings dashboard

```
$ neuralmind savings .
```

Reads the JSONL event log (`NEURALMIND_MEMORY=1`), groups events by session, and prints a dashboard: total sessions tracked, total tokens saved, average reduction ratio, and a table of the most recent queries with their individual ratios. A concrete number for the cost you've avoided — no more estimating.

### 6. `neuralmind probe` now queries by rationale, not name

The `probe` self-test now uses each symbol's **docstring/intent** as the query (e.g. *"Raised when the exp claim is in the past"*) instead of its humanized name. Because the rationale text doesn't contain the symbol name, retrieving the right code from it is a genuine **natural-language → code** test — not the string-match near-tautology the name-based version was (which read ~0.95 MRR on any healthy index and mostly flagged name collisions).

```
Retrieval self-probe — sample_project
Sampled 63 of 64 indexed symbols, retrieval depth k=10
Query source: 51 rationale, 12 label
============================================================
  answerability  : 98%  (file found in top-10)
  MRR            : 0.789
  recall@1/3/5   : 0.667 / 0.905 / 0.968
  blind spots    : 1
------------------------------------------------------------
Symbols the index couldn't retrieve from their own description (1 total):
  - get_me_endpoint()  (api/routes.py)
    query: "GET /api/users/me — requires Authorization: Bearer header"
```

The MRR drop (≈0.95 → 0.789) is the *point* — it's now measuring something real. Undocumented symbols fall back to a humanized name; the report discloses the split so a mostly-fallback run can't masquerade as a strong score.

Review hardening: code-only retrieval (`file_type="code"`), honest `index_size` (code nodes only), `--k ≥ 1` / `--sample-size ≥ 0` validation, no swallowed backend errors, `ks` honored for API callers.

## Per-agent expectations

| Agent | What changes in v0.39.0 |
|-------|--------------------------|
| **Claude Code** | `neuralmind build . --dry-run` estimates savings before building. `neuralmind query . "..." --explain` traces the retrieval. `neuralmind review .` surfaces co-break candidates from git diff. `neuralmind savings .` shows cumulative savings. `neuralmind probe .` now queries by rationale — output includes a `Query source:` line. |
| **Cursor / Cline / generic MCP** | New `neuralmind_review` MCP tool available. Other changes are CLI-only. |
| **Contributors / CI** | `FileActivityWatcher` gains an optional `deletion_callback`. `NeuralMind.deactivate_files(paths)` is a new public method. TOOLS count: 13 → 14. `retrieval_probe()` gains rationale extraction, code-only search, `ks` passthrough, and argument validation. |

## Upgrade notes

No index rebuild required. No config changes needed. All six improvements are additive:

- `--dry-run` and `--explain` are new flags; existing invocations are unchanged
- `deletion_callback=None` default means existing `FileActivityWatcher` callers are unaffected
- `neuralmind savings` requires `NEURALMIND_MEMORY=1` to have been set during prior sessions (the JSONL log must exist)
- `neuralmind review` requires an accumulated synapse graph — on a freshly built index with no `watch` sessions, spreading activation returns empty results (disclosed in output)
