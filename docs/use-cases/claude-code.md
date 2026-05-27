# Use Case: Claude Code User

## What you're solving for

You use Claude Code daily. Your context fills up fast, `Read` pulls in too much source, long `Bash` outputs blow your budget, and the bill is adding up. You want both **retrieval-side** and **consumption-side** optimization.

## Setup (one time)

```bash
pip install neuralmind graphifyy
cd your-project
graphify update .              # builds the knowledge graph
neuralmind build .             # builds the vector index
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
