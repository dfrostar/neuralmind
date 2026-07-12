# Use Case: Blast Radius Before a Rename — See Everything a Change Touches

## What you're solving for

You're about to rename a function, change a signature, or delete a module. In a small file that's a five-second edit. In a real codebase it's a gamble: something you don't have open calls it, imports it, or subclasses it — and you find out from a red CI run (or worse, production) instead of from the editor. You want the complete list of code a change would affect **before** you make it, so you can edit with every caller in view.

This is a *correctness* question, not a relevance question — exactly the kind an editing agent gets wrong ("it changed the function but missed two callers"). The static code graph already knows the answer.

## Setup (one time)

```bash
pip install neuralmind
cd your-project
neuralmind build .         # builds the knowledge graph (structural edges included)
```

No `watch` session and no learning history are required. Structural edges — `calls`, `inherits`, `imports_from`, `contains` — are extracted at build time and available on day one. (This is the difference from the synapse layer, which needs editing history to be useful.)

The structural query tools are on by default. To turn the whole layer off: `NEURALMIND_STRUCTURAL=0`.

## The workflow

**Before you rename or change a symbol**, ask the graph what depends on it:

```bash
neuralmind structural "charge customer" --blast-radius
```

`query` can be a symbol name or a natural-language description — it's resolved to the closest **code** node. NeuralMind walks the reverse-dependency edges (everything that transitively calls, imports, subclasses, or implements the symbol) and prints the transitive set:

```
## Blast radius of billing_stripe_client_charge_customer (depth 2) — 1 symbols

- charge_endpoint() — routes.py
```

Now you know: renaming `charge_customer` (or changing its signature) touches `charge_endpoint()` in `routes.py`. You open both, make the change together, and the PR is complete on the first pass.

The walk is **depth-bounded** (`--depth N`, default 2), **cycle-safe**, and **hub-capped** (`NEURALMIND_STRUCTURAL_HUB_DEGREE`, default 50) so one over-connected utility can't explode the result into the whole repo.

## Just the immediate wiring

Drop `--blast-radius` to see a symbol's direct neighbors instead of the transitive set — callers, callees, base/sub classes, importers:

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

Useful when you want to understand how a symbol sits in the code before touching it, rather than scoping a change. Filter with `--relation calls|inherits|imports|all`.

## As an MCP tool (for agents)

```
neuralmind_structural_neighbors(query="charge customer", blast_radius=true)
```

The agent can call this before it edits a symbol, get the affected set back as structured data, and pull every caller into context before writing the change — instead of editing the definition and leaving the callers stale. Same parameters as the CLI: `query`, `relations`, `blast_radius`, `depth`. The returned node ids compose with `neuralmind_synaptic_neighbors`, so an agent can ask both "what *can* be related" (structure) and "what *actually* gets used together" (synapses) in the same loop.

## Optionally fold structural neighbors into retrieval

If you want a query that lands on a called function to automatically pull its callers/callees into the retrieved context, set:

```bash
NEURALMIND_STRUCTURAL_RECALL=1
```

It's **budget-neutral** — a pulled-in neighbor displaces the weakest vector hit rather than adding to the count — and recalled nodes are tagged `[wired]` in the rendered context. This is **opt-in**: on graphs where the call/inherit signal is strong it can saturate top-k recall and crowd out the learned synapse signal, so default retrieval stays byte-identical to v0.41.0. The always-on `structural` tool carries the headline value without touching the tuned retrieval stack.

## What changes for you

| Before | After |
|---|---|
| Rename a symbol, push, wait for CI to tell you which callers you missed | `neuralmind structural … --blast-radius` lists every affected caller/importer/subclass before you edit |
| "I think this is only used in two places" is a gut-feel guess | The reverse-dependency walk gives the complete, depth-bounded set |
| An agent edits a definition and leaves callers stale | The agent calls `neuralmind_structural_neighbors` and edits with the callers in view |

## Limitations

- **Structure, not learned association.** Blast radius is the static call/import/inherit graph — precise about what *can* reach the symbol, silent about how often it actually does. For "what do people edit together," that's the synapse layer (`neuralmind review`).
- **Heuristic call edges are heuristic.** Bare-name call resolution can mislink overloaded names. The optional SCIP precision pass (`NEURALMIND_PRECISION`) upgrades `calls`/`inherits` to compiler-accurate edges; the structural layer consumes whatever is in the graph, so it inherits that precision automatically. Raise `NEURALMIND_STRUCTURAL_MIN_CONFIDENCE` toward `1.0` to trust only high-confidence edges.
- **Symbol-level, not editor navigation.** This is retrieval-time structural context, not a full LSP "find all references." A language whose extractor emits few `calls`/`inherits` edges simply has less to show — graceful degradation, never an error.

## See also

- [Review before push](review-before-push.md) — the *learned-association* complement: co-break candidates from your edit history, not the static graph
- [Full v0.42.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/RELEASE_NOTES_v0.42.0.md)
