# Plan — NeuralMind Future-Proofing PRD Pack

**Created:** 2026-06-10
**Status:** Planning artifact (roadmap reference — not yet scheduled)
**Scope:** A staged, nine-initiative roadmap for the durability arc beyond
the current eval-first releases.

---

## Relationship to existing roadmap

This pack is the longer-horizon companion to the already-tracked
eval-first arc. Several initiatives here formalize or extend work that is
already in flight — cross-reference before scheduling so they don't fork:

- **PRD 1 (Versioned IR)** and **PRD 7 (Pluggable Ingestion)** extend the
  `GraphSource` decoupling tracked in
  [`2026-06-05-graph-backend-decoupling.md`](2026-06-05-graph-backend-decoupling.md)
  and the v0.14 "Decouple" theme in [`../../ROADMAP.md`](../../ROADMAP.md).
- **PRD 2 (Retrieval Quality Harness)** builds on the v0.13 eval harness
  (`neuralmind eval`) and the onboarding-lift work in
  [`2026-06-06-onboarding-lift-eval-handoff.md`](2026-06-06-onboarding-lift-eval-handoff.md).
- **PRD 8 (Durable Team Memory)** is the portable cross-agent memory format
  flagged in the v0.16 "Anticipate" theme.
- **PRD 9 (Agent-Agnostic Orchestration)** is the host-capabilities adapter
  from the v0.15 "Endure" theme.

The broader engineering posture (cadence, monitoring, compliance, scale)
lives in [`../FUTURE-PROOFING-PLAN.md`](../FUTURE-PROOFING-PLAN.md).

---

## Overview

NeuralMind is a local-first coding memory and context system built around a
graph-backed repository representation, ChromaDB/TurboVec retrieval, MCP
tools, hooks, watcher/service modes, and learned synapse transitions for
session priming and next-context prediction. The current product is already
differentiated by its 4-layer retrieval model, persistent
`SYNAPSE_MEMORY.md` priming, local graph UI, and token-reduction
benchmarking, but its long-term durability depends on reducing
architectural coupling, making retrieval quality measurable, and stabilizing
the product boundary across CLI, MCP, watcher, and UI surfaces.

This PRD pack converts those priorities into a staged roadmap. The first
horizon focuses on internal contracts and observability, the second on
runtime architecture and memory isolation, and the third on platform
durability through pluggable ingestion and portable team memory.

## Roadmap at a glance

| Horizon | Initiative | Outcome |
|---|---|---|
| 0–30 days | PRD 1: Versioned Internal Index Contract | Stable canonical IR decouples NeuralMind from direct parser output assumptions. |
| 0–30 days | PRD 2: Retrieval Quality Harness | Retrieval changes are measured by relevance and answerability, not just token reduction. |
| 0–30 days | PRD 3: Explainability and Debug Traces | Retrieval failures can be diagnosed across ingestion, ranking, and compression layers. |
| 31–90 days | PRD 4: Memory Namespaces and Branch Isolation | Learned memory stays useful without polluting predictions across branches and teams. |
| 31–90 days | PRD 5: Daemon-First Architecture | NeuralMind becomes a stable local service with thin clients on top. |
| 31–90 days | PRD 6: Polyglot Monorepo Support | Large multi-package repositories become selective and incremental rather than fragile and global. |
| 3–6 months | PRD 7: Pluggable Ingestion Framework | Multiple parsers can target a shared NeuralMind representation. |
| 3–6 months | PRD 8: Durable Team Memory Portability | Teams can transfer useful learned context across machines and environments. |
| 3–6 months | PRD 9: Agent-Agnostic Orchestration Layer | Agent integrations become thin adapters instead of core-architecture dependencies. |

## PRD 1: Versioned Internal Index Contract

### Problem

NeuralMind currently depends on `graphify update .` (or the built-in
tree-sitter `graphgen`) and consumes a `graph.json`, which means the core
system is tightly coupled to one upstream graph producer and its format
assumptions. This creates risk in four areas: parser drift, limited language
coverage, migration friction, and difficulty introducing alternate ingestion
backends without touching retrieval internals.

### Goal

Introduce a canonical, versioned NeuralMind intermediate representation (IR)
that becomes the only internal contract consumed by retrieval, memory,
compression, benchmarking, UI, and MCP layers.

### Users

- Core maintainer extending the product surface.
- Power user indexing diverse repos with different parser quality.
- Integration author adding support for a new parser or language.
- Team adopting NeuralMind across multiple project types.

### User stories

- As a maintainer, a new parser backend should be able to plug into
  NeuralMind without rewriting retrieval or memory logic.
- As a user, an upgrade should migrate old project state safely instead of
  forcing a rebuild whenever the schema changes.
- As an integrator, the system should expose a documented schema for files,
  symbols, edges, clusters, and synapses.

### Scope

Must include:
- Canonical entities for file, symbol, function, class, method, module,
  document, cluster, edge, and synapse.
- `ir_version`, migration metadata, and compatibility rules in project state.
- A `graphify -> IR` adapter as the first supported ingestion path.
- Backward-compatible loaders for current projects.
- Validation tooling for malformed or incomplete IR payloads.

### Non-goals

- Shipping multiple parser backends in the first release.
- Replacing the current retrieval stack.
- Changing user-facing commands beyond compatibility shims.

### Functional requirements

1. `neuralmind build` must convert current graphify output into the canonical
   IR before indexing.
2. Existing commands such as `query`, `wakeup`, `skeleton`, `search`, and
   `benchmark` must operate on the IR without user workflow changes.
3. A migration command must upgrade older index state in place when possible.
4. The system must reject unsupported IR versions with actionable error
   messages.
5. A schema validation command must report missing required fields,
   incompatible edge types, and orphaned entities.

### Technical requirements

- Store IR metadata separately from embedding/index engine state.
- Define a JSON schema or equivalent typed contract for the IR.
- Support migration functions from at least the current storage format to
  IR v1.
- Add fixtures that compare legacy graphify builds against IR-adapted builds
  for equivalence.
- Ensure IR can represent partial parser coverage and confidence levels for
  future backends.

### UX and API changes

- Add `neuralmind validate`.
- Add `ir_version` and adapter metadata to stats output.
- Include compatibility details in debug and benchmark JSON outputs.

### Success metrics

- 100% of current fixture repos build successfully through the adapter path.
- Less than 5% variance in current retrieval output quality versus baseline
  on migrated fixtures.
- At least 95% of existing project directories migrate without requiring a
  clean rebuild.

### Risks

- Hidden assumptions in downstream retrieval code may surface only after
  migration.
- IR design may become too graphify-shaped if rushed.
- Migration bugs could silently corrupt learned memory associations.

### Rollout

- Phase 1: Hidden internal adapter, legacy mode default.
- Phase 2: Dual-write and comparison mode.
- Phase 3: IR default, legacy fallback retained one minor release.
- Phase 4: Legacy storage deprecated.

## PRD 2: Retrieval Quality Harness

### Problem

The repo already emphasizes token-reduction benchmarking, but token
reduction alone does not prove that retrieved context stays relevant,
complete, or answerable as ranking and compression evolve. Without a quality
harness, regressions can ship while still looking good on cost metrics.

### Goal

Create a retrieval evaluation framework that measures precision, recall,
ranking quality, and answerability for representative coding tasks across
fixture repositories.

### Users

- Maintainers reviewing PRs that modify retrieval or compression.
- Contributors experimenting with reranking, clustering, or synapse learning.
- Advanced users evaluating whether NeuralMind is trustworthy on their repos.

### User stories

- As a maintainer, each PR should show whether retrieval got better or worse
  in measurable terms.
- As a contributor, a change to synapse reranking should be testable against
  a fixed benchmark set.
- As a user, published benchmark results should explain both token savings
  and retrieval quality trade-offs.

### Scope

Must include:
- Golden query sets for fixture repos.
- Expected relevant files, symbols, or clusters for each query.
- Metrics including precision@k, recall@k, MRR, and answerability.
- CI reporting and regression thresholds.
- Machine-readable outputs for dashboarding later.

### Non-goals

- Building a hosted leaderboard.
- LLM judge orchestration in v1.
- Solving end-to-end code correctness evaluation.

### Functional requirements

1. `neuralmind benchmark` must support quality-eval mode in addition to
   token-comparison mode.
2. Benchmark fixtures must cover at least architecture questions,
   bug-localization questions, refactor questions, and "what should I edit
   next" style prompts.
3. CI must fail when quality metrics regress past configured thresholds.
4. PR comments must include metric deltas and affected queries.
5. JSON outputs must support later ingestion into charts or dashboards.

### Technical requirements

- Define benchmark fixture format as structured YAML or JSON.
- Support deterministic replay with pinned index versions.
- Separate retrieval evaluation from LLM generation to reduce noise.
- Allow optional human-reviewed labels for ambiguous queries.
- Version benchmark suites independently from code.

### UX and API changes

- Add `neuralmind benchmark --quality`.
- Add `--suite` and `--baseline` flags.
- Surface quality deltas in release notes and CI summaries.

### Success metrics

- At least 25 benchmark queries spanning 3 or more repos in the first
  release.
- Every retrieval-affecting PR reports quality metrics automatically.
- Zero silent regressions in benchmarked scenarios after rollout.

### Risks

- Gold labels may be incomplete or debatable.
- Contributors may overfit to the public fixture set.
- Answerability scoring may need refinement after early use.

### Rollout

- Phase 1: Internal benchmark suite.
- Phase 2: CI opt-in.
- Phase 3: CI required for retrieval-affecting PRs.
- Phase 4: Public benchmark docs and contributor guide.

## PRD 3: Explainability and Debug Traces

### Problem

NeuralMind retrieval combines layered summaries, graph clustering, semantic
search, learned associations, transitions, and output compression, which
makes failure analysis difficult when results are surprising or incomplete.
Users and maintainers need to know why a result was returned, what was
filtered out, and where ranking influence came from.

### Goal

Add first-class retrieval traces and explanation metadata across CLI, MCP,
and the graph UI.

### Users

- Maintainers triaging retrieval bugs.
- Advanced users trying to tune their setup.
- Integrators embedding NeuralMind into other agent workflows.

### User stories

- As a user, a wrong retrieval should show whether the issue came from
  ingestion, cluster selection, semantic search, or synapse boosts.
- As a maintainer, bug reports should include a compact trace bundle that
  reproduces the retrieval path.
- As an integrator, MCP responses should provide machine-readable
  attribution.

### Scope

Must include:
- Per-layer trace output for queries.
- Attribution for scores and boosts.
- Replay support in graph UI.
- Saved trace artifacts for recent queries.

### Non-goals

- Full observability platform.
- Cross-machine telemetry.
- Hosted analytics.

### Functional requirements

1. `query` and equivalent MCP methods must support trace mode.
2. The trace must show candidate generation, rank contributions, filters, and
   compression summaries.
3. The graph UI must visualize nodes chosen by the last traced query.
4. Trace payloads must be exportable as JSON.
5. Users must be able to toggle trace verbosity.

### Technical requirements

- Stable trace schema.
- Bounded payload sizes for MCP consumers.
- Redaction controls for sensitive file paths if traces are shared.
- Replay compatibility across minor versions when possible.

### Success metrics

- 90% of retrieval support issues become diagnosable from attached traces.
- Time-to-triage for retrieval bugs drops materially after release.
- Trace mode adds less than 15% median latency overhead in local use.

### Risks

- Traces may become too verbose to be useful.
- Score attribution may expose unstable internals if not normalized.
- UI replay may lag schema evolution unless versioned carefully.

### Rollout

- Phase 1: CLI trace mode.
- Phase 2: MCP trace metadata.
- Phase 3: Graph UI replay.
- Phase 4: Issue template with trace attachment support.

## PRD 4: Memory Namespaces and Branch Isolation

### Problem

NeuralMind learns from watcher activity and stores synapse associations plus
directional transitions, which is powerful but can become noisy over time if
different branches, personal habits, and team behaviors all update the same
memory layer. Long-lived repositories need scoped memory to avoid stale or
misleading priors.

### Goal

Introduce namespace-aware memory with branch isolation, merge policies, and
decay controls.

### Users

- Solo developers working across many experimental branches.
- Teams sharing conventions across a repo.
- CI or ephemeral agents that need short-lived memory scopes.

### User stories

- As a developer, feature-branch work should not poison default next-file
  predictions on main.
- As a team lead, reusable shared memory should be exportable across machines.
- As an agent operator, ephemeral sessions should be able to learn locally
  without permanent pollution.

### Scope

Must include:
- Namespaces for personal, shared, branch, and ephemeral memory.
- Configurable TTL or decay behavior per namespace.
- Export, import, inspect, and reset commands.
- Merged query behavior with transparent weighting.

### Non-goals

- Full identity and access management.
- Cloud sync.
- Multi-tenant hosted storage.

### Functional requirements

1. Synapse and transition writes must record namespace and branch metadata.
2. Query and next-context operations must support namespace selection or
   merged mode.
3. `stats` must show contribution by namespace.
4. Users must be able to clear one namespace without deleting the project
   index.
5. Default merge behavior must prioritize recent branch-local context while
   retaining useful long-term shared priors.

### Technical requirements

- Update storage schema for namespace-aware memory.
- Add configurable decay functions and retention policies.
- Support branch detection from Git state where available.
- Preserve performance under merged lookups.

### Success metrics

- Lower false-positive next-edit predictions after branch-heavy workflows.
- Shared-memory bootstrap improves time-to-usefulness on fresh machines.
- Namespace operations complete without requiring full rebuilds.

### Risks

- Weighting logic may become hard to reason about.
- Export/import semantics may drift across versions.
- Branch detection edge cases may create unexpected routing.

### Rollout

- Phase 1: Internal namespace tagging.
- Phase 2: CLI namespace controls.
- Phase 3: Default merged mode.
- Phase 4: Shared-memory export/import.

## PRD 5: Daemon-First Architecture

### Problem

NeuralMind currently exposes CLI, MCP, watch, and serve modes, but the stable
long-term boundary should be a local service that owns state, index
lifecycle, caching, health, and concurrency. A daemon-first architecture
reduces duplicated initialization, lowers latency on warm queries, and
centralizes state management.

### Goal

Promote NeuralMind into a local daemon with thin CLI, MCP, and UI clients on
top.

### Users

- Daily power users running NeuralMind continuously.
- Agent integrations requiring low-latency, repeatable access.
- Maintainers debugging concurrent watch/query/build behavior.

### User stories

- As a user, repeated queries should be fast without reinitializing state on
  every call.
- As an integrator, CLI and MCP should behave identically because they share
  one service contract.
- As a maintainer, index locking and rebuild orchestration should live in one
  place.

### Scope

Must include:
- Local daemon with health and job endpoints.
- Stable JSON API for query/build/watch/stats operations.
- CLI fallback when daemon is not running.
- Centralized locking, cache, rebuild queue, and watcher coordination.

### Non-goals

- Hosted SaaS.
- Multi-user remote service.
- Distributed indexing.

### Functional requirements

1. Starting the daemon must initialize project state once and reuse it across
   requests.
2. CLI commands must prefer daemon mode when available.
3. MCP server must call the same internal API used by CLI and graph UI.
4. The daemon must expose health, status, and active job information.
5. Concurrent watch/build/query operations must not corrupt index or memory
   state.

### Technical requirements

- Define local transport, such as Unix socket or localhost HTTP.
- Add job queue and lock manager.
- Add warm cache and project registry.
- Ensure graceful shutdown and crash recovery.
- Add compatibility tests for direct mode versus daemon mode.

### Success metrics

- Lower median warm-query latency versus direct CLI mode.
- Zero state-corruption incidents in concurrency tests.
- One shared API contract across CLI and MCP surfaces.

### Risks

- Service lifecycle bugs may be harder to diagnose than CLI-only flows.
- Windows and macOS background-service ergonomics may differ.
- Users may resist a daemon if startup is heavy or intrusive.

### Rollout

- Phase 1: Experimental daemon.
- Phase 2: CLI auto-detect and opt-in default.
- Phase 3: MCP and UI on shared API.
- Phase 4: Daemon-first default with direct fallback retained.

## PRD 6: Polyglot Monorepo Support

### Problem

Future-proof code memory must work for large polyglot monorepos with
generated code, vendored directories, package boundaries, and uneven parser
coverage. A project-global rebuild model becomes expensive and brittle as
repository size grows.

### Goal

Add selective, partition-aware, incremental indexing for monorepos.

### Users

- Teams running large multi-service repos.
- Solo developers with docs, tooling, frontend, backend, and infra in one
  tree.
- Agent users who need scoped retrieval instead of whole-repo noise.

### User stories

- As a user, changing one package should not require rebuilding the full
  repository index.
- As a maintainer, generated or vendored content should be excluded or
  downweighted predictably.
- As an agent operator, queries should respect service boundaries while still
  supporting cross-package relationships.

### Scope

Must include:
- Include/exclude rules by path and language.
- Partitioned indexes per package or service.
- Global cross-partition graph references.
- Incremental invalidation at partition level.

### Non-goals

- Perfect semantic understanding of every language.
- Fully custom parser stack.
- Distributed cluster indexing.

### Functional requirements

1. Users must be able to define index partitions via config or
   auto-detection.
2. Builds must invalidate only affected partitions where possible.
3. Queries must search relevant partitions first, then expand globally if
   needed.
4. Generated and vendored paths must be configurable for exclusion or
   downweighting.
5. Benchmark tooling must include monorepo fixtures.

### Technical requirements

- Extend project metadata with partition maps.
- Add cross-partition edge representation in IR.
- Support path-level invalidation and caching.
- Maintain acceptable query latency as partition count grows.

### Success metrics

- Large monorepos avoid full rebuilds for common edits.
- Query relevance improves on partition-scoped tasks.
- One benchmark suite includes a polyglot monorepo by the first stable
  release.

### Risks

- Auto-partitioning heuristics may misclassify packages.
- Cross-partition ranking may become complex.
- Users may need stronger defaults for exclude rules.

### Rollout

- Phase 1: Manual partition config.
- Phase 2: Auto-detection for common monorepo layouts.
- Phase 3: Partition-aware retrieval defaults.
- Phase 4: Advanced tuning and UI visibility.

## PRD 7: Pluggable Ingestion Framework

### Problem

Once a canonical IR exists, NeuralMind still needs multiple ways to populate
it so that parser limitations or ecosystem changes do not block adoption. A
pluggable ingestion framework makes the platform resilient to upstream tool
churn and expands language coverage over time.

### Goal

Create a plugin interface for ingestion backends with graphify as one backend
among several.

### Users

- Maintainers extending language support.
- Contributors building new parser adapters.
- Teams using repos that do not fit graphify coverage well.

### User stories

- As a user, a repo should still be indexable even if the preferred parser
  has partial support.
- As a contributor, adding a parser backend should be possible through a
  documented adapter contract.
- As a maintainer, multiple backends should produce comparable IR outputs for
  evaluation.

### Scope

Must include:
- Ingestion capability model.
- Adapter interface and lifecycle hooks.
- Backend selection and fallback logic.
- At least three modes: graphify, richer parser path, and filesystem-lite
  fallback.

### Non-goals

- Building first-party deep parsers for every language.
- Hosted parsing infrastructure.
- Perfect parity across all backends.

### Functional requirements

1. NeuralMind must declare backend capabilities such as symbols, references,
   imports, calls, docs, and tests.
2. Users must be able to choose a backend explicitly or use automatic
   selection.
3. Partial parser outputs must still map into the same IR.
4. Backends must report confidence or coverage indicators.
5. Benchmark suites must compare backend outputs where applicable.

### Technical requirements

- Stable ingestion adapter API.
- Capability metadata in IR build records.
- Merge rules for partial graph contributions from multiple sources.
- Adapter author documentation and sample backend.

### Success metrics

- At least two independent backends produce valid IR for the same fixture
  repo.
- Users can build indexes on repos that fail or underperform with graphify
  alone.
- New language support lands as adapters rather than core rewrites.

### Risks

- Capability mismatches may make evaluation noisy.
- Merge logic across backends may be difficult to explain.
- Support burden grows with plugin surface area.

### Rollout

- Phase 1: Internal adapter interface.
- Phase 2: Graphify plus one alternate backend.
- Phase 3: Public plugin documentation.
- Phase 4: Community adapter ecosystem.

## PRD 8: Durable Team Memory Portability

### Problem

NeuralMind's learned synapses, transitions, and query patterns become more
valuable over time, but today that value is primarily local to one machine
and one working directory lifecycle. Teams, CI agents, and ephemeral
environments need a safe way to transfer useful non-code memory without
copying raw source material.

### Goal

Add portable, policy-aware memory bundles for exporting and importing learned
context.

### Users

- Teams standardizing coding workflows.
- Devcontainer or CI setups that need warm context quickly.
- Enterprises with local-only or air-gapped constraints.

### User stories

- As a team, a new machine should inherit useful project memory quickly.
- As an admin, exported memory should be inspectable and policy-controlled.
- As a CI operator, ephemeral coding agents should start with validated
  shared priors.

### Scope

Must include:
- Export/import of synapses, transitions, and query-pattern metadata.
- Redaction and policy controls.
- Signed or checksummed bundle manifests.
- Version compatibility checks.

### Non-goals

- Automatic cloud sync.
- Exporting raw code or embeddings by default.
- Consumer-style account identity features.

### Functional requirements

1. Users must be able to export selected memory namespaces into a portable
   bundle.
2. Import must validate version, checksum, and policy constraints.
3. Sensitive paths and identifiers must support redaction rules.
4. CI or container startup workflows must be able to hydrate from a bundle.
5. Inspection tooling must summarize bundle contents before import.

### Technical requirements

- Bundle manifest schema.
- Optional cryptographic signing or integrity verification.
- Namespace-aware export format.
- Compatibility logic across minor versions.

### Success metrics

- Fresh environments reach useful retrieval quality faster after import.
- Enterprises can review exactly what is exported.
- Import/export remains compatible across supported minor versions.

### Risks

- Over-redaction may reduce usefulness.
- Under-redaction may create policy concerns.
- Bundle semantics may become difficult to preserve as memory models evolve.

### Rollout

- Phase 1: Manual export/import for local use.
- Phase 2: Policy controls and inspection tooling.
- Phase 3: CI/devcontainer hydration support.
- Phase 4: Signed bundle workflows.

## PRD 9: Agent-Agnostic Orchestration Layer

### Problem

NeuralMind already works across several MCP clients and coding-agent
environments, but those client ecosystems will continue to change. The
durable asset is not any single hook implementation but a stable lifecycle
model for session priming, retrieval, edit observation, and next-context
prediction.

### Goal

Define a client-agnostic orchestration layer with stable lifecycle events and
thin adapters per agent environment.

### Users

- Maintainers supporting many coding-agent clients.
- Integration authors targeting new editors or runtimes.
- Teams avoiding lock-in to one agent UX.

### User stories

- As an integrator, a new coding agent should require only an adapter that
  maps its lifecycle into NeuralMind events.
- As a user, switching IDEs or agents should not cost learned memory value.
- As a maintainer, client-specific behavior should live at the edge rather
  than in the core.

### Scope

Must include:
- Formal lifecycle event model.
- Adapter contract for existing and future clients.
- Mapping of current Claude hooks, MCP tools, watcher signals, and UI events
  into that model.
- Integration documentation and conformance tests.

### Non-goals

- Replacing IDE-native interfaces.
- Owning a complete agent runtime.
- Standardizing every editor workflow.

### Functional requirements

1. Define events such as `session_start`, `pre_read`, `post_tool_use`,
   `post_edit`, and `pre_commit`.
2. Existing clients must be expressible through the new lifecycle contract.
3. Adapters must remain thin and avoid reimplementing retrieval logic.
4. Conformance tests must validate expected behavior across supported clients.
5. Documentation must describe the minimum viable adapter implementation.

### Technical requirements

- Stable event schema.
- Backward-compatible mapping for current MCP tools and hooks.
- Adapter test harness.
- Clear separation between lifecycle events and memory/index internals.

### Success metrics

- New client integrations require adapter work rather than core changes.
- Behavior parity improves across supported environments.
- Memory and compression value survives agent ecosystem churn.

### Risks

- Event taxonomy may be too abstract or too client-specific.
- Some clients may not expose enough lifecycle hooks.
- Adapter parity may lag fast-moving editors.

### Rollout

- Phase 1: Internal lifecycle model.
- Phase 2: Claude and generic MCP adapters.
- Phase 3: Cursor/Cline/Continue adapters.
- Phase 4: Public integration SDK and conformance suite.

## Prioritization

If only three initiatives are funded first, the best sequence is PRD 1,
PRD 2, and PRD 5. A versioned IR reduces architectural fragility, the quality
harness prevents silent retrieval regressions, and the daemon boundary turns
NeuralMind into stable local infrastructure instead of a loosely connected
set of modes and adapters.

The remaining work compounds on those decisions. Namespace-aware memory,
monorepo support, and portable team memory all become easier once schemas are
stable and runtime state is owned by a single service boundary.

## Suggested release gates

Every milestone should clear three gates before default rollout:

- **Schema compatibility gate:** migrations and rollback paths are verified.
- **Retrieval quality gate:** benchmark thresholds pass on representative
  suites.
- **Runtime stability gate:** watch, query, build, and adapter workflows pass
  under concurrency and upgrade scenarios.

Those gates align with the product's actual risk profile because NeuralMind's
value depends on durable project state, trustworthy retrieval, and smooth
operation across multiple client surfaces.
