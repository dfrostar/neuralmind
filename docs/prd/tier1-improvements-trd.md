# TRD: Tier 1 Improvements — technical design

**Status:** Build-ready · **Owner:** dfrostar · **Created:** 2026-07-17
**Companion:** `docs/prd/tier1-improvements-brd.md`
**Target:** v0.46.0

---

## 1. Component 1 — Structural edges table

### 1.1 Schema change (`synapses.py`)

Add one table to `SCHEMA`:

```sql
CREATE TABLE IF NOT EXISTS structural_edges (
    caller TEXT NOT NULL,
    callee TEXT NOT NULL,
    call_count INTEGER NOT NULL DEFAULT 1,
    edge_type TEXT NOT NULL DEFAULT 'call',
    last_seen REAL NOT NULL,
    PRIMARY KEY (caller, callee, edge_type)
);
CREATE INDEX IF NOT EXISTS idx_se_caller ON structural_edges(caller);
CREATE INDEX IF NOT EXISTS idx_se_callee ON structural_edges(callee);
CREATE INDEX IF NOT EXISTS idx_se_type ON structural_edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_se_last_seen ON structural_edges(last_seen);
```

`edge_type` ∈ {`call`, `import`, `inherits`, `implements`, `uses`, `contains`}. Mirrors the `RELATION_VIEWS` vocabulary in `structural.py`.

No schema version bump — the new table is additive and `CREATE TABLE IF NOT EXISTS` is idempotent for both fresh and existing databases.

### 1.2 New method on `SynapseStore`

```python
def persist_structural_edges(
    self, edges: Iterable[dict], now: float | None = None
) -> int:
    """Persist directed structural edges from the loaded graph.

    Reads edge['source']/edge['target']/edge['relation'] with
    fallbacks for graphify's _src/_tgt and label/kind. Only edges whose
    relation is in RELATION_VIEWS are stored. Idempotent: re-running
    build() increments call_count and updates last_seen on conflict.

    Returns the number of edge rows upserted.
    """
```

### 1.3 Constants added

```python
# Edge type vocabulary (subset of graph.json relations we persist)
STRUCTURAL_EDGE_TYPES = frozenset({
    "call", "import", "inherits", "implements", "uses", "contains",
})
# Mapping from graph.json relation strings to our edge_type values
RELATION_TO_EDGE_TYPE = {
    "calls": "call",
    "imports_from": "import",
    "imports": "import",
    "inherits": "inherits",
    "implements": "implements",
    "uses": "uses",
    "references": "uses",
    "contains": "contains",
}
```

### 1.4 Wiring (`core.py build()`)

After the `StructuralIndex` is built (existing code at core.py:447-458), persist to the synapse store:

```python
# Persist structural edges to the synapse store so they survive rebuilds
# (the in-memory StructuralIndex is lost on process exit).
if self.enable_synapses and self._synapses is not None:
    try:
        edges = getattr(self.embedder, "edges", None) or []
        count = self._synapses.persist_structural_edges(edges)
        if count:
            result["structural_edges"] = count
    except Exception:
        pass  # fail-open: persistence is non-critical
```

### 1.5 Retrieval

The existing in-memory `StructuralIndex.recall()` and `context_selector._apply_structural_expansion()` already drive L3 retrieval when `NEURALMIND_STRUCTURAL_RECALL=1`. The `structural_edges` table adds durability — the in-memory index is lost on process exit, but the table persists across sessions and can be queried via direct SQL for CLI/MCP tools.

---

## 2. Component 2 — Time-based half-life decay

### 2.1 New module-level function

```python
def decay_weight(
    current_weight: float, last_activated: float,
    half_life_days: float = 30.0, now: float | None = None,
) -> float:
    """Exponential half-life decay on a single weight.

    Returns current_weight * exp(-λ * age_days) where
    λ = ln(2) / half_life_days and age_days = (now - last_activated) / 86400.
    """
```

### 2.2 New constants

```python
HALF_LIFE_DAYS = 30.0        # default half-life for personal / branch:* namespaces
SHARED_HALF_LIFE_DAYS = 60.0  # sticky team baseline
EPHEMERAL_HALF_LIFE_DAYS = 1.0  # session scratch decays fast

NAMESPACE_HALF_LIVES: dict[str, float] = {
    SHARED_NAMESPACE: SHARED_HALF_LIFE_DAYS,
    EPHEMERAL_NAMESPACE: EPHEMERAL_HALF_LIFE_DAYS,
}
```

### 2.3 Modified `decay()` method

Replace the fixed-rate decay with time-based. Instead of:

```sql
UPDATE synapses SET weight = weight * (1.0 - DECAY_RATE) WHERE ...
```

Use:

```sql
UPDATE synapses SET weight = MAX(?, weight * EXP(-? * (? - last_activated) / 86400.0))
WHERE namespace = ? AND activation_count >= ?
```

The decay lambda and age are computed per-row from `last_activated`, so edges decay by **how long ago they were last activated**, not by how many tick calls have passed. LTP floor and per-namespace policy preserved by passing the appropriate half-life per namespace.

### 2.4 Backward compatibility

- The `decay(now=...)` method signature is unchanged — only the UPDATE statements change.
- Edges with `last_activated` in the future or NULL (shouldn't happen, but defensive) are skipped.
- The `last_decay` meta stamp is still written — tick callers don't need changes.

---

## 3. Component 3 — Migration version check

### 3.1 Stamp version on build (`core.py`)

In `_materialize_ir()`, after computing the summary:

```python
from neuralmind import __version__ as _nm_version
summary["neuralmind_version"] = _nm_version
```

This value is already written to `ir_meta.json` by the existing code, so no extra I/O.

### 3.2 Warn on mismatch (`cli.py`)

New helper:

```python
def _check_version_mismatch(project_path: str) -> str | None:
    """Return a warning string if the project's ir_meta.json was built with
    a different NeuralMind version than the running one, else None.
    """
    ir_meta_path = Path(project_path) / ".neuralmind" / "ir_meta.json"
    if not ir_meta_path.exists():
        return None
    try:
        meta = json.loads(ir_meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    stored = meta.get("neuralmind_version")
    current = __version__  # from neuralmind import __version__
    if stored and stored != current:
        return (
            f"This project was indexed with NeuralMind v{stored}.\n"
            f"v{current} requires a one-time reindex.\n"
            f"Run: neuralmind build --force"
        )
    return None
```

`cmd_build()` and `cmd_query()` call it once and print the warning if returned (to stderr so it doesn't contaminate JSON output). The build still proceeds — it's advisory.

---

## 4. Test plan

| Test | File | Verifies |
|------|------|----------|
| `test_persist_basic` | `tests/test_tier1.py` | Table populated after `persist_structural_edges()` |
| `test_persist_idempotent` | `tests/test_tier1.py` | Re-upsert increments call_count, not rows |
| `test_persist_skip_unknown_relations` | `tests/test_tier1.py` | Unknown relations dropped |
| `test_persist_survives_reopen` | `tests/test_tier1.py` | Data persists across `SynapseStore` reopen |
| `test_decay_weight_half_life_math` | `tests/test_tier1.py` | `decay_weight()` values match hand-computed |
| `test_decay_weight_zero_age_is_identity` | `tests/test_tier1.py` | age_days=0 → weight unchanged |
| `test_time_decay_reduces_old_edges` | `tests/test_tier1.py` | Old `last_activated` edges decay more than fresh ones |
| `test_time_decay_ltp_floor_preserved` | `tests/test_tier1.py` | LTP edges floor at LTP_FLOOR after time decay |
| `test_time_decay_prunes_weak_old_edges` | `tests/test_tier1.py` | Old weak edges pruned |
| `test_time_decay_fresh_edges_unchanged` | `tests/test_tier1.py` | Fresh edges unaffected by decay tick |
| `test_migration_warning_fires_on_version_mismatch` | `tests/test_tier1.py` | CLI warns when `ir_meta.json` version ≠ running version |
| `test_no_warning_when_versions_match` | `tests/test_tier1.py` | No warning on matching versions |
| `test_no_warning_without_ir_meta` | `tests/test_tier1.py` | No warning when ir_meta.json absent |

---

## 5. Backward compatibility

| Concern | Handling |
|---------|---------|---------|
| Existing `synapses.db` without `structural_edges` | `CREATE TABLE IF NOT EXISTS` — created lazily on first use |
| Existing `ir_meta.json` without `neuralmind_version` | `stored` is None → no warning. Population happens on next build. |
| Tick-based callers of `decay()` | Signature unchanged. `Hook` SessionStart path works without modification. |
| Schema version | Not bumped — purely additive. |

---

## 6. Open questions

1. **Should `persist_structural_edges()` be called even when synapses are disabled?** → No. The table lives in `synapses.db`; if synapses are off, the graph.json links are still accessible via the existing `StructuralIndex` when built.

2. **What if `EXP()` is missing from a very old SQLite?** → Fallback: fetch rows, compute in Python, batch update. Likely unnecessary in practice (verified on this system).
