# NeuralMind v0.42.0 — the code graph learns to answer "what does this touch?"

**Release Date:** July 2026

## What's in this release

NeuralMind's recall has always run on two *soft* signals — semantic
similarity and the learned synapse graph. This release adds the *hard* one
the graph has carried all along: **how the code is actually wired.**

`graphify` already extracts typed structural edges into every `graph.json`
— `calls`, `inherits`, `imports_from`, `contains` — and the embedder
already loads them. Until now they were dead weight, used only by the
graph-view UI. v0.42.0 turns them into a **first-class, queryable recall
signal and an agent-visible capability.**

| Change | What | Surface |
|---|---|---|
| **Structural code graph** | callers/callees/base classes/subclasses/importers of any symbol, from the static graph — precise and available day-one | `neuralmind_structural_neighbors` · `neuralmind structural` |
| **Blast radius** | the transitive set of code a change to a symbol would affect (everything that calls/imports/subclasses it) | `neuralmind structural … --blast-radius` · `blast_radius=true` |
| **Structural recall in retrieval** *(opt-in)* | a query hit's callers/callees pulled into L3 context — budget-neutral (displacement, not addition) | `NEURALMIND_STRUCTURAL_RECALL=1` |

The structural **query surface** (tools + CLI + blast-radius) is on by
default; **default retrieval is byte-identical to v0.41.0**. Folding
structural neighbors into L3 is opt-in (`NEURALMIND_STRUCTURAL_RECALL=1`)
because it interacts with the tuned synapse reranker — see *Honest scope*.
The whole layer is killable with `NEURALMIND_STRUCTURAL=0`; no schema bump,
no change to synapse learning.

> **Two brains, now with innate wiring.** The synapse layer is *learned*
> potentiation — it earns "these go together" from how you work. The
> structural layer is *innate* wiring — precise, compiler/AST-derived,
> known before you've run a single query. They fuse in retrieval without
> competing: **structure says what *can* be related; synapses say what
> *actually* gets used together.** A static index can copy the structure;
> it cannot copy the fusion.

---

## Why this release matters

The failures a structural graph prevents are **correctness** failures, not
relevance failures — exactly the ones an editing agent makes:

- *"It changed the function but missed two callers."* — the call graph now
  pulls callers into context when the definition is the query hit.
- *"It reimplemented a method the base class already provides."* — the
  inheritance chain is one tool call away.
- *"It edited the wrong `parse()` — there are three."* — structure
  disambiguates where similarity can't.
- *"It didn't realize deleting this module breaks four importers."* —
  `--blast-radius` lists them.

The learned synapse layer eventually approximates some of this (things you
edit together wire together) — but only **after** you've paid for the
mistakes that taught it. Structural edges are known on day one.

### 1. Ask how a symbol is wired

```bash
neuralmind structural "create user"
```
```
## Structural neighbors of users_crud_create_user

### Callers (1)
- create_user_endpoint() — routes.py

### Callees (2)
- get_connection() — connection.py
- User — crud.py
```

The MCP tool `neuralmind_structural_neighbors` returns the same, shaped for
agent consumption. `query` may be a symbol name or a natural-language
description — it's resolved to the closest **code** node (rationale/doc
nodes are skipped, since they carry no structural edges).

### 2. Blast radius before a risky change

```bash
neuralmind structural "charge customer" --blast-radius
```
```
## Blast radius of billing_stripe_client_charge_customer (depth 2) — 1 symbols

- charge_endpoint() — routes.py
```

The transitive reverse-dependency set — everything that (transitively)
calls, imports, subclasses, or implements the symbol. Depth-bounded,
cycle-safe, and hub-capped so one over-connected utility can't explode the
result.

### 3. Optionally fold structural recall into retrieval

With `NEURALMIND_STRUCTURAL_RECALL=1`, a query that lands on a called
function also pulls its callers/callees into L3 context. It's
**budget-neutral**: a pulled-in neighbor displaces the weakest vector hit
rather than adding to the count, so the token budget is identical. Recalled
nodes are tagged `[wired]` in the rendered context.

This is **opt-in, not default.** On graphs where the call/inherit signal is
strong it can saturate top-k recall and crowd out the learned synapse
signal (measurable on our onboarding eval), so we keep default retrieval
byte-identical and let you turn on the structural fusion where it helps.
The always-on structural **tools** carry the headline value — "what calls
this?", "what breaks if I change it?" — with zero effect on the tuned
retrieval stack.

---

## What the agent actually sees post-install

| Agent | What changes | How to use it |
|---|---|---|
| **Claude Code** | A new MCP tool `neuralmind_structural_neighbors` appears. (With `NEURALMIND_STRUCTURAL_RECALL=1`, L3 context also folds in `[wired]` callers/callees.) | Ask "what calls `foo`?" or "what would break if I change `Bar`?" — the agent calls the tool |
| **Cursor / Cline** | Same MCP tool over the shared server | Same — the tool is provider-agnostic |
| **Generic MCP** | `neuralmind_structural_neighbors` in the tool list, with `query`, `relations`, `blast_radius`, `depth` params | Call it directly; returns real graph node ids that compose with `neuralmind_synaptic_neighbors` |
| **CLI (any agent / human)** | `neuralmind structural <symbol> [--relation calls\|inherits\|imports\|all] [--blast-radius] [--depth N] [--json]` | Inspect wiring or scope a refactor from the terminal |

---

## Configuration

| Env var | Default | Effect |
|---|---|---|
| `NEURALMIND_STRUCTURAL` | `1` (on) | Master switch for the index + query tools. `0` → nothing built, retrieval byte-identical to v0.41.0. |
| `NEURALMIND_STRUCTURAL_RECALL` | `0` (off) | `1` → fold structural neighbors into L3 retrieval (budget-neutral). Off by default because it interacts with the synapse reranker. |
| `NEURALMIND_STRUCTURAL_MIN_CONFIDENCE` | `0.0` | Drop edges below this `confidence_score`. Raise toward `1.0` to trust only compiler-accurate edges (with `NEURALMIND_PRECISION`). |
| `NEURALMIND_STRUCTURAL_HUB_DEGREE` | `50` | Per-relation degree cap for recall / blast-radius, so a hub can't dominate. |

---

## Honest scope

- **No new extraction.** This surfaces the edges `graphify` (and the
  in-repo `graphgen`) already produce. A language whose extractor emits few
  `calls`/`inherits` edges simply has less to show — graceful degradation,
  never an error.
- **Heuristic call edges are heuristic.** Bare-name call resolution can
  mislink overloaded names. The optional SCIP precision pass
  (`NEURALMIND_PRECISION`) upgrades `calls`/`inherits` to compiler-accurate
  edges; the structural layer consumes whatever is in the graph, so it
  inherits that precision automatically.
- **Symbol-level, not editor navigation.** This is retrieval-time
  structural context, not a full LSP "go to definition" replacement.

---

## Upgrade

`pip install --upgrade neuralmind`. No rebuild required — the structural
index is built from the graph you already have on the next `build` or first
structural query. Nothing to migrate; set `NEURALMIND_STRUCTURAL=0` to opt
out entirely.
