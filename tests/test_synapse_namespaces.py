"""Tests for memory namespaces & branch isolation (PRD 4).

Stdlib-only by convention (like all synapse-layer tests): no chromadb,
no yaml, no git binary — branch detection is exercised with a mocked
subprocess. Covers the v0→v1 schema migration (the mandatory
no-data-loss test), namespaced writes + isolation, merged-read
weighting, per-namespace decay and reset, export→import round-trips,
and namespace resolution.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess

from neuralmind import namespaces
from neuralmind.ir import (
    SYNAPSE_BUNDLE_FORMAT,
    SYNAPSE_BUNDLE_VERSION,
    IRError,
    export_synapse_bundle,
    import_synapse_bundle,
    validate_synapse_bundle,
)
from neuralmind.synapses import (
    DEFAULT_NAMESPACE,
    EPHEMERAL_NAMESPACE,
    LEARNING_RATE,
    SCHEMA_VERSION,
    SHARED_NAMESPACE,
    W_BRANCH,
    W_PERSONAL,
    W_SHARED,
    SynapseStore,
    default_db_path,
    merge_weight_for,
    normalize_namespace,
)

# The exact pre-namespace (v0) schema, frozen here so the migration test
# keeps exercising a byte-faithful old database even after the live SCHEMA
# constant moves on.
V0_SCHEMA = """
CREATE TABLE IF NOT EXISTS synapses (
    node_a TEXT NOT NULL,
    node_b TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 0.0,
    activation_count INTEGER NOT NULL DEFAULT 0,
    last_activated REAL NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (node_a, node_b),
    CHECK (node_a < node_b)
);
CREATE INDEX IF NOT EXISTS idx_syn_a ON synapses(node_a);
CREATE INDEX IF NOT EXISTS idx_syn_b ON synapses(node_b);
CREATE INDEX IF NOT EXISTS idx_syn_weight ON synapses(weight);

CREATE TABLE IF NOT EXISTS synapse_transitions (
    from_node TEXT NOT NULL,
    to_node TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 0.0,
    count INTEGER NOT NULL DEFAULT 0,
    last_activated REAL NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (from_node, to_node),
    CHECK (from_node <> to_node)
);
CREATE INDEX IF NOT EXISTS idx_trans_from ON synapse_transitions(from_node);
CREATE INDEX IF NOT EXISTS idx_trans_weight ON synapse_transitions(weight);

CREATE TABLE IF NOT EXISTS node_activations (
    node_id TEXT PRIMARY KEY,
    activation_count INTEGER NOT NULL DEFAULT 0,
    last_activated REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _build_v0_db(db_path) -> None:
    """Create a pre-namespace database with known learned memory."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(V0_SCHEMA)
        conn.executemany(
            "INSERT INTO synapses VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("auth.py", "session.py", 0.42, 7, 1000.0, 900.0),
                ("billing.py", "stripe.py", 0.05, 1, 1100.0, 1050.0),
            ],
        )
        conn.executemany(
            "INSERT INTO synapse_transitions VALUES (?, ?, ?, ?, ?, ?)",
            [("models.py", "schema.py", 3.0, 4, 1200.0, 1150.0)],
        )
        conn.executemany(
            "INSERT INTO node_activations VALUES (?, ?, ?)",
            [("auth.py", 12, 1000.0), ("session.py", 9, 1000.0)],
        )
        conn.commit()
    finally:
        conn.close()


def _store(tmp_path, namespace=None):
    return SynapseStore(tmp_path / "synapses.db", namespace=namespace)


# ---------------------------------------------------------------------------
# v0 → v1 migration (mandatory: no data loss, idempotent)
# ---------------------------------------------------------------------------


def test_v0_db_migrates_in_place_without_losing_memory(tmp_path):
    db = tmp_path / "synapses.db"
    _build_v0_db(db)

    store = SynapseStore(db)

    assert store.schema_version() == SCHEMA_VERSION
    # Every v0 edge lands in 'personal' with identical weight + count.
    edges = {(a, b): (w, c) for a, b, w, c in store.edges(namespaces=[DEFAULT_NAMESPACE])}
    assert edges[("auth.py", "session.py")] == (0.42, 7)
    assert edges[("billing.py", "stripe.py")] == (0.05, 1)
    # Transitions and activations survive verbatim too.
    rows = store.transitions(namespaces=[DEFAULT_NAMESPACE])
    assert rows == [("models.py", "schema.py", 3.0, 4)]
    stats = store.stats()
    assert stats["namespaces"][DEFAULT_NAMESPACE]["edges"] == 2
    assert stats["namespaces"][DEFAULT_NAMESPACE]["nodes"] == 2
    # The renamed scratch tables are gone — the rebuild committed fully.
    conn = sqlite3.connect(db)
    try:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert not any(name.endswith("_v0") for name in names)


def test_migrated_db_reopens_as_a_noop(tmp_path):
    db = tmp_path / "synapses.db"
    _build_v0_db(db)
    SynapseStore(db)

    again = SynapseStore(db)

    assert again.schema_version() == SCHEMA_VERSION
    edges = {(a, b): (w, c) for a, b, w, c in again.edges(namespaces=[DEFAULT_NAMESPACE])}
    assert edges[("auth.py", "session.py")] == (0.42, 7)
    assert len(edges) == 2


def test_migrated_memory_behaves_like_pre_namespace_memory(tmp_path):
    """The single-namespace behavior users already have IS 'personal':
    merged-default reads return the old weights unchanged."""
    db = tmp_path / "synapses.db"
    _build_v0_db(db)
    store = SynapseStore(db)
    assert dict(store.neighbors("auth.py"))["session.py"] == 0.42
    assert dict(store.next_likely("models.py")) == {"schema.py": 1.0}


def test_fresh_db_is_created_at_current_schema_version(tmp_path):
    store = _store(tmp_path)
    assert store.schema_version() == SCHEMA_VERSION


def test_reset_preserves_schema_version_marker(tmp_path):
    store = _store(tmp_path)
    store.reinforce(["a", "b"])
    store.reset()
    assert store.schema_version() == SCHEMA_VERSION
    # And a re-open must not mistake the wiped store for a v0 database.
    assert SynapseStore(store.db_path).stats()["edges"] == 0


# ---------------------------------------------------------------------------
# Namespaced writes + isolation
# ---------------------------------------------------------------------------


def test_writes_default_to_personal_namespace(tmp_path):
    store = _store(tmp_path)
    store.reinforce(["a", "b"])
    store.record_sequence(["a", "b"])
    stats = store.stats()
    assert set(stats["namespaces"]) == {DEFAULT_NAMESPACE}


def test_branch_namespaces_are_isolated_from_each_other(tmp_path):
    store = _store(tmp_path, namespace="branch:feature-x")
    store.reinforce(["a", "b"])
    store.record_sequence(["a", "b"])

    assert store.edges(namespaces=["branch:feature-x"]) != []
    assert store.edges(namespaces=["branch:feature-y"]) == []
    assert store.next_likely("a", namespaces=["branch:feature-y"]) == []
    assert dict(store.next_likely("a", namespaces=["branch:feature-x"])) == {"b": 1.0}


def test_explicit_namespace_argument_overrides_active(tmp_path):
    store = _store(tmp_path, namespace="branch:feature-x")
    store.reinforce(["a", "b"], namespace=SHARED_NAMESPACE)
    assert store.edges(namespaces=["branch:feature-x"]) == []
    assert dict(store.neighbors("a", namespaces=[SHARED_NAMESPACE]))["b"] > 0.0


def test_invalid_namespace_is_rejected(tmp_path):
    store = _store(tmp_path)
    for bad in ("   ", "two words"):
        try:
            store.reinforce(["a", "b"], namespace=bad)
        except ValueError:
            continue
        raise AssertionError(f"namespace {bad!r} should have been rejected")
    # Empty/None mean "use the active namespace" — the write must not fork.
    store.reinforce(["a", "b"], namespace="")
    assert set(store.stats()["namespaces"]) == {DEFAULT_NAMESPACE}
    assert normalize_namespace("  branch:x ") == "branch:x"


# ---------------------------------------------------------------------------
# Merged-read weighting (W_BRANCH > W_PERSONAL > W_SHARED)
# ---------------------------------------------------------------------------


def test_merged_read_applies_documented_weights(tmp_path):
    store = _store(tmp_path, namespace="branch:feature-x")
    store.reinforce(["a", "b"])  # branch:feature-x → 0.15
    store.reinforce(["a", "b"], namespace=DEFAULT_NAMESPACE)  # personal → 0.15
    store.reinforce(["a", "b"], namespace=SHARED_NAMESPACE)  # shared → 0.15

    merged = dict(store.neighbors("a"))["b"]
    expected = LEARNING_RATE * (W_BRANCH + W_PERSONAL + W_SHARED)
    assert abs(merged - expected) < 1e-9


def test_branch_local_context_outranks_shared_priors(tmp_path):
    """One branch-local observation must outrank one shared observation of a
    competing neighbor — recent local context wins under the merged view."""
    store = _store(tmp_path, namespace="branch:feature-x")
    store.reinforce(["a", "branch_pick"])
    store.reinforce(["a", "shared_pick"], namespace=SHARED_NAMESPACE)
    ranked = store.neighbors("a")
    assert ranked[0][0] == "branch_pick"
    assert abs(ranked[0][1] - LEARNING_RATE * W_BRANCH) < 1e-9
    assert abs(dict(ranked)["shared_pick"] - LEARNING_RATE * W_SHARED) < 1e-9


def test_active_personal_reads_at_full_weight(tmp_path):
    """On the default branch the active namespace IS personal, so merged
    reads return pre-namespace weights unchanged (no surprise rescale)."""
    store = _store(tmp_path)  # active namespace: personal
    store.reinforce(["x", "y"])
    assert abs(dict(store.neighbors("x"))["y"] - LEARNING_RATE) < 1e-9
    assert merge_weight_for(DEFAULT_NAMESPACE, DEFAULT_NAMESPACE) == W_BRANCH


def test_merged_next_likely_weights_branch_over_shared(tmp_path):
    store = _store(tmp_path, namespace="branch:feature-x")
    store.record_sequence(["a", "b"])  # branch: weight 1.0
    store.record_sequence(["a", "c"], namespace=SHARED_NAMESPACE)  # shared: weight 1.0
    probs = dict(store.next_likely("a"))
    # branch 1.0*W_BRANCH vs shared 1.0*W_SHARED, normalized.
    assert abs(probs["b"] - W_BRANCH / (W_BRANCH + W_SHARED)) < 1e-9
    assert abs(probs["c"] - W_SHARED / (W_BRANCH + W_SHARED)) < 1e-9


def test_spread_merges_namespaces_and_reports_contributions(tmp_path):
    store = _store(tmp_path, namespace="branch:feature-x")
    store.reinforce(["A", "B"])
    store.reinforce(["A", "B"], namespace=SHARED_NAMESPACE)

    ranked, contributions = store.spread_with_contributions([("A", 1.0)], depth=1, top_k=5)

    energy = dict(ranked)["B"]
    by_ns = contributions["B"]
    assert set(by_ns) == {"branch:feature-x", SHARED_NAMESPACE}
    # Per-namespace shares explain exactly the merged energy.
    assert abs(sum(by_ns.values()) - energy) < 1e-9
    assert by_ns["branch:feature-x"] > by_ns[SHARED_NAMESPACE]


def test_spread_without_tracking_matches_traced_energies(tmp_path):
    store = _store(tmp_path, namespace="branch:feature-x")
    store.reinforce(["A", "B"])
    store.reinforce(["B", "C"], namespace=DEFAULT_NAMESPACE)
    plain = store.spread([("A", 1.0)], depth=2, top_k=5)
    traced, _ = store.spread_with_contributions([("A", 1.0)], depth=2, top_k=5)
    assert plain == traced


# ---------------------------------------------------------------------------
# Per-namespace reset + decay/TTL
# ---------------------------------------------------------------------------


def test_clear_namespace_leaves_other_namespaces_intact(tmp_path):
    store = _store(tmp_path, namespace="branch:feature-x")
    store.reinforce(["a", "b"])
    store.record_sequence(["a", "b"])
    store.reinforce(["a", "b"], namespace=DEFAULT_NAMESPACE)

    counts = store.clear_namespace("branch:feature-x")

    assert counts["edges"] == 1
    assert counts["transitions"] == 1
    assert store.edges(namespaces=["branch:feature-x"]) == []
    assert store.next_likely("a", namespaces=["branch:feature-x"]) == []
    assert dict(store.neighbors("a", namespaces=[DEFAULT_NAMESPACE]))["b"] > 0.0


def test_ephemeral_decays_much_faster_than_personal(tmp_path):
    store = _store(tmp_path)
    store.reinforce(["a", "b"], namespace=EPHEMERAL_NAMESPACE)
    store.reinforce(["a", "b"], namespace=DEFAULT_NAMESPACE)
    for _ in range(10):
        store.decay()
    # 0.15 * 0.75^10 ≈ 0.008 → pruned; personal at 0.15 * 0.98^10 ≈ 0.12 lives.
    assert store.edges(namespaces=[EPHEMERAL_NAMESPACE]) == []
    assert store.edges(namespaces=[DEFAULT_NAMESPACE]) != []


def test_shared_namespace_is_stickier_than_personal(tmp_path):
    store = _store(tmp_path)
    store.reinforce(["a", "b"], namespace=SHARED_NAMESPACE)
    store.reinforce(["a", "b"], namespace=DEFAULT_NAMESPACE)
    for _ in range(20):
        store.decay()
    shared_w = dict(store.neighbors("a", namespaces=[SHARED_NAMESPACE]))["b"]
    personal_w = dict(store.neighbors("a", namespaces=[DEFAULT_NAMESPACE]))["b"]
    assert shared_w > personal_w > 0.0


def test_ephemeral_gets_no_ltp_immunity(tmp_path):
    """Even a heavily-reinforced ephemeral edge fades: session scratch must
    never become permanent through the LTP floor."""
    store = _store(tmp_path)
    for _ in range(10):  # well past LTP_THRESHOLD
        store.reinforce(["hot_a", "hot_b"], namespace=EPHEMERAL_NAMESPACE)
    for _ in range(30):
        store.decay()
    assert store.edges(namespaces=[EPHEMERAL_NAMESPACE]) == []


def test_ephemeral_transitions_prune_fast(tmp_path):
    store = _store(tmp_path)
    store.record_sequence(["a", "b"], namespace=EPHEMERAL_NAMESPACE)
    store.record_sequence(["a", "b"], namespace=DEFAULT_NAMESPACE)
    for _ in range(5):
        store.decay()
    # 1.0 * 0.75^5 ≈ 0.24 < prune threshold 0.5; personal 1.0 * 0.99^5 survives.
    assert store.next_likely("a", namespaces=[EPHEMERAL_NAMESPACE]) == []
    assert store.next_likely("a", namespaces=[DEFAULT_NAMESPACE]) != []


# ---------------------------------------------------------------------------
# Stats by namespace
# ---------------------------------------------------------------------------


def test_stats_reports_contribution_by_namespace(tmp_path):
    store = _store(tmp_path, namespace="branch:feature-x")
    store.reinforce(["a", "b", "c"])
    store.reinforce(["a", "b"], namespace=SHARED_NAMESPACE)
    store.record_sequence(["a", "b"], namespace=SHARED_NAMESPACE)

    stats = store.stats()

    assert stats["namespace"] == "branch:feature-x"
    assert stats["schema_version"] == SCHEMA_VERSION
    assert stats["namespaces"]["branch:feature-x"]["edges"] == 3
    assert stats["namespaces"][SHARED_NAMESPACE]["edges"] == 1
    assert stats["namespaces"][SHARED_NAMESPACE]["transitions"] == 1
    # Totals still span the whole store.
    assert stats["edges"] == 4


# ---------------------------------------------------------------------------
# Export / import bundles (PRD 8 on-ramp)
# ---------------------------------------------------------------------------


def test_export_import_round_trip(tmp_path):
    src = SynapseStore(tmp_path / "src.db", namespace="branch:feature-x")
    for _ in range(3):
        src.reinforce(["auth.py", "session.py"])
    src.record_sequence(["models.py", "schema.py"])

    bundle = export_synapse_bundle(src, "branch:feature-x")
    assert bundle["format"] == SYNAPSE_BUNDLE_FORMAT
    assert bundle["version"] == SYNAPSE_BUNDLE_VERSION
    assert validate_synapse_bundle(bundle) == []
    # Bundles survive JSON serialization (the CLI writes them to disk).
    bundle = json.loads(json.dumps(bundle))

    dst = SynapseStore(tmp_path / "dst.db")
    result = import_synapse_bundle(dst, bundle, namespace=SHARED_NAMESPACE)

    assert result == {"namespace": SHARED_NAMESPACE, "synapses": 1, "transitions": 1}
    src_w = dict(src.neighbors("auth.py", namespaces=["branch:feature-x"]))["session.py"]
    dst_w = dict(dst.neighbors("auth.py", namespaces=[SHARED_NAMESPACE]))["session.py"]
    assert abs(src_w - dst_w) < 1e-9
    assert dict(dst.next_likely("models.py", namespaces=[SHARED_NAMESPACE])) == {"schema.py": 1.0}


def test_reimporting_a_bundle_is_idempotent(tmp_path):
    src = SynapseStore(tmp_path / "src.db")
    src.reinforce(["a", "b"])
    bundle = export_synapse_bundle(src, DEFAULT_NAMESPACE)

    dst = SynapseStore(tmp_path / "dst.db")
    import_synapse_bundle(dst, bundle, namespace=SHARED_NAMESPACE)
    once = dict(dst.neighbors("a", namespaces=[SHARED_NAMESPACE]))["b"]
    import_synapse_bundle(dst, bundle, namespace=SHARED_NAMESPACE)
    twice = dict(dst.neighbors("a", namespaces=[SHARED_NAMESPACE]))["b"]
    assert once == twice


def test_import_rejects_malformed_bundles(tmp_path):
    dst = _store(tmp_path)
    bad_bundles = [
        {"format": "something-else", "version": 1, "namespace": "shared"},
        {"format": SYNAPSE_BUNDLE_FORMAT, "version": SYNAPSE_BUNDLE_VERSION + 1, "namespace": "x"},
        {"format": SYNAPSE_BUNDLE_FORMAT, "version": 1},  # no namespace
        {
            "format": SYNAPSE_BUNDLE_FORMAT,
            "version": 1,
            "namespace": "shared",
            "synapses": [{"source": "a"}],  # missing target
        },
    ]
    for bundle in bad_bundles:
        assert validate_synapse_bundle(bundle) != []
        try:
            import_synapse_bundle(dst, bundle)
        except IRError:
            continue
        raise AssertionError(f"bundle {bundle!r} should have been rejected")
    assert dst.stats()["edges"] == 0  # nothing partially imported


def test_validate_bundle_tolerates_non_dict_input():
    assert validate_synapse_bundle(None) == ["bundle must be a JSON object"]
    assert validate_synapse_bundle([1, 2]) == ["bundle must be a JSON object"]


# ---------------------------------------------------------------------------
# Namespace resolution (mocked git — no repo, no git binary needed)
# ---------------------------------------------------------------------------


def _mock_git(monkeypatch, branch=None, default_branch=None):
    """Stub namespaces' git subprocess: branch/default None → command fails."""

    def fake_check_output(cmd, **kwargs):
        if "rev-parse" in cmd:
            if branch is None:
                raise subprocess.CalledProcessError(128, cmd)
            return f"{branch}\n".encode()
        if "symbolic-ref" in cmd:
            if default_branch is None:
                raise subprocess.CalledProcessError(128, cmd)
            return f"origin/{default_branch}\n".encode()
        raise AssertionError(f"unexpected git call: {cmd}")

    monkeypatch.setattr(namespaces.subprocess, "check_output", fake_check_output)


def test_feature_branch_resolves_to_branch_namespace(tmp_path, monkeypatch):
    _mock_git(monkeypatch, branch="feature-x", default_branch="main")
    assert namespaces.resolve_namespace(tmp_path, env={}) == "branch:feature-x"


def test_default_branch_resolves_to_personal(tmp_path, monkeypatch):
    _mock_git(monkeypatch, branch="main", default_branch="main")
    assert namespaces.resolve_namespace(tmp_path, env={}) == DEFAULT_NAMESPACE


def test_non_repo_resolves_to_personal(tmp_path, monkeypatch):
    _mock_git(monkeypatch, branch=None)
    assert namespaces.resolve_namespace(tmp_path, env={}) == DEFAULT_NAMESPACE


def test_detached_head_resolves_to_personal(tmp_path, monkeypatch):
    _mock_git(monkeypatch, branch="HEAD")
    assert namespaces.resolve_namespace(tmp_path, env={}) == DEFAULT_NAMESPACE


def test_unusual_default_branch_via_origin_head(tmp_path, monkeypatch):
    """A repo whose default branch is 'develop' treats it as personal."""
    _mock_git(monkeypatch, branch="develop", default_branch="develop")
    assert namespaces.resolve_namespace(tmp_path, env={}) == DEFAULT_NAMESPACE


def test_master_fallback_without_origin_head(tmp_path, monkeypatch):
    _mock_git(monkeypatch, branch="master", default_branch=None)
    assert namespaces.resolve_namespace(tmp_path, env={}) == DEFAULT_NAMESPACE


def test_env_var_overrides_branch_detection(tmp_path, monkeypatch):
    _mock_git(monkeypatch, branch="feature-x", default_branch="main")
    resolved = namespaces.resolve_namespace(tmp_path, env={"NEURALMIND_NAMESPACE": "ephemeral"})
    assert resolved == EPHEMERAL_NAMESPACE


def test_config_pin_overrides_branch_detection(tmp_path, monkeypatch):
    _mock_git(monkeypatch, branch="feature-x", default_branch="main")
    resolved = namespaces.resolve_namespace(
        tmp_path, config={"memory_namespace": "team-baseline"}, env={}
    )
    assert resolved == "team-baseline"


def test_config_file_pin_is_read_from_disk(tmp_path, monkeypatch):
    _mock_git(monkeypatch, branch="feature-x", default_branch="main")
    (tmp_path / "neuralmind-backend.json").write_text(
        json.dumps({"memory_namespace": "pinned"}), encoding="utf-8"
    )
    assert namespaces.resolve_namespace(tmp_path, env={}) == "pinned"


def test_yaml_config_pin_line_scan(tmp_path, monkeypatch):
    """The YAML probe works in the stdlib-only hook path (regex fallback
    matches the same line PyYAML would parse)."""
    _mock_git(monkeypatch, branch="feature-x", default_branch="main")
    (tmp_path / "neuralmind-backend.yaml").write_text(
        "backend: auto\nmemory_namespace: shared\n", encoding="utf-8"
    )
    assert namespaces.resolve_namespace(tmp_path, env={}) == SHARED_NAMESPACE
    match = namespaces._YAML_KEY_RE.search("backend: auto\nmemory_namespace: shared\n")
    assert match is not None and match.group(1) == "shared"


def test_invalid_env_override_degrades_to_detection(tmp_path, monkeypatch):
    _mock_git(monkeypatch, branch="feature-x", default_branch="main")
    resolved = namespaces.resolve_namespace(tmp_path, env={"NEURALMIND_NAMESPACE": "   "})
    assert resolved == "branch:feature-x"


# ---------------------------------------------------------------------------
# Session boundaries: hooks + daemon clear ephemeral scratch
# ---------------------------------------------------------------------------


def test_session_start_hook_clears_ephemeral_namespace(tmp_path, monkeypatch):
    import io
    import sys

    from neuralmind.hooks import run_hook

    monkeypatch.delenv("NEURALMIND_NAMESPACE", raising=False)
    monkeypatch.setenv("NEURALMIND_SYNAPSE_EXPORT", "0")  # keep writes inside tmp_path
    db = default_db_path(tmp_path)
    seeded = SynapseStore(db, namespace=EPHEMERAL_NAMESPACE)
    seeded.reinforce(["scratch_a", "scratch_b"])
    seeded.reinforce(["keep_a", "keep_b"], namespace=DEFAULT_NAMESPACE)

    stdin_backup, stdout_backup = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(json.dumps({"cwd": str(tmp_path)}))
    sys.stdout = io.StringIO()
    try:
        rc = run_hook("session-start")
    finally:
        sys.stdin, sys.stdout = stdin_backup, stdout_backup

    assert rc == 0
    store = SynapseStore(db)
    assert store.edges(namespaces=[EPHEMERAL_NAMESPACE]) == []
    assert store.edges(namespaces=[DEFAULT_NAMESPACE]) != []


def test_daemon_shutdown_clears_ephemeral_for_registered_projects(tmp_path):
    from neuralmind.daemon import ProjectRegistry, _clear_ephemeral_memory

    db = default_db_path(tmp_path)
    seeded = SynapseStore(db, namespace=EPHEMERAL_NAMESPACE)
    seeded.reinforce(["scratch_a", "scratch_b"])
    seeded.reinforce(["keep_a", "keep_b"], namespace=DEFAULT_NAMESPACE)

    registry = ProjectRegistry(mind_factory=lambda path: object())
    registry.get(str(tmp_path))
    _clear_ephemeral_memory(registry)

    store = SynapseStore(db)
    assert store.edges(namespaces=[EPHEMERAL_NAMESPACE]) == []
    assert store.edges(namespaces=[DEFAULT_NAMESPACE]) != []
