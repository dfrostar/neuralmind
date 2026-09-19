# Synapse Module

**Last updated:** 2026-08-21
**Version:** v3.x
**Audience:** Engineers, operators, and contributors who want to understand (or extend) NeuralMind's brain-like associative memory layer.

The synapse module is NeuralMind's *hippocampus + associative cortex*. It sits
as a second, persistent brain alongside the LLM: the agent fires queries and
tool calls, NeuralMind reinforces or decays the weighted edges between the code
nodes those events activated, and future retrievals spread activation across
the resulting graph instead of relying on a flat top-k vector search alone.

This page is the architecture reference for the module as a whole, including
the **seeding** layer (N-13) that solves the cold-start problem. For the
learning model itself, see the [Learning Guide](Learning-Guide). For usage in
the build/query lifecycle, see the [Architecture](Architecture#synapse-layer-v04)
overview.

---

## Table of contents

- [The four files](#the-four-files)
- [Data model](#data-model)
- [Learning: Hebbian co-activation + decay](#learning-hebbian-co-activation--decay)
- [Memory namespaces](#memory-namespaces)
- [Recall: spreading activation](#recall-spreading-activation)
- [Directional transitions (what comes next)](#directional-transitions-what-comes-next)
- [Seeding — solving the cold start (Tier 1 / N-13)](#seeding--solving-the-cold-start-tier-1--n-13)
  - [Structural seeding](#structural-seeding)
  - [Business-context seeding — N-13](#business-context-seeding--n-13)
  - [Bundle seeding](#bundle-seeding)
  - [LLM-assisted documentation seeding](#llm-assisted-documentation-seeding)
- [Agent memory export](#agent-memory-export)
- [Operations: stats, pruning, namespaces](#operations-stats-pruning-namespaces)
- [Design invariants](#design-invariants)

---

## The four files

| File | Responsibility | Stdlib-only |
|------|----------------|-------------|
| `neuralmind/synapses.py` | The `SynapseStore` itself — SQLite-backed Hebbian store, schema + migration, seeding, spread/recall, stats | ✅ |
| `neuralmind/synapse_client.py` | Thin file/activity-level orchestration over the store (activate, spread, compliance) | ✅ |
| `neuralmind/synapse_feedback.py` | The write-path: watcher co-activation, Edit/Write reuse detection, decay on delete, query reinforcement | ✅ |
| `neuralmind/synapse_memory.py` | Export learned associations to agent-readable markdown (`SYNAPSE_MEMORY.md`, Claude Code auto-memory) | ✅ |

The whole module is deliberately **stdlib-only** (SQLite + `math`) so the
synapse layer runs and tests without the heavy embedding/tree-sitter depend
cycle. It reaches the graph only through `mind.embedder.get_file_nodes` /
`get_graph`, never by parsing source itself.

---

## Data model

Five tables in `<project>/.neuralmind/synapses.db` (WAL mode):

| Table | Holds |
|-------|-------|
| `synapses` | Undirected Hebbian edges `(node_a, node_b, namespace, weight, activation_count, …)` via canonical ordering `node_a < node_b` |
| `synapse_transitions` | Directional, ordered transitions `(from_node, to_node, …)` — "after touching A, you touched B" |
| `node_activations` | Per-node activation/salience counters |
| `structural_edges` | Persisted directed call/import/inherits graph from the build (the seeding substrate) |
| `type_edges` | Type-inference edges (return type, optionality, confidence, inferrer) |
| `meta` | Key/value store (schema version stamped here) |

Schema versioning is explicit: v0 (pre-namespace) is migrated in place to v1 in
a single IMMEDIATE transaction, folding `namespace` into the primary keys.
A migration bug never corrupts learned memory — any failure rolls the whole
migration back.

---

## Learning: Hebbian co-activation + decay

The store learns by *co-activation*: nodes that fire together wire together.

- **Reinforcement** is Hebbian — `activate(node_ids)` strengthens every edge
  among the co-activated set.
- **Decay** is multiplicative and *time-based* (since v0.??): an exponential
  half-life model `weight × exp(−λ·age_days)`, `λ = ln 2 / half_life_days`.
  A 60-day-old edge has exactly half the weight of a 1-day-old edge at the
  default 30-day half-life. Decay is one-way — it never re-inflates a fresh
  edge, and never resurrects a pruned one.
- **Pruning** — weights decaying below `PRUNE_THRESHOLD` are deleted; stale
  synapses older than N days can be cleared with `neuralmind synapse prune`.
- **Long-term potentiation (LTP)** — edges whose lifetime activation count
  crosses `LTP_THRESHOLD` get a weight floor (`LTP_FLOOR`) and decay slower,
  so heavily-used long-established associations survive routine refactors.
- **Hub normalization** — nodes with degree above `HUB_DEGREE` divide their
  outgoing contributions by degree during spread, so a single utility node
  can't dominate retrieval.

---

## Memory namespaces

Every synapse, transition, and activation row carries a `namespace` (PRD 4) so
different kinds of memory don't pollute each other. Namespaces are plain
single-token strings (`normalize_namespace` rejects whitespace/empty), so
import/export and new kinds stay trivial — there is no enum table.

| Namespace | Meaning | Half-life |
|-----------|---------|-----------|
| `personal` | **Default.** All pre-namespace memory migrates here. | 30 days |
| `shared` | Imported team baseline — `seed_from_*`, bundles, `neuralmind memory import`. | 60 days |
| `branch:<name>` | Per-git-branch working memory. | 30 days (active namespace weighting) |
| `ephemeral` | Session-scoped scratch; decays fast, cleared at session boundaries. | 1 day |

**Merged-read weighting.** Reads default to a *merged* view across the active
namespace, `personal`, and `shared`, each scaled by a constant:

```
merged_weight = W_BRANCH · w_active + W_PERSONAL · w_personal + W_SHARED · w_shared
```

- Active namespace reads at `W_BRANCH` (1.0) → recent/branch-local context wins.
- `personal`, when not the active namespace, reads at `W_PERSONAL` (0.8).
- `shared` reads at `W_SHARED` (0.5) → imported team baseline is never louder
  than your own memory.

Passing `namespaces=[...]` reads **only** those namespaces at **raw** weights
(no multipliers), which is what `neuralmind synapse stats`, `export`, and
inspection use. On the default branch the active namespace *is* `personal`, so
merged behavior is byte-identical to the pre-namespace store.

---

## Recall: spreading activation

Retrieval is spreading activation over the weighted graph, not flat vector
similarity:

- `spread(seeds, depth=2, top_k)`) dispatches energy from seed nodes through
  neighbors (optionally with per-namespace attribution via
  `spread_with_contributions`), decaying at `SPREAD_DECAY` per hop, and returns
  the `top_k` nodes ranked by accumulated activation.
- `neighbors(node)` — merged, ranked strongest neighbors of a single node.
- `next_likely(from)` — probability distribution over what typically follows
  (see directional transitions below).

The `SynapseClient.spread` / `spread_detailed` / `synaptic_neighbors` methods
wrap these for file-level convenience and fail-open (return `[]` on a cold
graph or any error).

---

## Directional transitions (what comes next)

The `synapse_transitions` table learns *order*, not just co-occurrence:
"after touching A, you normally touch B."

- **Write path:** `record_sequence(file_paths)` (used by the watcher /
  `activate_files`) records a directional `A → B → C` for consecutive pairs in
  an edited batch.
- **Half-life:** transitions decay slower than undirected edges
  (`TRANSITION_*` constants) — sequential signals are rarer and noisier and
  need to accumulate before fading.
- **Read path:** `next_likely(node)` normalizes over all outgoing transitions
  to yield a probability distribution. Surface via `neuralmind next` and the
  `neuralmind_next_likely` MCP tool.

---

## Seeding — solving the cold start (Tier 1 / N-13)

A fresh install has **no** learned associations — the old Hebbian layer waited
days/weeks of real use to accumulate signal. Seeding fixes this by loading the
writable store with *real architectural priors* at build time. Seeding is
**automatic, idempotent, and fail-open**: it runs inside `build()`, never
blocks a build if it errors, and re-running only reinforces existing edges.

The build pipeline (`core.py` `build()`, when synapses are enabled) runs, in
order:

1. `seed_from_structural()` — persist + seed the real call-graph.
2. `seed_from_bundle(bundle_path)` — only when `--bootstrap <bundle.json>`.
3. `seed_from_documents(all_nodes)` — the N-13 business-context matcher.

### Structural seeding

`PersistStructuralEdges` first folds the graphify relation vocabulary into the
`structural_edges` table (`calls`/`imports`/`inherits`/`implements`/`uses`/
`contains`), then `seed_from_structural()` converts each
`(caller, callee, call_count)` into an undirected synapse edge using a
log-scaled weight:

```
weight = clamp(BASE + LOG_SCALE · ln(call_count + 1), MAX)   # 0.25 → 0.70
```

Hot call paths grow toward the cap; single-observation edges stay near the
floor. Seeded edges land in the **`shared`** namespace (60-day half-life), are
**not** LTP-protected, and increment `activation_count` on re-seed — so a path
that disappears from the graph eventually prunes after enough builds skip it.

### Business-context seeding — N-13

`seed_from_documents(content_nodes)` builds **deterministic, LLM-free** Hebbian
edges between ingested business documents (book chapters, decisions, SOPs,
meeting notes, policies) and the code symbols they reference — the backbone of
the "second brain" expansion. It runs every `build()` so daemon rebuilds pick up
new content, not just the one-shot ingest path.

**Which nodes are "business"?** Node metadata must carry a
`content_category` of `ai-agent-playbook`, `peptide-patient-guide`, or
`business_context` with a `file_type` of `book-chapter` / `report` / `source` /
`document` / `book`. Config, plans, progress, and claims files are excluded.

**Matching** normalizes every node ID by splitting on `_ . / - ::` and
lowercasing, tokenizes business text (content + label + title, words ≥ 3 chars),
and classifies stopwords (component appearing in >10% of node IDs, or on a
hardcoded common-token blacklist like `test`, `core`, `api`, `auth`, `this`,
`function`, …).

| Match signal | Edge weight | Rule |
|--------------|-------------|------|
| **Exact label** | 0.40 | A node's label tokens are a subset of the business node's text tokens. |
| **Compound** | 0.25 | 2+ consecutive non-stopword ID components appear **adjacent** in the text (not just present). |
| **Single rare component** | 0.20 | Exactly one non-stopword component appears, and it's rare (<5% of nodes derive it from a word appearing in fewer than 5% of node IDs) — blocks common prose words like "book", "system", "engine". |
| **Shared specific tag** (business↔business) | 0.20 | Two business nodes share a metadata tag present in <20% of business nodes. |
| **Title reference** (business↔business) | 0.25 | One business node's title appears in the other's text. |

Idempotency is careful: re-seeding uses `MAX(weight)` and `MAX(activation_count)`
— *never* `+1` — so keyword-match seeding can't LTP-protect false positives
after ~5 runs the way structural re-observation legitimately can (`+1` there is
re-observing real call edges). Returns the number of *new* edges created (0
when no business nodes — fail-open).

### Bundle seeding

`seed_from_bundle(bundle_path)` imports a JSON file mapping
`(node_a, node_b) → weight` — typically exported from a mature project via
`neuralmind export --synapses`. Used for **cold-start onboarding** when no edit
history exists: curated architectural priors land in `shared` at high
confidence (`weight = MAX(existing, bundle)`). Wire it into a build with
`--bootstrap <bundle.json>`.

### LLM-assisted documentation seeding

`seed_from_documentation(docs_root)` is the opt-in, LLM-based analogue. When
`NEURALMIND_LLM_SEED=1` **and** an `ANTHROPIC_API_KEY` are present, it parses
`README.md`/`docs/architecture.md` and asks `claude-haiku-4-5` for explicit
"node_a,node_b,weight" relationships (weight clamped to 0.25–0.40). It's fully
**fail-open** — any import/parse/API error returns 0 edges. Because it issues
an external model call, it is *not* part of the default build path.

---

## Agent memory export

`synapse_memory.py` renders the learned weights into agent-readable markdown so
the model references associations even without calling the MCP tools:

- **Project-local** — always writes `<project>/.neuralmind/SYNAPSE_MEMORY.md`
  (import via `@.neuralmind/SYNAPSE_MEMORY.md` from `CLAUDE.md`).
- **Claude Code auto-memory** — additionally writes
  `~/.claude/projects/<slug>/memory/synapse-activations.md` when that dir
  exists.

Content: top strongest pairs (with LTP tags), hub nodes, and directional
"what typically comes next" transitions (v0.11.0+). Keys off `stats()`; an
empty store still yields a valid document. Purely an export — never blocks the
live store, fails open (returns the paths that succeeded).

---

## Operations: stats, pruning, namespaces

| Command | What |
|---------|------|
| `neuralmind synapse stats` | Edge/synapse/activation counts, per-namespace breakdown, active namespace, LTP count. |
| `neuralmind synapse prune --days N` | Delete synapses older than N days (LTP-protected edges survive). |
| `neuralmind memory export\|import --namespace` | Export/import a learned-weights bundle (`neuralmind/ir.py`) — team memory hand-off. |
| `neuralmind health` | End-to-end install check including synapse store status (exit 0/1/2). |

Toggle the synapse layer: `NEURALMIND_SYNAPSE_INJECT=0` skips prompt-time
recall, `NEURALMIND_SYNAPSE_EXPORT=0` skips memory export. All fail-open.

---

## Design invariants

- **The store is syntax-agnostic.** It operates on graph node IDs + identifier
  tokens (via `synapse_feedback`), never on parsed source — so it works
  uniformly across every tree-sitter extractor and every added language.
- **Everything fails open.** A seeding error, a locked DB, a missing graph, or
  a dead LLM never breaks a build, a hook, or a query.
- **Seeding is idempotent.** Already-seeded edges are reinforced, not
  duplicated, and matching paths avoid LTP-poisoning themselves.
- **Per-project isolation is physical.** The store lives in
  `<project>/.neuralmind/`; `build .` in repo A never touches repo B. See
  [Multi-Project-Scoping](Multi-Project-Scoping).
- **Stdlib-only by design.** The synapse layer (and its tests) run without the
  full dependency set.

---

*This page is part of the NeuralMind docs/wiki. For the higher-level learning
model, see [Learning-Guide](Learning-Guide); for the build/query lifecycle,
see [Architecture](Architecture).*
