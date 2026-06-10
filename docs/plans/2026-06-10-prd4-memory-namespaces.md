# Plan — PRD 4: Memory Namespaces & Branch Isolation

**Created:** 2026-06-10
**Status:** Design / ready-to-implement (own branch + PR, fresh session)
**Depends on:** v0.23.0 (PRD 1 IR, PRD 2 quality harness, PRD 3 traces, PRD 5
daemon) — branch from `main` after PR #217 merges.
**Owner seam:** `neuralmind/synapses.py` (the SQLite synapse store everything
learns into).

This is the concrete migration + design plan referenced by the PRD 4 handoff
prompt. It exists so the schema migration — the highest-risk part, because a
bug "could silently corrupt learned memory associations" — is worked out before
code is written.

---

## Why this needs care

The synapse store is the brain. Every query, hook activation, and watcher
batch reinforces it. Namespacing means the *same* node pair can carry
*different* learned weights in different namespaces (your `main` branch vs a
feature branch vs the shared team baseline). That changes the **primary keys**,
which SQLite cannot `ALTER` in place — so this is a table-rebuild migration,
not an `ADD COLUMN`. Get it wrong and a user loses months of learned memory.

## Current schema (v0 — pre-namespace)

From `neuralmind/synapses.py` `SCHEMA`:

```sql
synapses(node_a, node_b, weight, activation_count, last_activated, created_at,
         PRIMARY KEY (node_a, node_b), CHECK (node_a < node_b))
synapse_transitions(from_node, to_node, weight, count, last_activated,
         created_at, PRIMARY KEY (from_node, to_node), CHECK (from_node <> to_node))
node_activations(node_id PRIMARY KEY, activation_count, last_activated)
meta(key PRIMARY KEY, value)
```

There is currently **no** `meta` schema-version row; treat its absence as v0.

## Target schema (v1 — namespace-aware)

Add `namespace TEXT NOT NULL DEFAULT 'personal'` to the three data tables and
fold it into each primary key:

```sql
synapses(..., namespace TEXT NOT NULL DEFAULT 'personal',
         PRIMARY KEY (node_a, node_b, namespace), CHECK (node_a < node_b))
synapse_transitions(..., namespace TEXT NOT NULL DEFAULT 'personal',
         PRIMARY KEY (from_node, to_node, namespace), CHECK (from_node <> to_node))
node_activations(node_id, namespace TEXT NOT NULL DEFAULT 'personal',
         activation_count, last_activated, PRIMARY KEY (node_id, namespace))
meta(key, value)   -- unchanged; add row ('schema_version','1')
```

Add indexes that include `namespace` for the merged-read path:
`idx_syn_ns ON synapses(namespace, weight)`, similar for transitions.

**Namespace values:** `personal` (default/local), `shared` (team baseline,
importable), `branch:<name>` (per-git-branch), `ephemeral` (session-scoped,
fast-decay). Keep them plain strings — no enum table — so import/export and new
kinds stay trivial.

## Migration (v0 → v1), in `SynapseStore._init_schema` / a `_migrate()`

SQLite can't change a PK in place, so rebuild each data table:

1. Open; read `meta.schema_version` (absent ⇒ 0).
2. If 0 and the old tables exist, inside one transaction, per table:
   - `ALTER TABLE synapses RENAME TO synapses_v0;`
   - create the new `synapses` (v1 schema above);
   - `INSERT INTO synapses (node_a,node_b,weight,activation_count,last_activated,created_at,namespace) SELECT node_a,node_b,weight,activation_count,last_activated,created_at,'personal' FROM synapses_v0;`
   - `DROP TABLE synapses_v0;`
   - repeat for `synapse_transitions`, `node_activations`.
3. Recreate indexes; `INSERT OR REPLACE INTO meta VALUES ('schema_version','1')`.
4. Wrap in `BEGIN IMMEDIATE` … `COMMIT`; on any error `ROLLBACK` and raise — never leave a half-migrated db.

**Existing memory is preserved verbatim under `personal`** (the current
single-namespace behavior == the `personal` namespace, so nothing changes for
users who never touch namespaces).

**Mandatory test:** build a v0 db (old SCHEMA), insert known edges, open with
the new `SynapseStore`, assert (a) `schema_version==1`, (b) every old edge
present under `personal` with identical weight/count, (c) re-open is a no-op.
Keep it stdlib-only (the synapse tests already are).

## Namespace resolution (active namespace for writes)

`SynapseStore` write methods (`reinforce`, `record_sequence`, the activation
bump) gain `namespace: str | None = None`. When `None`, resolve via a small
helper in `core` (not in the stdlib-only store):

- config `neuralmind-backend.yaml` may pin `memory_namespace`;
- else if in a git repo and not on the default branch → `branch:<name>`;
- else `personal`.

Branch detection: best-effort `git -C <proj> rev-parse --abbrev-ref HEAD`
(mirror the existing `_maybe_detect_repo_url` subprocess pattern in `cli.py`;
5s timeout; degrade to `personal` on any failure / non-repo). The default
branch name (to treat as `personal`, not `branch:main`) comes from
`git symbolic-ref refs/remotes/origin/HEAD` or falls back to `main`/`master`.

Keep `SynapseStore` itself git-agnostic — it just takes a namespace string.

## Read / merge behavior

- `spread`, `neighbors`, `next_likely`, `edges`, `transitions`, `stats` gain
  `namespaces: list[str] | None` (None ⇒ merged default).
- **Merged default** (the recall path the selector uses): union edges across
  the active branch namespace + `personal` + `shared`, combining weights with
  explicit, documented constants:
  `merged_weight = w_branch*W_BRANCH + w_personal*W_PERSONAL + w_shared*W_SHARED`
  with `W_BRANCH > W_PERSONAL > W_SHARED` (e.g. 1.0 / 0.8 / 0.5) so recent
  branch-local context wins but shared priors still surface. Put the constants
  at module top with a comment — the PRD's #1 risk is "weighting hard to reason
  about."
- `ephemeral` is included in merged reads only for the current session.
- PRD 3 traces: add a `namespace_contribution` field to the synapse-boost trace
  event so `query --trace` shows which namespace drove a boost (the recall hook
  lives in `context_selector._boost_communities_from_synapses`, guarded on
  `self._trace`).

## Decay / TTL per namespace

Extend `decay()` to take per-namespace retention: `ephemeral` decays fast (or
is cleared on session end / daemon shutdown), `branch:*` decays normally,
`shared` is sticky. Represent policy as a `{namespace_prefix: half_life}` map
with sane defaults; document it.

## CLI surface (Phase 2)

- `neuralmind memory inspect [--namespace N] [--json]` — counts/weights per
  namespace (also fold into `stats`: contribution by namespace).
- `neuralmind memory reset --namespace N` — clear ONE namespace without
  touching the project index or other namespaces.
- `neuralmind memory export --namespace N [-o file]` — portable JSON bundle
  reusing the `IRSynapse` shape (`neuralmind/ir.py` `synapses_from_edges`);
  versioned manifest (this is the PRD 8 on-ramp).
- `neuralmind memory import <file> [--namespace N]` — validate version +
  merge into target namespace.
- Namespace flag on `next` / `query` recall where meaningful.

## Rollout (ship Phase 1–2 in the PR; note 3–4)

1. **Phase 1** — internal namespace tagging + the v0→v1 migration (default
   everything to `personal`; no behavior change). 
2. **Phase 2** — CLI controls + stats-by-namespace + branch resolution.
3. **Phase 3** — default merged read mode on.
4. **Phase 4** — shared-memory export/import bundles.

## Test plan (stdlib-only)

- Migration: v0 db → v1, no data loss, idempotent re-open (mandatory).
- Namespaced `reinforce`/`record_sequence` write under the right namespace;
  isolation (a `branch:x` edge doesn't appear in `branch:y`).
- Merged read weighting (branch > personal > shared) with explicit fixtures.
- `reset --namespace` clears one, leaves others + index intact.
- Per-namespace decay (ephemeral fast, shared sticky).
- export → import round-trip (+ version/`checksum` validation).
- Branch resolution with `git` mocked (repo on feature branch → `branch:x`;
  default branch → `personal`; non-repo → `personal`).

## Risks & mitigations

- **Memory corruption on migrate** → single transaction, rollback-on-error,
  the mandatory no-data-loss test, and keep the rename’d `*_v0` table only
  until commit.
- **Weighting opacity** → explicit named constants + a trace field showing
  per-namespace contribution.
- **Branch-detection edge cases** (detached HEAD, worktrees, no remote) →
  best-effort with a `personal` fallback; never fail a write because git is
  weird.
- **Daemon concurrency** (PRD 5) → keep writes under the per-project lock; the
  store is already opened per process.

## Out of scope (PRD 4)

Identity/RBAC, cloud sync, multi-tenant hosted storage. Signed bundles and
CI/devcontainer hydration are PRD 8.
