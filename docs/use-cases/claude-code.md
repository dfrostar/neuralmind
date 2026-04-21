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

## Escape hatches

Need the raw file body for a specific command?

```bash
NEURALMIND_BYPASS=1 <your command>
```

Tune hook thresholds via env vars — see [PostToolUse Compression](../../README.md#-posttooluse-compression).

## Expected savings

Combined retrieval + consumption reduction is typically **5–10×** vs vanilla Claude Code on the same tasks. Run `neuralmind benchmark . --json` on your repo for a concrete number.

---

[← Back to use-case index](./README.md) · [Main README](../../README.md)
