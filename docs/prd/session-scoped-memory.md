# PRD: Session-scoped memory — namespaces for orchestrated agents

**Status:** Draft · **Owner:** dfrostar · **Created:** 2026-07-20 · **Updated:** 2026-07-21
**Tracking branch:** claude/session-identity-namespaces
**Target:** v1.3.0 (Wave 5) · **Origin:** Discussion #1 — ofekron (Better Agent)

---

## 1. Background & strategic motivation

Multi-agent orchestration is where coding agents are heading: a parent session delegates to workers (possibly different providers — Claude, Codex, Gemini), often in parallel git worktrees. Supervisors like Better Agent need memory scoping NeuralMind is almost shaped for:

> "If a delegated Codex worker discovers a test command in a feature worktree, I want that fact available to its parent immediately, inherited by another worker on the same branch, but not promoted to shared project memory until the branch merges or a human approves it."

The existing namespace ladder (`ephemeral` → `branch:<name>` → `personal` → `shared`, PRD 4) plus the human-gated team-memory publish flow (PRD 8) already model the top of that lifecycle. Two gaps block the bottom:

1. **Worktrees don't share memory.** The store is keyed by directory (`<project>/.neuralmind/synapses.db`), and a git worktree is a different directory — so two worktrees on the same branch have separate stores, and "same branch inherits the same memory" silently fails in exactly the parallel-worktree setups orchestrators create.
2. **No per-worker scope.** A delegated worker writes to the same branch namespace as everyone else on the branch. There is no scratch scope a worker learns into that a parent can inspect, then deliberately promote or discard.

**Positioning:** this makes NeuralMind the memory substrate designed for multi-agent orchestration — a lifecycle (session → branch → shared) where every hop is explicit and gated, which no static-index competitor models at all. It also answers a real integrator asking to build on us.

---

## 2. What already exists (the on-ramp)

| Primitive | Location | Status |
|-----------|----------|--------|
| Namespace resolution (`NEURALMIND_NAMESPACE` → config → `branch:<name>` → `personal`) | `core.py:217-241` (via `ns_mod.resolve_namespace`) | **SHIPPED** |
| Per-namespace decay policy (`ephemeral` fast-decay, no LTP floor, cleared at session boundary) | `synapses.py:85,152-157,732-834` | **SHIPPED** |
| Merged reads (active + personal 0.8× + shared 0.5×) | `synapses.py:88-106,522` | **SHIPPED** |
| `head_fingerprint()` for cache invalidation on branch switch | `core.py:235-240` (via `ns_mod.head_fingerprint`) | **SHIPPED** |
| WAL journal mode + busy timeout | `synapses.py:356-362` (`PRAGMA journal_mode=WAL`, `synchronous=NORMAL`, 30s timeout) | **SHIPPED** |
| `SynapseStore.import_edges()` / `import_transitions()` | `synapses.py:1537-1620` | **SHIPPED** |
| `SynapseStore.clear_namespace()` for GC | `synapses.py:1494-1520` | **SHIPPED** |
| `NEURALMIND_NAMESPACE` env override | `core.py:222` | **SHIPPED** |

**What does NOT exist yet (greenfield):**

| Primitive | Location | Status |
|-----------|----------|--------|
| `resolve_state_root()` — worktree-aware state dir resolution | `synapses.py:1626` (`default_db_path` is naive) | **NOT BUILT** |
| `session:<id>` namespace prefix + decay class | — | **NOT BUILT** |
| `promote_namespace()` API + CLI + MCP tool | — | **NOT BUILT** |
| `NEURALMIND_SESSION_SCOPE=1` env var | — | **NOT BUILT** |
| `CLAUDE_SESSION_ID` session stamping | — | **NOT BUILT** |
| Legacy per-worktree DB migration (MAX-merge → shared) | — | **NOT BUILT** |
| Bundle export/import (`export_synapse_bundle` / `import_synapse_bundle`) | — | **NOT BUILT** (use `import_edges`/`import_transitions` instead) |

**Note:** The original PRD referenced `namespaces.py`, `memory.py`, and `ir.py` as if they were separate files. As of v1.1.1, namespace resolution lives in `core.py` (via `ns_mod`), session identity is not yet file-level, and bundle machinery is `SynapseStore.import_edges`/`import_transitions`. This PRD has been updated to reflect actual file locations.

---

## 3. The gap (what v1.3.0 / Wave 5 adds)

### Part A — worktree-shared store

Resolve the state directory through the git common dir so every worktree of a repo opens the same `synapses.db`, with namespaces — not directories — providing isolation.

### Part B — `session:<id>` namespaces + explicit promotion

A per-worker scratch scope with ephemeral-style decay, plus a `neuralmind memory promote` command that MAX-merges a session scope into the branch scope. Completes the lifecycle:

```
session:<id>  ──promote (parent/orchestrator decision)──▶  branch:<name>
branch:<name> ──publish + PR review + merge (PRD 8)────▶  shared
```

Every hop is explicit. Nothing is ever auto-promoted.

---

## 4. Goals / non-goals

### Goals

1. Two sessions in different worktrees of the same repo, same branch, read and write the same branch memory with zero configuration.
2. An orchestrator can scope a worker with one env var, inspect what it learned as a unit, and promote or discard that unit with one command.
3. Session scopes are self-cleaning (fast decay + age-based GC) — an abandoned worker never leaves permanent residue.
4. Everything stays stdlib-only on the hook path, fail-open, and 100% local. Cross-provider by construction (env vars + CLI, no SDK).

### Non-goals

- Per-edge session provenance. A Hebbian weight is an aggregate; per-edge attribution would turn a compact weight into an event log. "Who learned what" at session granularity stays in the orchestration layer above.
- Automatic promotion on branch merge. Promotion is a decision, not a side effect.
- A session registry inside NeuralMind. Resolution stays place-based; identity enters only via explicit pinning.
- Changing PRD 8's branch→shared flow, core synapse math, or the merged-read weights of existing namespaces.
- Network sync / cross-repo scopes.

---

## 5. Design

### 5.1 Part A — worktree-shared store

**New resolver:** `resolve_state_root(project_path: Path) -> Path` (in `synapses.py`, replacing `default_db_path`, reusing `head_fingerprint`'s gitdir: pointer-following logic from `ns_mod`):

1. If `<project>/.git` is a **file** (worktree), follow `gitdir:` to `<main>/.git/worktrees/<name>`; strip the `worktrees/<name>` suffix to get the common git dir; its parent is the main working tree. Return `<main working tree>/.neuralmind`.
2. If `.git` is a directory or absent (normal checkout, non-repo, bare repo, any parse failure): return `<project>/.neuralmind` — exactly today's behavior. Fail-open, no subprocess, microsecond file read.

**Callers:** `default_db_path()` delegates to `resolve_state_root()`. `core.py:264` (`SynapseStore` construction) uses `default_db_path(self.project_path)` — no change needed there.

**Env opt-out:** `NEURALMIND_WORKTREE_SHARED=0` restores per-directory stores (for deliberate isolation experiments).

**Concurrency.** WAL already enabled (`synapses.py:358`). Writes are short transactions. The existing 30s busy timeout (`synapses.py:356`) handles cross-process contention. No change needed.

**Migration.** First time a worktree resolves to the shared store while a legacy `<worktree>/.neuralmind/synapses.db` exists:
- Open legacy store, read all edges/transitions grouped by namespace
- `import_edges()` / `import_transitions()` into shared store (MAX-merge via existing `SynapseStore` methods)
- Rename legacy DB to `synapses.db.migrated` so merge runs exactly once
- Fail-open: any error leaves legacy file untouched, uses shared store fresh

**Edge case — two divergent legacy stores:** When worktree B starts after worktree A already migrated, both legacy stores merge into the same shared store. MAX-merge handles weight conflicts correctly (higher weight wins). Metadata (`added_at`, `last_active_at`) is per-edge in the legacy store; migration preserves the most recent value per edge. Documented as acceptable: decay erodes stale weights.

**Namespace resolution interaction.** None needed — `core.py:235` already derives `branch:<name>` from the worktree's checkout via `ns_mod.head_fingerprint`. The store is shared; the namespace still reflects the branch that worktree has checked out.

### 5.2 Part B — session namespaces

**Convention.** `SESSION_NAMESPACE_PREFIX = "session:"` in `synapses.py`, parallel to `BRANCH_NAMESPACE_PREFIX`. A session namespace is **never auto-resolved** — it is only ever entered by explicit pinning:

- `NEURALMIND_NAMESPACE=session:<id>` — orchestrator assigns the scope (works for any provider; it's just an env var), OR
- `NEURALMIND_SESSION_SCOPE=1` — convenience: derive `session:<CLAUDE_SESSION_ID>` (falling back to a process UUID). Lets a user scope a single Claude Code session without knowing its id in advance.

**Resolution order becomes:** `NEURALMIND_NAMESPACE` → `NEURALMIND_SESSION_SCOPE` → pinned config → `branch` → `personal`.

**Decay class.** Session namespaces get ephemeral's treatment — fast decay rate, no LTP floor — via a prefix match in the decay tick (any `session:*` namespace uses `EPHEMERAL_DECAY_RATE` / `EPHEMERAL_TRANSITION_DECAY_RATE`). Unlike `ephemeral` they are **not** cleared at session boundaries (a parent must be able to harvest after the worker exits); instead, age-based GC (below) bounds them.

**Merged reads while session-scoped.** Today the merged view is `active + personal + shared` (`synapses.py:522`). When the active namespace is `session:*`, also merge the current branch namespace (resolved from git as usual) at `W_PERSONAL` (0.8×) — so a scoped worker still reads everything a branch-scoped worker would (branch + personal + shared), while its writes land only in its own scope. This is what makes "inherited by another worker on the same branch" true even while workers are individually scoped.

**Promotion.** New Python API + CLI + MCP tool:

- `SynapseStore.promote_namespace(src, dst, min_weight=0.0, clear=False) -> dict` — reads edges from `src` filtered by `min_weight`, `import_edges()` into `dst` (MAX-merge, so promotion can only raise weights and re-promotion is idempotent), optionally `clear(src)`. Returns `{"promoted": N, "raised": M, "new": K, "unchanged": U}` — the parent learns "did this worker discover anything new."
- `neuralmind memory promote --from session:<id> [--to branch:<name>] [--min-weight W] [--clear]` — `--to` defaults to the current branch namespace (or `personal` off-branch). Refuses `--to shared` with a pointer to `memory publish` (PRD 8 owns that hop, human-gated).
- MCP tool `neuralmind_memory_promote` with the same parameters, so a parent agent can harvest a worker without shelling out.
- `neuralmind memory inspect --namespace session:<id>` — already shows a scope's contents via `SynapseStore.stats()` / `edges()`; document it as the pre-promotion review.

**GC.** The decay tick records a `last_write` timestamp per namespace (meta table). Any `session:*` namespace idle longer than `NEURALMIND_SESSION_TTL_DAYS` (default 7) is cleared outright via existing `clear_namespace()`. Also `neuralmind memory reset session:<id>` discards one worker explicitly — the "worker's findings rejected" path.

**GC interaction with existing decay.** `team_staleness.py` handles team-edge decay. Session GC layers on top: the decay tick checks namespace prefix generically (`session:*`) rather than special-casing. No conflict — `team_staleness` operates on `shared` namespace edges; session GC operates on `session:*` namespaces.

### 5.3 The orchestrator contract (the Better Agent story)

```bash
# parent spawns a worker into a feature worktree, scoped:
NEURALMIND_NAMESPACE=session:worker-7 codex run ...

# worker learns; writes land in session:worker-7; reads see
# branch + personal + shared (shared store spans worktrees — Part A)

# parent reviews what the worker learned, as a unit:
neuralmind memory inspect --namespace session:worker-7

# parent accepts → same-branch workers inherit immediately:
neuralmind memory promote --from session:worker-7   # → branch:<feature>

# ...or rejects:
neuralmind memory reset session:worker-7

# branch merges + human approves → team inherits (PRD 8, unchanged):
neuralmind memory publish   # → committed bundle → PR → shared
```

---

## 6. Acceptance criteria

- [ ] Two worktrees of one repo resolve to the same `synapses.db` (main working tree's `.neuralmind/`); a write in worktree A is readable in worktree B with no configuration (test uses a real `git worktree add`).
- [ ] Non-repo, bare-repo, and unparsable-`.git` paths fall back to the per-directory store; `NEURALMIND_WORKTREE_SHARED=0` forces the fallback. Resolver is stdlib-only, no subprocess, never raises.
- [ ] Legacy per-worktree DB is MAX-merged into the shared store exactly once, then renamed; corrupt legacy DB is skipped fail-open.
- [ ] Concurrent writes from two processes (two worktrees) succeed (WAL + 30s busy timeout already enabled; stress test in `tests/`, stdlib-only).
- [ ] `NEURALMIND_NAMESPACE=session:x` scopes writes to `session:x` while merged reads include current branch + personal + shared; `NEURALMIND_SESSION_SCOPE=1` derives the id from `CLAUDE_SESSION_ID` (falls back to process UUID).
- [ ] `session:*` namespaces decay at ephemeral rates, survive session boundaries, and are GC'd after `NEURALMIND_SESSION_TTL_DAYS` idle (default 7).
- [ ] `memory promote` MAX-merges `--from` into `--to` (default: current branch namespace), honors `--min-weight`/`--clear`, is idempotent, returns counts, and refuses `--to shared` with a `memory publish` pointer. Exposed as an MCP tool.
- [ ] All other namespaces and PRD 8 behavior are byte-for-byte unchanged when no session scope or worktree is involved (regression suite green).
- [ ] Docs + SEO propagated per the shipping checklist: release notes with the per-agent expectations table, README, both HTML pages, CLI-Reference (`memory promote`, four new env vars), a new use-case walkthrough ("Scoped memory for multi-agent orchestration" — parent/worker/worktree lifecycle), `pyproject.toml` keywords (`multi-agent-memory`, `agent-orchestration`, `session-scoped-memory`, `git-worktree-memory`), sitemap.

---

## 7. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| SQLite contention across parallel sessions | WAL + existing 30s busy timeout + short transactions; opt-out env restores per-directory stores; stress test in CI. |
| Shared-store migration merges junk from a stale worktree DB | MAX-merge only raises asserted pairs; decay erodes them; migration renames the source so it runs once; `memory reset` per namespace remains. |
| Session-namespace proliferation bloats the store | Fast decay + prune, 7-day idle GC, `--clear` on promote, explicit `memory reset`. |
| Orchestrators promote garbage into branch scope | `--min-weight` filters unconsolidated edges; branch scope itself decays; promotion never touches shared (that hop stays human-gated behind PRD 8). |
| A worker reads another worker's scratch | Can't by default: merged reads include branch/personal/shared, never other `session:*` scopes. Cross-session reads require an explicit pinned `--namespace`. |
| Same-id collision (two workers pinned to one session id) | Documented as intentional: the orchestrator owns id assignment; sharing an id is sharing a scope. |
| Two divergent legacy stores merge into shared | MAX-merge handles weight conflicts; metadata (`added_at`, `last_active_at`) preserved per-edge from whichever legacy store has the most recent value. Decay erodes stale weights. |

---

## 8. Rollout

Single `feat:` PR → release-please cuts v1.3.0. Part A is a silent correctness fix worth its own headline line; Part B is the release headline: **"memory scopes for agent orchestrators — session → branch → shared, every promotion explicit."**

Reply on Discussion #1 linking the release + the new use-case walkthrough, closing the loop with Better Agent as the first named integrator.

---

## 9. Success metric

An orchestrator can run the §5.3 contract end-to-end with env vars and two CLI commands, on any provider, with zero NeuralMind-side session registry: a worker's discovery is visible to its parent immediately (shared store), inherited on the same branch after one explicit promote, and reaches shared only through the existing human-gated publish. Better Agent integrating against this — and not needing a fork or a sidecar database to do it — is the concrete proof.

---

## 10. Wave placement

**Confirmed for Wave 5.** Rationale:
- Wave 4 closes the self-improvement loop (C4 tuner promotion) and completes quality harness (D3/D4) — these are on the critical path for "product that improves itself."
- Session-scoped memory is a **force multiplier** — it makes multi-agent orchestration work correctly, but it's not on the critical path for the learning loop.
- Wave 5 is the natural home: after the tuner can promote/rollback (C4), session-scoped learning feeds it better data.

---

*PRD v2.0. Updated 2026-07-21 to reflect actual v1.1.1 codebase state. Original draft from 2026-07-20.*
