# NeuralMind v3.2.0 — drift, caught at commit time

v0.44.0 gave the graph a way to spot the *odd one out* — the cluster member
that skips a pattern its peers share — but only at **query time**, over
whatever a prompt happened to surface. v3.2.0 moves that same consensus
check to the one moment it matters most for an agent-written codebase: the
commit that's about to ship.

## What's in this release

| Feature | Surfaces the… | Surface |
|---------|---------------|---------|
| **`neuralmind drift`** | *pattern drift* — a changed symbol that skips an association a strong majority of its siblings make | `neuralmind drift`, `pre-commit` hook |
| **`init-hook` pre-commit guard** | the same check, wired in automatically | `.git/hooks/pre-commit` |

Both are additive. `drift` warns and exits 0 by default — nothing about a
plain `neuralmind init-hook` can block a commit unless you ask it to with
`--strict`.

## 1. `neuralmind drift` — pattern drift, caught before it ships

Ten endpoint handlers all call `verify_session()`. An agent writes an
eleventh, tests pass, review skims it, and the missing auth check ships —
because the eleventh handler *looks* exactly like the other ten to anyone
scanning the diff. That's the shape `NEURALMIND_SYNAPSE_OUTLIERS` already
catches for a query-time cluster; `drift` catches it for a diff.

```bash
$ neuralmind drift . --staged

## NeuralMind drift check (warning) — 1 finding(s)

- api/routes.py:67 — `delete_me_endpoint()` skips `verify_session()`, which
  3 of its 9 peers (33%) use. Confirm this is deliberate.

Warning only — the commit proceeds. Use --strict to block on drift.
```

It reads the diff (`--staged`, a ref via `--diff`, or the working tree by
default), maps the changed lines back onto graph symbols, groups each one
with its siblings in the same file or class, and asks whether the changed
symbol omits an association its peer group otherwise agrees on. **Only
symbols actually touched by the diff are ever reported** — the graph is
full of pre-existing odd-ones-out, and blaming a commit for those trains
people to ignore the check. Tune what counts as consensus with
`--cohesion` (default `0.6`) and `--min-peers` (default `3`); cap findings
with `--max-findings`.

Stdlib-only, like the rest of the synapse/structural layer — no ChromaDB,
no tree-sitter required to run the check itself. When tree-sitter *is*
installed (the `graphgen` extra), changed files are transparently
re-parsed before judging, so a brand-new function in the diff is visible
even though the persisted index predates it (`--no-refresh` or
`NEURALMIND_DRIFT_REFRESH=0` to skip that and judge against the graph
exactly as last built).

## 2. `init-hook` installs the guard automatically

`neuralmind init-hook` now installs **two** hooks instead of one:

- `post-commit` — rebuilds the index (unchanged from prior releases).
- `pre-commit` — runs `neuralmind drift . --staged`.

```bash
neuralmind init-hook .            # both hooks; drift warns, never blocks
neuralmind init-hook . --strict   # drift blocks the commit
neuralmind init-hook . --no-drift # post-commit rebuild only, no drift guard
```

Both hooks are idempotent and append to (rather than clobber) any existing
hook script, so `init-hook` composes with hooks another tool already
installed.

## What the agent actually sees post-install

| Agent | What changes | How to use it |
|-------|--------------|---------------|
| **Claude Code** | A staged commit that drifts from its peers prints a warning in the terminal (or blocks, under `--strict`) before the commit lands | Run `neuralmind init-hook .` once per repo; adjust `--cohesion`/`--min-peers` if it's too chatty or too quiet for your codebase |
| **Cursor / Cline** | Same — the hook is a plain git `pre-commit` script, provider-agnostic | Nothing agent-specific to configure |
| **Generic MCP / CLI** | `neuralmind drift [path] [--staged\|--diff BASE] [--strict] [--json]` | Call directly, or wire into any CI job with `--diff origin/main --strict --json` |

## Configuration

| Env var | Default | Effect |
|---------|---------|--------|
| `NEURALMIND_DRIFT_REFRESH` | `1` | `0` → skip the transparent re-parse of changed files; judge strictly against the last-built graph. Already a no-op without tree-sitter installed. |

## Honest scope

- **`drift`** needs a built graph (`neuralmind build .`); on a cold graph it
  reports "No code graph found" and exits 0 — it never fails a commit for a
  missing index.
- Peer groups come from the graph's `contains` hierarchy (same file or
  class) narrowed by a shared naming role (`create_*`, `*_endpoint`); a
  symbol with fewer than `--min-peers` siblings, or no strong majority
  among them, is judged as having nothing to say — quiet by design, not a
  false negative to fix.
- This is a heuristic over structural edges (`calls`, `inherits`), not a
  type checker or a security scanner: it flags "this looks different from
  its peers," not "this is wrong." Findings are a prompt to confirm intent,
  not a verdict.

## Upgrade

```
pip install --upgrade neuralmind
neuralmind init-hook .   # re-run to pick up the new pre-commit guard
```
