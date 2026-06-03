# NeuralMind — Next-Release Plan & Feature Map

**Status:** Proposed · **Owner:** Project-Manager agent · **Horizon:** v0.13 → v0.16
**Supersedes the relevant parts of:** `docs/FUTURE-PROOFING-PLAN.md` (see "Why this
replaces the old plan" below). **Reads alongside:** `ROADMAP.md`,
`docs/HONEST-ASSESSMENT.md`.

This is the document the PM agent owns and the agent team executes against. It
turns a strategy decision ("both audiences, staged; focus on evals, graphify
decoupling, host resilience, and proactive/cross-agent memory") into a sequenced,
parallelizable feature map with acceptance criteria and suggested agent roles.

---

## 0. The decision this plan encodes

| Question | Decision | Consequence for this plan |
|---|---|---|
| Primary user | **Both, staged** | Local-first core quality **first**; enterprise lane runs **behind** it, gated on real multi-user demand. |
| Focus pillars | **All four**: evals · decouple graphify · host resilience · proactive/cross-agent memory | Sequenced across four releases, not crammed into one. |
| Shared/team memory | **Undecided — argue both** | A dedicated decision gate (§6). It is the *fork* that determines whether the enterprise lane is even coherent. |

**One-line strategy:** *Prove the memory makes answers better, then make the
pipeline that produces it swappable and durable, then make the memory proactive
and portable. Enterprise readiness is a consequence of those, not a parallel
investment.*

---

## 1. Why this replaces the old plan

`docs/FUTURE-PROOFING-PLAN.md` is an enterprise-readiness checklist (SOC 2, RBAC,
SAML/OAuth, FIPS 140-2, encrypt-at-rest, Spark/Dask, seven named "Teams"). Two
problems for a 100%-local, per-project, solo/small-team tool:

1. **Threat-model mismatch.** "Encrypt queries in transit (TLS)", "SAML for the
   MCP server", and "encrypt index at rest" are mostly the OS's job for a
   localhost process. They add surface area without protecting a real attack path
   *until there is a multi-user surface* — which only **shared memory** (§6)
   would create.
2. **Effort mismatch.** It assumes an org headcount the project doesn't have, and
   it spends scarce effort on compliance theater instead of the core retrieval
   quality that `HONEST-ASSESSMENT.md` says actually determines whether anyone
   keeps NeuralMind installed.

What the old plan got *right* and we keep: dependency pinning + compatibility
matrix (§5 of the old doc), benchmark regression gating (already shipped), and
secret-scanning of indexed code (folds into v0.13 as a small, honest, local-first
win). Everything else is **deferred behind the shared-memory decision**, not
cancelled.

---

## 2. The release arc (themes)

| Release | Theme | One sentence | Pillar |
|---|---|---|---|
| **v0.13** | **Measure** | An eval harness that proves memory makes answers *better*, not just shorter — the fitness function everything else depends on. | Retrieval/faithfulness evals |
| **v0.14** | **Decouple** | A `GraphSource` adapter so tree-sitter / LSP / SCIP / ctags can feed the pipeline, proven at parity by the v0.13 harness. | Decouple from graphify |
| **v0.15** | **Endure** | A host-capabilities adapter + integration-contract tests so a Claude Code hook / MCP spec change is one adapter swap, not a rewrite. | Host-dependency resilience |
| **v0.16** | **Anticipate** | Promote directional "what comes next" to a first-class agent surface and ship a portable, cross-agent memory format. | Proactive/cross-agent memory |
| **Enterprise lane** | **Earn it** | A thin, honest compliance slice that only ships items that fit local-first; the rest waits on the §6 fork. | Staged enterprise |

**Why this order is not arbitrary:** evals come first because *you cannot safely
refactor graph ingestion (v0.14) or tune the synapse layer (#156) without a
fitness function that catches quality regressions.* Measure → change → measure.

---

## 3. v0.13 "Measure" — detailed feature map (the immediate next release)

**Release goal:** Ship a reproducible, CI-gated evaluation harness that answers the
question `HONEST-ASSESSMENT.md` flags as unanswered: *"Does the agent's answer get
better with NeuralMind context, or just shorter?"* — plus the polyglot fixtures
that make every downstream quality claim non-Python-only.

**Definition of done for the release:** `neuralmind eval .` produces a
faithfulness + retrieval-quality report; CI gates regressions the way
`ci-benchmark.yml` already gates token reduction; TS and Go fixtures exist; the
metrics are exposed in a stable shape the future self-improvement engine (#156)
can read as a fitness function.

### Epic E1 — Faithfulness eval harness
*Suggested role: eval-engineer (lead) · retrieval-engineer (support)*

| Task | Detail | Acceptance |
|---|---|---|
| E1.1 Query+gold set | Extend `tests/benchmark/benchmark_queries.json` (or new `evals/faithfulness/`) with N≥20 queries that have rubric-style gold answers (key facts the answer must contain), not just gold *modules*. | A versioned query set with per-query expected-fact lists. |
| E1.2 A/B answer generation | For each query, generate an answer **with** NeuralMind context vs **without** (naive baseline). Pluggable answerer. | Two answer sets produced deterministically given a fixed answerer. |
| E1.3 Judge — two modes | **Offline mode (default, local-first):** heuristic scoring — expected-fact recall, citation/grounding rate, contradiction check. **API mode (opt-in):** LLM-as-judge for nuanced scoring, clearly flagged as leaving the machine. | Offline mode runs with zero network. API mode is opt-in via env var and documented as non-local. |
| E1.4 Report | `neuralmind eval` prints faithfulness delta (with vs without), grounding rate, and per-query breakdown; `--json` for machines. | Stable schema; mirrors `doctor --json` ergonomics. |

> **Local-first tension to resolve in E1.3 (flag for PM):** a good faithfulness
> judge usually wants a strong LLM, which conflicts with the 100%-local promise.
> Resolution baked in above: ship a real *offline heuristic* judge as the default
> and gating signal; make the API judge strictly opt-in and labelled. Do **not**
> let the eval quietly phone home — that would contradict the headline claim.

### Epic E2 — Retrieval quality beyond token reduction (polyglot)
*Suggested role: retrieval-engineer (lead)*

| Task | Detail | Acceptance |
|---|---|---|
| E2.1 Promote top-k metric | Lift the existing top-k hit-rate measurement (currently ~71.7% / 83.3% with synapses on the Python fixture) into the eval harness as a first-class, reported metric. | Hit-rate reported by `neuralmind eval`, not buried in `tests/benchmark`. |
| E2.2 TypeScript fixture | Add `tests/fixtures/sample_project_ts/` with a built graph + query set, mirroring the Python fixture shape. | TS numbers appear in the report and CI. |
| E2.3 Go fixture | Same for Go. | Go numbers appear in the report and CI. |
| E2.4 Per-language report | Report breaks quality out per language so the "Python-strong, polyglot-weaker" reality is *visible and tracked*, not just disclosed in prose. | Per-language table in `eval --json`. |

### Epic E3 — CI gating + regression tracking
*Suggested role: platform/devops-engineer (lead)*

| Task | Detail | Acceptance |
|---|---|---|
| E3.1 CI workflow | New (or extended) workflow modeled on `ci-benchmark.yml` that runs the offline eval and fails on >X% faithfulness/hit-rate regression vs baseline. | Red build on a deliberate quality regression; baseline stored like the token baseline. |
| E3.2 Sticky PR comment | Post eval deltas as a sticky comment on PRs, same pattern as the benchmark comment. | Every PR shows faithfulness + hit-rate deltas. |

### Epic E4 — Fitness-function hook for self-improvement (#156)
*Suggested role: eval-engineer + retrieval-engineer*

| Task | Detail | Acceptance |
|---|---|---|
| E4.1 Stable metrics API | Expose the eval metrics through a stable function/JSON the future auto-tuner can call as a fitness function (the thing #156 says it needs). | #156's "subsystem C eval-driven" has a concrete API to target. |

### Cross-cutting (every release) — the CLAUDE.md docs + SEO checklist
*Suggested role: docs-engineer*

Per `CLAUDE.md`, every user-facing change ships docs across **all five surfaces**
in the *same PR* and refreshes SEO: `RELEASE_NOTES_v0.13.0.md`, `README.md` banner
+ history demotion + release table, `docs/index.html`, `docs/about.html`
("What's New"), `docs/wiki/CLI-Reference.md` (the new `eval` command + any env
vars like the opt-in judge flag), and a `docs/use-cases/*` walkthrough ("proving
retrieval quality on your repo"). Add `pyproject.toml` keywords
(`retrieval-eval`, `faithfulness`, `answer-quality`) and `docs/sitemap.xml`
entries. **Do not edit `CHANGELOG.md`** — release-please owns it.

### v0.13 parallelization map
- **Wave 1 (parallel):** E1.1 (query/gold set) ‖ E2.2/E2.3 (TS/Go fixtures) — independent.
- **Wave 2:** E1.2→E1.3→E1.4 (depends on E1.1) ‖ E2.1/E2.4 (depends on fixtures).
- **Wave 3:** E3 (depends on a runnable `eval`) → E4 (depends on stable metrics) → docs/SEO.

---

## 4. v0.14–v0.16 — lighter maps (sequenced, re-detailed when they become "next")

### v0.14 "Decouple" — graph-source adapters
*Roles: retrieval-engineer (lead) · platform-engineer*
- **Problem:** `graphify-out/graph.json` is hardcoded in ~10 sites (`embedder.py:49`,
  `doctor.py:49`, `compressors.py:235`, `core.py:281`, `watcher.py`, …); retrieval
  quality = graphify quality = tree-sitter coverage; graphify is a single
  maintainer-owned dependency.
- **Move:** introduce a `GraphSource` ABC (mirror the existing `EmbeddingBackend`
  ABC pattern in `embedding_backend.py`). graphify becomes the default adapter;
  add a second adapter (direct tree-sitter or LSP/SCIP). Centralize the
  `graphify-out/graph.json` path behind the abstraction.
- **Gate:** v0.13 eval harness must show the new adapter at **parity or better** on
  the fixtures before it ships. This is *why evals come first.*
- **Stretch:** a non-graph fallback so a repo with zero graph still gets degraded-
  but-useful retrieval (closes a first-run cliff).

### v0.15 "Endure" — host-dependency resilience
*Roles: platform-engineer (lead) · integration-engineer*
- **Problem:** the headline value ("agent boots with memory, no tool call") depends
  on Claude Code's hook API + `SYNAPSE_MEMORY.md` auto-load + the MCP spec — all
  moving targets the project doesn't control. `HONEST-ASSESSMENT.md` already
  concedes "the baseline keeps moving."
- **Move:** (1) a thin host-capabilities adapter so each host's hook/memory
  injection path is one module; (2) **integration-contract tests** that pin
  against each host's real behavior (Claude Code settings.json hook schema, MCP
  tool-call shape) and fail loudly when an upstream contract drifts; (3) a
  documented "native memory landed upstream — here's where NeuralMind still adds
  value" positioning, so a Claude Code native-memory release is a *narrative we
  control*, not a surprise.

### v0.16 "Anticipate" — proactive + cross-agent memory
*Roles: retrieval-engineer (lead) · docs-engineer*
- **Proactive:** promote `neuralmind next` / `neuralmind_next_likely` (the v0.11
  directional-transition surface — your most novel capability) from CLI/MCP
  afterthought to a first-class, surfaced workflow ("after X you usually touch
  Y/Z — want me to?"). Tune the transition signal (`TRANSITION_*` constants in
  `synapses.py`) against the v0.13 eval harness.
- **Cross-agent portability:** define a portable memory export/import format so one
  learned synapse map serves Claude Code + Cursor + Cline + Continue. This is the
  durable wedge: **no single host will build cross-host memory**, because each only
  optimizes itself.

---

## 5. Enterprise lane (staged, behind the fork)

Ships **only** the slices that are coherent for a local-first tool, and only when
they ride on something else:
- **v0.13:** secret-scanning of indexed code (block API keys/secrets from being
  embedded) — small, honest, protects a real local risk. Folds into the eval/build
  path.
- **Deferred behind §6:** RBAC, SAML/OAuth, TLS, encrypt-at-rest, 7-year audit
  retention, FIPS. These only make sense once there is a **multi-user surface**,
  which only shared memory creates. Building them before that is the mismatch §1
  describes.
- **Keep regardless:** dependency pinning + compatibility matrix, SBOM (shipped),
  signed releases.

---

## 6. Decision gate — committable team/shared memory (argue both)

This is the fork that decides whether the enterprise lane is real. Resolve it
**before v0.16** (it changes the portable-format design) and **before any further
enterprise investment.**

### The case FOR (it could be the biggest differentiator)
- **No host will build it.** Cross-developer shared memory is exactly the gap
  native agent memory (Claude's memory tool, Cursor's, etc.) will *not* fill —
  they're per-user. That's a durable niche.
- **It stays local-first.** A git-committed, human-reviewable `SYNAPSE_MEMORY.md` /
  synapse export means the team's learned map of the codebase travels in the repo,
  reviewed in PRs — **no SaaS, no server, no exfiltration.** Consistent with the
  headline promise.
- **It compounds onboarding value.** "New hire's agent boots with the team's
  accumulated map of what-goes-with-what" is a concrete, searchable workflow and a
  strong enterprise story *without* a hosted backend.
- **It's the honest trigger for the enterprise lane.** Multi-user shared memory is
  what finally makes RBAC/audit/secret-scanning *non-theater* — now there's a real
  multi-writer surface to govern.

### The case AGAINST (keep it strictly per-developer)
- **Privacy/leakage.** Synapses encode *how individuals work* (edit sequences,
  query intent). Committing that to a shared repo can leak sensitive workflow
  patterns or in-progress direction; "the team's brain" can become surveillance.
- **Merge/decay semantics are hard.** Hebbian weights + LTP + directional
  transitions don't merge cleanly across people; whose decay clock wins? A naive
  union produces a muddy average that's worse than any individual's map.
- **Scope creep toward the SaaS the project explicitly rejected.** Shared state is
  the on-ramp to "just host it for us," which `ROADMAP.md` lists as out of scope.
  Saying yes here is a strategic commitment, not a feature.
- **Quality dilution.** Per-developer memory is sharp because it's personal; shared
  memory optimizes for the team-average codebase tour, which may help nobody
  specifically.

### Recommended framing for the decision
Treat it as **opt-in, additive, and read-mostly**: a *committed, reviewed*
team-baseline synapse layer that a developer's personal (uncommitted) layer
**overlays**, never replaces. Personal stays sharp and private; team baseline is
explicit, diffable, and decays on its own clock. If the team chooses this shape,
it resolves most of the "against" points and turns the enterprise lane on
honestly. **PM action:** put this to the maintainer as a yes/no/shape decision,
with this section as the brief.

---

## 7. How else to think about this (meta — for the PM agent)

1. **Measure → change → measure is the spine.** The single highest-leverage thing
   this project lacks is a *fitness function for answer quality.* Once it exists,
   every other change (graphify swap, synapse tuning, host adapters, even
   marketing claims) becomes safe and self-justifying. This is why v0.13 is first.
2. **The synapse layer is the product; the vector-RAG half is commodity.** Defend
   and deepen the part nobody else has (Hebbian + LTP + directional transitions).
   Treat the embedding/retrieval half as swappable plumbing — which the
   `EmbeddingBackend` ABC already acknowledges.
3. **Your durable niche is the seam between hosts, not inside one.** Cross-agent
   portable memory and host-contract resilience are bets that *the ecosystem
   stays fragmented* — a safe bet. Anything that competes head-on with a single
   host's native memory is a bet you'll lose on their timeline.
4. **Protect the honesty asset.** `HONEST-ASSESSMENT.md` is a competitive
   advantage, not a liability. Every release should be able to update it with
   *measured* numbers (which v0.13 makes possible). Never let the
   docs+SEO checklist's marketing energy outrun the measured reality.
5. **Watch the effort ratio.** A large share of recent energy goes to
   docs/SEO/marketing surfaces (the CLAUDE.md checklist is enormous). Keep a
   running ratio of core-quality commits vs surface commits; if surfaces are
   winning, the product stops improving while looking like it is.
6. **Re-detail just-in-time.** Only v0.13 is fully specced here on purpose.
   v0.14–v0.16 get re-detailed when they become "next," using whatever the v0.13
   eval harness taught us. Plans decay like synapses — refresh on activation.

---

## 8. Agent-team operating model

- **Project-Manager agent** owns this doc, sequences the waves in §3, and runs the
  §6 decision gate with the maintainer. Keeps a status checklist per epic.
- **Sub-agents** map to the suggested roles (eval-engineer, retrieval-engineer,
  platform/devops-engineer, integration-engineer, docs-engineer). Wave-1 tasks in
  §3 are independent and should be dispatched in parallel.
- **Release mechanics** (unchanged, per `CLAUDE.md`): land work as `feat:` commits
  → release-please opens the version PR (bumps `pyproject.toml`,
  `.release-please-manifest.json`, writes `CHANGELOG.md`) → merge tags the release
  → PyPI + GHCR publish. Never bump versions or edit `CHANGELOG.md` by hand. Docs +
  SEO ship in the *same PR* as the feature.
- **Every PR** must keep the token-reduction benchmark green (existing gate) and,
  from v0.13 on, the new eval gate.
