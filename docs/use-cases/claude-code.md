# Use Case: Claude Code User

## What you're solving for

You use Claude Code daily. Your context fills up fast, `Read` pulls in too much source, long `Bash` outputs blow your budget, and the bill is adding up. You want both **retrieval-side** and **consumption-side** optimization.

## Setup (one time)

```bash
pip install neuralmind
cd your-project
neuralmind build .             # builds the knowledge graph + vector index
neuralmind install-hooks .     # PostToolUse compression (Read/Bash/Grep)
neuralmind init-hook .         # auto-rebuild on every git commit
```

## Daily workflow

**At session start**, have Claude Code call:

```
neuralmind_wakeup(project_path=".")
```

That gives the agent ~400 tokens of architecture/cluster context instead of 50K tokens of file reads.

**When asking a code question**, prefer `neuralmind_query` over raw exploration:

```
neuralmind_query(project_path=".", question="How does authentication flow through the middleware?")
```

Returns ~800–1,100 tokens with the right clusters and search hits.

**Before opening a file**, use `neuralmind_skeleton`:

```
neuralmind_skeleton(project_path=".", file_path="src/auth/handlers.py")
```

Returns the function list, rationales, call graph, and cross-file edges — ~88% cheaper than `Read`.

**Everything else** (Read, Bash, Grep you don't route through NeuralMind) is **automatically compressed** by the hooks. You don't have to think about it.

## What changes for you

| Before | After |
|---|---|
| Session starts with "let me explore the repo" + 20 file reads | `wakeup` loads orientation in one call |
| Asking about a flow = reading 5 files end-to-end | `query` returns the relevant slice |
| `npm test` dumps 800 lines into the agent | Hook keeps errors + last 3 lines (~91% smaller) |
| `grep -r "foo"` floods with 200 matches | Capped at 25 with "N more hidden" pointer |
| Every commit drifts the index | `post-commit` hook rebuilds incrementally |
| "What should I open next?" is guesswork *(v0.11.0+)* | `neuralmind next . path/to/file.py` returns the files most often edited after this one, ranked by probability |

## Predict the next file *(v0.11.0+)*

Once `neuralmind watch` has been running for a few sessions, the
directional synapse layer accumulates ordered `(from_file, to_file)`
transitions and the agent can ask:

```bash
$ neuralmind next . src/auth/handlers.py
After src/auth/handlers.py:
   45.2%  tests/test_auth.py
   28.4%  src/auth/middleware.py
   12.1%  docs/auth.md
```

Same data via the `neuralmind_next_likely` MCP tool — Claude Code
can call it right after finishing edits in one file to surface the
files you usually touch next, no manual prompt needed.

## Let the selector tune itself *(v0.26.0+, opt-in)*

If you want NeuralMind to adapt how much context a query surfaces to how you
actually work, set `NEURALMIND_SELECTOR_AUTOTUNE=1`. The `SessionStart` hook then
runs the self-improvement tuner once per session (after the synapse decay tick):
it watches the **re-query rate** — when you fire two same-session queries whose
recalled communities overlap heavily, the first one under-disclosed and you had
to come back — and nudges the L2 recall depth up (so the next query lands more in
one shot) or down (so it stops spending tokens on context you didn't use). Moves
are single-step, clamped to `[2, 6]`, and fail-open.

```bash
export NEURALMIND_SELECTOR_AUTOTUNE=1   # off by default; unset = byte-identical to before
neuralmind self-improve status .        # read-only: current depth, re-query rate, warm-up state
```

It's off by default and does zero extra hot-path work when unset, so it's safe to
try and trivial to turn back off.

## Understand why a retrieval answered the way it did *(v0.40.0+)*

Add `--explain` to any `query` call to get a structured trace of how the budget was spent:

```bash
neuralmind query . "How does authentication flow through the middleware?" --explain
```

Output appended after the normal context block:

```
  Token budget breakdown:
    L0 (identity):   42 tok
    L1 (summary):   180 tok
    L2 (communities): 410 tok  [auth, middleware, session]
    L3 (search):    268 tok    [handlers.py:authenticate, session.py:validate_token, ...]
  Synapse recall:  +3 edges injected
  Reduction ratio: 6.1×
```

The trace is the primary tool for diagnosing a retrieval that felt wrong or incomplete — it shows you exactly which clusters loaded and which search hits scored, so you know where to look.

## Catch co-breaks before you push *(v0.40.0+)*

Before opening a PR, run:

```bash
neuralmind review .
```

NeuralMind reads `git diff --name-only main`, maps each changed file to its graph nodes, runs spreading activation, and surfaces the nodes most strongly associated with your changes that you haven't touched yet — the most likely co-break candidates:

```
Co-break candidates for 3 changed files:
  1. src/session/store.py          (weight 0.84, 12 activations)
  2. tests/test_auth_middleware.py (weight 0.71,  8 activations)
  3. src/auth/token_validator.py   (weight 0.58,  6 activations)
```

Same data via the `neuralmind_review` MCP tool — Claude Code can call it automatically after editing a file, before a commit or push.

## Track cumulative savings *(v0.40.0+, requires NEURALMIND_MEMORY=1)*

```bash
export NEURALMIND_MEMORY=1   # enables the JSONL event log (off by default)
# … work for a week …
neuralmind savings .
```

Shows total sessions tracked, total tokens saved, average reduction ratio, and a table of the most recent queries with individual ratios. A concrete number for the cost you've avoided.

## Escape hatches

Need the raw file body for a specific command?

```bash
NEURALMIND_BYPASS=1 <your command>
```

Tune hook thresholds via env vars — see [PostToolUse Compression](../../README.md#-posttooluse-compression).

## Expected savings

Combined retrieval + consumption reduction is typically **5–10×** vs vanilla Claude Code on the same tasks. Run `neuralmind benchmark . --json` on your repo for a concrete number.

## Second screen: see what the agent is looking at (v0.6.0+)

Pop a separate terminal and run:

```bash
neuralmind serve .
```

Open the URL it prints. You now have an Obsidian-style graph view
of your codebase that updates in real time as Claude works. Every
time Claude calls `neuralmind_query` (or any other NeuralMind tool),
the relevant nodes **pulse** on the canvas — animated radial rings,
color-coded by event source. The sidebar shows a rolling log of
the most recent ~80 events.

The use this unlocks is **trust-gap closure**:

| You wonder… | The graph view answers in ~2 seconds |
|---|---|
| Is Claude looking at the right code? | Watch which nodes pulse during the prompt |
| Did the retrieval miss something obvious? | Use the replay-last-query overlay to see the L3 hits |
| Why did this answer feel wrong? | Pulse pattern usually shows it — wrong cluster, missing edge, unexpected hub |
| Has the synapse layer learned anything yet? | Hover the synapse edges; weight + activation count appear |

Pin the nodes you want to keep in focus (the visible pin glyph
shows pinned state at a glance), use the depth slider (1–3 hops)
to see how far the agent's retrieval reached, and use Cmd/Ctrl-K
or `/` to jump-to-search from anywhere.

`NEURALMIND_EVENT_LOG=0` disables the cross-process bridge if you
prefer the in-process feed only.

---

[← Back to use-case index](./README.md) · [Main README](../../README.md) ·
[Multi-agent: share the brain across all your tools](./multi-agent.md)
