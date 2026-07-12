# TRD: Structural code graph — technical design

**Status:** Draft · **Owner:** dfrostar · **Created:** 2026-07-12
**Tracking branch:** `claude/neuralmind-improvements-lx1950` · **Target:** v0.42.0
**Companion:** `docs/prd/structural-edges-brd.md` (business requirements)

## 1. Overview

The BRD's ask: make `graphify`'s already-extracted typed structural edges
(`calls`, `inherits`, `imports_from`, `contains`, …) a first-class,
queryable recall signal and an agent-visible capability. This TRD
specifies the components, the exact insertion seams, the data contracts,
and the test plan.

**Core design principle: thin surfacing layer, additive, killable.** No new
extraction, no changes to synapse learning, and byte-identical behavior
when `NEURALMIND_STRUCTURAL=0`. Every seam mirrors an existing one (the
synapse layer), so the change is low-novelty and low-risk.

## 2. Current state (what already exists)

| Fact | Location |
| --- | --- |
| Structural edges are produced by the in-repo generator | `neuralmind/graphgen.py` — `resolve_edges`, `_resolve_calls` (`:836`), `_resolve_inherits` (`:804`), `_resolve_imports` (`:778`), `contains` in `_emit_*` |
| Full relation vocabulary is defined | `neuralmind/ir.py:72-86` (`contains`, `calls`, `imports_from`, `imports`, `inherits`, `implements`, `uses`, `references`, `defines`, `shares_data_with`, `rationale_for`) |
| `Edge` dataclass | `neuralmind/ir.py:282-300` |
| Edges land in `graph.json` under the **`links`** key | `graphgen.py:641-654` |
| Embedder loads them into `self.edges` | `embedder.py:130` (`self.graph.get("edges", self.graph.get("links", []))`) |
| Edge shape | `{relation, context, confidence, source_file, source_location, weight, source, target, confidence_score}` (`graphgen.py:321-342`) |
| …but they are consumed only by the graph-view + IR | `querying.graph_data` (`:231-264`), `ir.py`. **Never fed into retrieval; never exposed via MCP/CLI.** |
| Optional compiler-accurate edges (SCIP) upgrade `calls`/`inherits` | `neuralmind/precision.py`, gated on `NEURALMIND_PRECISION` (`core.py:611-625`) |
| Retrieval injection seam (synapse recall) | `core.py:402-405` — `selector.synapse_recall = self._recall_for_selection` |
| Synapse recall template method | `core.py:952-984` (`_recall_for_selection`) |
| Public per-symbol API precedent | `NeuralMind.synaptic_neighbors` (`core.py:986`) |
| MCP tool template | `tool_synaptic_neighbors` (`mcp_server.py:176-194`); `TOOLS` list (`:370`); `handlers` dict (`:640-681`) |
| CLI structural-render precedent | `cmd_skeleton` (`cli.py:1384`); nested-subcommand pattern `memory` (`:2232`) |
| `community_<id>` pseudo-nodes are **not** real graph nodes | membership-filter precedent `querying.py:245-264` |
| Stdlib-only test pattern | `tests/test_synapses.py`, `tests/test_graphgen.py`; fixtures `tests/fixtures/sample_project*/graphify-out/graph.json` |

**Implication:** the feature is ~80% wiring existing data through new
read paths, plus one small new pure-Python module. No parser work.

## 3. Architecture

```
graph.json ("links")
      │  (already loaded by embedder.load_graph → embedder.edges)
      ▼
┌─────────────────────────┐
│ StructuralIndex          │  NEW — neuralmind/structural.py
│  (pure-Python, stdlib)   │  typed adjacency over real node ids
│  build_from_edges(edges) │  callers/callees/bases/subclasses/importers
│  neighbors(id, rels)     │  blast_radius(id, depth)
└───────────┬─────────────┘
            │ injected by core.build()  (mirror of synapse_recall seam)
   ┌────────┴────────┬──────────────┬─────────────────┐
   ▼                 ▼              ▼                 ▼
ContextSelector   NeuralMind     MCP tool          CLI
_apply_structural  .structural_   neuralmind_       neuralmind
_expansion()       neighbors()    structural_       structural
(budget-neutral)   .blast_radius() neighbors         <symbol>
```

The `StructuralIndex` is the only genuinely new logic. Everything else is a
thin call into it, following an existing template line-for-line.

## 4. Component 1 — `neuralmind/structural.py` (new module)

Pure-Python, stdlib-only (no ChromaDB, no numpy), so it tests like the
synapse layer.

### 4.1 Relation semantics

Raw `relation` strings map to **direction-aware semantic views**. An edge
`{source: A, target: B, relation: R}` contributes:

| `relation` | Forward view (of A) | Reverse view (of B) |
| --- | --- | --- |
| `calls` | `callees` | `callers` |
| `inherits` | `bases` (A's base classes) | `subclasses` (B's subclasses) |
| `implements` | `interfaces` | `implementers` |
| `imports_from` / `imports` | `imports` | `importers` |
| `contains` | `members` | `container` |
| `uses` / `references` | `uses` | `used_by` |

`rationale_for`, `shares_data_with`, `defines` are indexed but not part of
the default neighbor view (available via explicit `relations=[...]`).

### 4.2 API

```python
class StructuralIndex:
    # Edges whose confidence_score < min_confidence are dropped (default 0.0
    # keeps all EXTRACTED edges; raise it to trust only SCIP-precise edges).
    def build_from_edges(self, edges: list[dict], *, min_confidence: float = 0.0) -> None: ...

    # Direct typed neighbors. `relations=None` → the default semantic views
    # (callers, callees, bases, subclasses, importers, container/members).
    def neighbors(self, node_id: str, relations: list[str] | None = None
                  ) -> dict[str, list[str]]: ...

    # Transitive reverse-dependency set: everything that (calls|imports|
    # subclasses)-> node_id, up to `depth` hops, degree-capped per hop.
    def blast_radius(self, node_id: str, depth: int = 2) -> list[str]: ...

    # Flat weighted recall for context expansion (see §6). Returns
    # [(neighbor_id, structural_weight), ...] for the union of the seed ids'
    # highest-priority structural neighbors, hub-capped.
    def recall(self, seed_ids: list[str], top_k: int = 8) -> list[tuple[str, float]]: ...

    def stats(self) -> dict: ...   # edge counts by relation, node coverage, hub list
```

### 4.3 Storage model

Two `dict[str, dict[str, list[str]]]` adjacency maps (forward + reverse
keyed by node id then relation), built once from `embedder.edges`. In
memory only — the edges are already materialized in `graph.json`; there is
no separate persisted DB (unlike synapses, which accumulate learned state
across sessions). Rebuilt lazily on first structural query and cached on
the `NeuralMind` instance; invalidated by `update_files()` incremental
re-index. Memory is O(edges); the demo graph is 189 edges — trivial. A
100k-symbol repo with ~500k edges is still a few tens of MB of Python
lists.

### 4.4 Node-id contract (critical)

The index references **whatever ids are present in the loaded
`graph.json`** — it never mints or assumes ids. `graphify` and the in-repo
`graphgen` use different id schemes (agent confirmed: graphgen →
`users_crud_py`/`__init___fn`; real graphify → `users_crud_user`); both
are internally consistent. `StructuralIndex.build_from_edges` reads
`edge["source"]`/`edge["target"]` verbatim, so it is correct for either
producer. Symbol/query → node-id resolution (for CLI/MCP ergonomics) is
delegated to `embedder.search(query, n=1)` — the same resolver
`synaptic_neighbors` uses — never to id reconstruction.

### 4.5 Hub handling

A utility function called 500× would make `callers` a firehose. `recall()`
and `blast_radius()` apply a per-relation degree cap
(`STRUCTURAL_HUB_DEGREE`, default 50, mirroring `synapses.HUB_DEGREE`):
above the cap, the relation is down-weighted (recall) or truncated with a
`"…+N more"` marker (neighbors/CLI), never silently dropped.

## 5. Component 2 — `core.py` wiring

In `NeuralMind.build()`, immediately after the synapse-recall injection
(`core.py:402-405`), add the structural injection — same shape:

```python
# structural recall — precise, day-one code wiring (BRD §3)
if os.environ.get("NEURALMIND_STRUCTURAL") != "0":
    self._structural_index = StructuralIndex()
    self._structural_index.build_from_edges(self.embedder.edges)
    selector.structural_recall = self._structural_for_selection
```

New private method mirroring `_recall_for_selection` (`core.py:952-984`):

```python
def _structural_for_selection(self, seed_ids: list[str]) -> list[tuple[str, float]]:
    idx = getattr(self, "_structural_index", None)
    return idx.recall(seed_ids) if idx else []
```

New public API next to `synaptic_neighbors` (`core.py:986`):

```python
def structural_neighbors(self, query_or_id, relations=None, resolve=True): ...
def blast_radius(self, query_or_id, depth=2, resolve=True): ...
```
`resolve=True` runs `embedder.search` to turn a symbol/NL string into a
node id; `resolve=False` treats the input as a literal node id.

## 6. Component 3 — context-selection expansion (`context_selector.py`)

Add a **structural** sibling to the synapse boost, gated + budget-neutral,
following `_apply_synapse_boost` (`context_selector.py:553-633`) exactly:

```python
# new constants (mirror the SYNAPSE_* ones)
STRUCTURAL_SEED_K = 3
STRUCTURAL_PULL_IN_MAX = 2
STRUCTURAL_BOOST_WEIGHT = 0.35   # ≥ SYNAPSE_BOOST_WEIGHT: structure is precise

self.structural_recall = None    # injected by core.build(), else no-op
```

`_apply_structural_expansion(results)`:
1. No-op if `structural_recall` is None or `NEURALMIND_STRUCTURAL == "0"`.
2. Seed from the top `STRUCTURAL_SEED_K` hit ids.
3. `cands = structural_recall(seeds)` → strongest absent structural
   neighbors (callers/callees/bases) vector search missed.
4. **Displace** the weakest vector hits with up to `STRUCTURAL_PULL_IN_MAX`
   structural neighbors, fetched via `embedder.get_nodes_by_ids`
   (already exists, `embedder.py:390`). Count fixed → **zero net tokens**,
   identical discipline to the synapse pull-in.
5. Tag swapped-in nodes `_structural_recalled: True` + `_structural_relation`
   so `get_l3_search`'s renderer (`:664-679`) can show
   `[caller]`/`[base class]` labels next to `[recalled]`.

**Ordering:** run structural expansion **before** the synapse boost in
`get_l3_search` (`:651`). Rationale: structure is precise and known day-one;
it should claim a displacement slot first, then learned co-activation
re-ranks whatever remains. Both are individually budget-neutral, so
composing them is still budget-neutral.

L2 (community) expansion is **out of scope** for v0.42 — structural edges
are symbol-level, not community-level; forcing them through the
`community_<id>` path (`_boost_communities_from_synapses`, `:520`) would
require synthesizing pseudo-nodes we don't want. Symbol-level L3 expansion
is where the value is.

### 6.1 Shipping decision — L3 expansion is opt-in (default off)

The L3 expansion is wired but **not injected by default**. `build()` sets
`selector.structural_recall` only when `NEURALMIND_STRUCTURAL_RECALL=1`; the
index and the query tools (§5, §7, §8) are always on.

Rationale, found during implementation: the structural signal is *strong*.
On the reference `onboarding` eval, turning L3 expansion on lifted the
**cold** (no team memory) top-k hit-rate from 0.759 → 0.843 — so high it
saturated the metric and left the learned synapse layer no headroom, driving
the gated `onboarding_lift` **negative** (−0.074). This is the classic
dual-reranker interaction the project deliberately avoided (PILOT-BRD:
"dual reranker confusion → single synapse layer"). Faithfulness was
unaffected (+0.19); the regression is specifically synapse-vs-structural
competition for top-k slots.

Keeping the expansion opt-in preserves byte-identical default retrieval (so
the onboarding gate stays green at +0.009) while still shipping the
high-value, zero-risk query surface. Making it default-on is deferred to a
follow-up that resolves the composition (e.g. structural only fills slots
the synapse boost declined, or a unified single-pass scorer) — tracked in
§15.

## 7. Component 4 — MCP tool (`mcp_server.py`)

Clone `tool_synaptic_neighbors` (`:176-194`):

```python
def tool_structural_neighbors(project_path, query, relations=None,
                              blast_radius=False, depth=2):
    mind = _mind(project_path)
    if blast_radius:
        return {"query": query, "blast_radius": mind.blast_radius(query, depth=depth)}
    return {"query": query, "neighbors": mind.structural_neighbors(query, relations)}
```

Register: append one dict to `TOOLS` (`:370`) and one lambda to `handlers`
(`:640-681`). `inputSchema`: `{query: str (required), relations: [str],
blast_radius: bool, depth: int}`. Wrapped by `security.secure_call` like
every other tool (`:696`) — no new auth surface. Returns real node-id
strings, so it composes with `neuralmind_synaptic_neighbors` output.

**Description copy (agent-facing):** "Return how a symbol is wired into the
codebase — its callers, callees, base/sub classes, and importers — from the
static code graph. Use before editing a function's signature (find all
callers) or a class (find overrides), or pass `blast_radius=true` to get the
transitive set of code a change would affect."

## 8. Component 5 — CLI (`cli.py`)

New `cmd_structural(args)` next to `cmd_skeleton` (`:1384`), registered near
`:2305` with the nested-subcommand shape of `memory` (`:2232`):

```
neuralmind structural <symbol> [--relation calls|inherits|imports|all]
                               [--blast-radius] [--depth N] [--json]
```
Human output groups by semantic view (Callers / Callees / Base classes /
Subclasses / Importers), each line `label  —  source_file:Lnn`, resolved
from node metadata. `--json` emits the raw `structural_neighbors` dict for
scripting. Symbol resolution reuses `embedder.search` top-1 with a
"did you mean" list when the match score is low.

## 9. Component 6 — graph-view overlay (minor)

`querying.graph_data` (`:231-264`) already returns `links`, so structural
edges are already available to the graph-view server. Change is
cosmetic: tag each edge with its `relation` and a `signal: "structural"`
field so the front-end can style structural edges distinctly from
`signal: "synapse"` learned edges (same membership filter at `:245-264`
still applies to drop `community_*` synapse endpoints). No new endpoint.

## 10. Configuration

| Env var | Default | Effect |
| --- | --- | --- |
| `NEURALMIND_STRUCTURAL` | `1` (on) | Master switch for the index + query tools. `0` → index never built, retrieval byte-identical to v0.41.0. |
| `NEURALMIND_STRUCTURAL_RECALL` | `0` (**off**) | `1` → inject `structural_recall` so L3 folds in structural neighbors. **Shipped off** — see §6.1. |
| `NEURALMIND_STRUCTURAL_MIN_CONFIDENCE` | `0.0` | Drop edges below this `confidence_score`. Raise toward `1.0` to trust only SCIP-precise edges when `NEURALMIND_PRECISION` is on. |
| `NEURALMIND_STRUCTURAL_HUB_DEGREE` | `50` | Per-relation degree cap for recall/blast-radius. |

All three documented in `docs/wiki/CLI-Reference.md`'s Environment
Variables table per the CLAUDE.md checklist.

## 11. Backward compatibility

- **Kill switch parity:** with `NEURALMIND_STRUCTURAL=0`, `build()` skips
  index construction and never sets `selector.structural_recall`; a
  regression test asserts identical L3 output vs baseline on a fixture.
- **Graceful degradation:** a language whose extractor emits no
  `calls`/`inherits` (or an old `graph.json` without those relations)
  yields an empty index → every structural path returns empty, never
  errors. `stats()` surfaces coverage so users see when a language is thin.
- **No schema bump:** consumes existing `graph.json` `SCHEMA_VERSION = 1`;
  no migration. Old indexes work unchanged.
- **Synapse layer untouched:** structural edges are non-decaying and stored
  separately; they never call `reinforce`/`decay`.

## 12. Testing plan

Stdlib-only unit module `tests/test_structural.py` (pattern:
`test_synapses.py` + `test_graphgen.py`):

- **Relation direction:** given a tiny edge list, `neighbors("A")` returns
  `B` as a callee when `A --calls--> B`, and `callers` of `B` includes `A`.
- **Inheritance direction:** `A --inherits--> B` → `B` in `A.bases`, `A` in
  `B.subclasses`.
- **Node-id fidelity:** build from both a graphgen fixture and a real
  graphify fixture (`tests/fixtures/sample_project*/graphify-out/graph.json`)
  — assert ids are read verbatim, not reconstructed.
- **Confidence gating:** edges below `min_confidence` excluded.
- **Hub cap:** a node with degree > cap truncates/down-weights.
- **Blast radius:** transitive reverse closure at depth 1 vs 2; cycle-safe.
- **Budget-neutrality (integration, `tests/test_structural_recall.py`):**
  L3 hit count and token budget unchanged with expansion on vs off; a query
  whose top hit is a called function pulls in a known caller (displacement,
  not addition).
- **Kill-switch parity:** `NEURALMIND_STRUCTURAL=0` → byte-identical L3.
- **MCP + CLI smoke:** `tool_structural_neighbors` and `cmd_structural`
  return expected shapes on the demo graph.
- **Eval:** extend `evals/` with a caller-recall fixture; assert ≥ +15pt
  caller recall and no faithfulness regression (BRD §5).

## 13. Performance

- Index build: single O(edges) pass at `build()` time; ~µs for the demo
  graph, low-ms for large repos. Amortized into the existing embed step.
- `neighbors()` / `recall()`: O(degree) dict lookups, in-memory → sub-ms;
  meets the BRD's "< +20ms p95" target with margin.
- `blast_radius(depth=2)`: BFS bounded by hub cap; worst case bounded by
  `hub_degree^depth`, capped and cycle-guarded.
- Memory: two adjacency dicts, O(edges). Freed on `close()`.

## 14. Docs & SEO (CLAUDE.md checklist — same PR as the feature)

**Docs (every surface):**
- [ ] `RELEASE_NOTES_v0.42.0.md` — "what the agent sees post-install" +
  per-agent expectations table (Claude Code / Cursor / Cline / generic MCP).
- [ ] `README.md` — bump banner, demote v0.41, new release-notes row,
  update the "PostToolUse — what happens automatically" / tools sections.
- [ ] `docs/index.html` — banner + earlier-releases trail.
- [ ] `docs/about.html` — new "What's New in v0.42.0" section above prior.
- [ ] `docs/wiki/CLI-Reference.md` — `neuralmind structural` command +
  the three `NEURALMIND_STRUCTURAL*` env vars.
- [ ] `docs/use-cases/*.md` — update the "editing / refactoring safely"
  walkthrough (existing) **and** add a new "blast-radius before a rename"
  walkthrough (potential use case the feature unlocks).
- [ ] Do **not** edit `CHANGELOG.md` (release-please owns it).

**SEO:**
- [ ] `pyproject.toml` keywords — add `call-graph`, `blast-radius`,
  `structural-code-search` (new nouns).
- [ ] `docs/index.html` `<meta description>`/`<meta keywords>` — broaden to
  "structural + learned code intelligence."
- [ ] `docs/about.html` page `<meta>` — refresh if positioning shifts.
- [ ] `docs/sitemap.xml` — add release notes + new use-case URLs.
- [ ] Consider `SoftwareApplication`/`Article` JSON-LD (still an open gap).

**Release flow:** land as a single `feat:` commit so release-please bumps
`pyproject.toml` + manifest and writes the changelog; docs + SEO ship in
the same PR.

## 15. Rollout / phasing

**v0.42.0 (this TRD):** `StructuralIndex`, core wiring, L3 expansion, MCP
tool, CLI command, graph-view tag, kill switch, docs + SEO.

**Deferred (roadmap, noted in BRD §7):**
- Structure-aware synapse weighting (a co-activation that follows a real
  `calls` edge reinforces harder).
- `PostToolUse` blast-radius warning ("edited `foo`; 3 callers not in
  context").
- Interactive path tracing in the graph-view.

## 16. Open questions

1. **Default recall aggressiveness.** Ship `STRUCTURAL_PULL_IN_MAX=2` or
   start at `1` and raise after eval? *Proposed: start at 2; it's
   displacement, not addition, and eval gates it.*
2. **`contains`/`rationale_for` in default neighbor view?** *Proposed: no —
   available via explicit `--relation`, but noisy in the default view.*
3. **Precision coupling.** Should `NEURALMIND_PRECISION` auto-raise
   `MIN_CONFIDENCE`? *Proposed: no — keep them independent; document the
   combination.*
