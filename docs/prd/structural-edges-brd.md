# BRD: Structural code graph — agents see how the code is wired, not just what it's near

**Status:** Draft · **Owner:** dfrostar · **Created:** 2026-07-12
**Tracking branch:** `claude/neuralmind-improvements-lx1950` · **Target:** v0.42.0
**Companion:** `docs/prd/structural-edges-trd.md` (technical requirements)

## 1. Executive summary

NeuralMind recall today is driven by two signals: **semantic similarity**
(vector + BM25 search over node text) and **learned co-activation** (the
Hebbian synapse graph — "these nodes get touched together"). Both are
*soft* signals. Neither answers the hard, structural questions an agent
actually asks when it edits code:

- "What **calls** this function? If I change its signature, what breaks?"
- "What does this class **inherit** from, and what overrides it?"
- "What **imports** this module?"

The answers already exist. `graphify` — the extractor that produces
`graph.json` — already emits typed structural edges: `inherits`, `calls`,
`imports_from`, and `contains`. The embedder already loads them
(`embedder.py:130`). But **they are dead weight**: NeuralMind uses them
only for a file-scoped lookup and never surfaces them to the agent, never
feeds them into spreading activation, and never uses them to shape which
context a query pulls in.

This release turns that latent, already-extracted structural graph into a
first-class recall signal and an agent-visible capability — **the "big
picture before you zoom in" the product has always implied but never
delivered.** It is a thin surfacing layer over data we already ship, so
the risk profile is low and the effectiveness gain is concrete: fewer
missed call-sites, fewer broken overrides, fewer "I didn't know that
inherited from X" mistakes.

Positioning: from "finds code that reads like your query" → "**knows how
your code is wired and warns you what a change touches.**"

## 2. The problem (user pain, in the user's words)

| Pain today | What the agent does wrong | Root cause |
| --- | --- | --- |
| "It changed the function but missed two callers." | Edits a definition without visiting every call-site. | No call-graph awareness — callers aren't retrieved unless they happen to be semantically similar. |
| "It reimplemented a method the base class already provides." | Doesn't see the inheritance chain. | `inherits` edges are extracted but invisible to recall. |
| "It edited the wrong `parse()` — there are three." | Picks by vector similarity, not by who actually calls the one in scope. | Structure disambiguates; similarity doesn't. |
| "It didn't realize deleting this module would break four importers." | No blast-radius view. | `imports_from` edges never surface. |

These are *correctness* failures, not *relevance* failures — and they are
exactly the failures a structural graph prevents. The learned synapse
layer eventually approximates some of this (things you edit together wire
together), but only **after** you've paid for the mistakes that taught it.
Structural edges are known on day one, before any learning.

## 3. Why us, why now

- **The data is already in the box.** We ship `inherits`/`calls`/
  `imports_from` in every `graph.json` and throw them away at recall time.
  This is the rare feature that is mostly *deletion of a limitation*.
- **It compounds the moat, doesn't dilute it.** Static-AST competitors
  have structural edges too — that's commodity. Our differentiator is the
  **learned** layer. Fusing structural (known, precise, day-one) with
  learned (earned, associative, improves with use) is a combination a
  static index cannot reproduce: structure tells you what *can* be
  related; synapses tell you what *actually* gets used together.
- **It's on-brand for the "two brains" architecture.** Structural edges
  are the "associative cortex's" innate wiring; synapses are the learned
  potentiation on top. The story writes itself.

## 4. Goals & non-goals

**Goals**
1. Make structural edges (`calls`, `inherits`, `imports_from`, `contains`)
   a queryable, agent-visible signal.
2. Let a query's retrieved context **expand along structural edges** so
   callers/callees/base-classes of a hit are pulled in when relevant —
   budget-neutral, matching how synapse recall already behaves.
3. Give the agent a direct tool to ask "what calls / what inherits / what
   imports this?" and "what is the blast radius of changing this?"
4. Ship with the learned layer intact and every existing behavior
   byte-identical when the feature is disabled.

**Non-goals**
- No new extraction. We do **not** build our own AST parser or replace
  `graphify`. We consume the edges it already produces. (If a language's
  extractor doesn't emit `inherits`/`calls`, this feature simply has less
  to show for that language — graceful degradation, not a blocker.)
- No change to the synapse learning rules. Structural edges are a separate,
  non-decaying signal; they don't reinforce or decay like Hebbian edges.
- Not a full LSP / "go to definition" replacement. This is retrieval-time
  structural context, not an editor navigation feature.

## 5. Success metrics

| Metric | Baseline | Target | How measured |
| --- | --- | --- | --- |
| Caller recall on edit tasks | vector-only | **+15pt** callers retrieved when a called function is the query hit | `eval` fixture with known call-sites |
| "Blast radius" completeness | n/a | ≥90% of direct importers/callers listed by the new tool on the reference repo | golden set in `evals/` |
| Token budget | current L2/L3 | **0 net tokens** added (displacement, not addition) | budget assertion in tests, same discipline as synapse boost |
| Cold-start parity | identical | byte-identical recall when `NEURALMIND_STRUCTURAL=0` | regression test |
| Agent-visible latency | current | < +20ms p95 on structural neighbor lookup | in-memory adjacency index |

## 6. User stories

- *As an agent editing a function signature,* when I retrieve the
  definition, its **callers are pulled into context automatically** so I
  update every call-site in one pass.
- *As an agent,* I can call one MCP tool — `neuralmind_structural_neighbors`
  — to get the typed structural neighborhood of a symbol (callers, callees,
  base classes, subclasses, importers) without a full-text search.
- *As an agent about to delete or rename a symbol,* I can ask for its
  **blast radius** and get the transitive set of things that reference it.
- *As a developer,* the graph-view server overlays structural edges
  (distinct from learned synapse edges) so I can see the two signals side
  by side.

## 7. Scope & phasing

**v0.42.0 (this release) — the core surfacing layer:**
- Structural adjacency index built from `graph.json` edges at build time.
- Structural expansion folded into context selection (budget-neutral).
- `neuralmind_structural_neighbors` MCP tool + `neuralmind structural`
  CLI command.
- `NEURALMIND_STRUCTURAL` kill switch (default on) + docs/SEO across all
  five surfaces per the CLAUDE.md checklist.

**Later (out of scope here, noted for the roadmap):**
- Structure-aware weighting of synapse decay (edges along a real call are
  "realer" than incidental co-activation).
- Blast-radius as a first-class `PostToolUse` warning ("you edited `foo`;
  3 callers were not in context").
- Graph-view interactive path tracing.

## 8. Risks & mitigations

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Edge quality varies by language (weak extractor → few edges) | Med | Graceful degradation; feature shows what exists, never errors on absence. `confidence_score` gates low-confidence edges. |
| Structural expansion adds noise to recall | Med | Budget-neutral displacement + relevance gating, same discipline as the synapse boost; kill switch defaults let us ship conservative. |
| Hub symbols (a utility called 500×) blow up neighborhoods | Med | Degree cap / hub normalization, mirroring the synapse layer's `HUB_DEGREE` treatment. |
| Perceived overlap with synapse layer | Low | Clear framing: structural = innate wiring (precise, day-one); synaptic = learned potentiation (earned). They fuse; they don't compete. |

## 9. Acceptance criteria (pilot-ready)

- [ ] `neuralmind build` produces a structural adjacency index from
  `graph.json` with zero new extraction steps.
- [ ] `neuralmind structural <symbol>` prints typed neighbors (callers,
  callees, bases, subclasses, importers).
- [ ] `neuralmind_structural_neighbors` MCP tool returns the same, shaped
  for agent consumption.
- [ ] A query whose top hit is a called function pulls that function's
  callers into context within the existing token budget.
- [ ] `NEURALMIND_STRUCTURAL=0` yields byte-identical recall to v0.41.0.
- [ ] Docs + SEO shipped across all five surfaces in the same PR.
- [ ] `eval` shows caller-recall lift ≥ +15pt with no faithfulness
  regression.
