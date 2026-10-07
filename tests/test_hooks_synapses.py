"""Tests for the SessionStart / UserPromptSubmit / PreCompact hook actions."""

from __future__ import annotations

import io
import json
import sys
from types import SimpleNamespace

from neuralmind.hooks import _hook_block, install_hooks, run_hook
from neuralmind.synapses import SynapseStore, default_db_path


def _run(action: str, payload: dict) -> tuple[int, str]:
    """Drive run_hook with a stdin payload and capture stdout."""
    stdin_backup, stdout_backup = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(json.dumps(payload))
    sys.stdout = io.StringIO()
    try:
        rc = run_hook(action)
        captured = sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = stdin_backup, stdout_backup
    return rc, captured


def test_hook_block_advertises_lifecycle_events():
    block = _hook_block()
    assert "SessionStart" in block
    assert "UserPromptSubmit" in block
    assert "PreCompact" in block
    cmds = []
    for event in ("SessionStart", "UserPromptSubmit", "PreCompact"):
        for matcher_block in block[event]:
            for h in matcher_block["hooks"]:
                cmds.append(h["command"])
    assert any("session-start" in c for c in cmds)
    assert any("prompt-submit" in c for c in cmds)
    assert any("pre-compact" in c for c in cmds)


def test_install_writes_lifecycle_event_blocks(tmp_path):
    install_hooks(scope="project", project_path=str(tmp_path))
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    hooks = settings["hooks"]
    for event in ("SessionStart", "UserPromptSubmit", "PreCompact"):
        assert event in hooks
        # Each event has exactly one neuralmind-managed block on fresh install.
        assert len(hooks[event]) == 1


def test_install_idempotent_for_lifecycle_events(tmp_path):
    install_hooks(scope="project", project_path=str(tmp_path))
    install_hooks(scope="project", project_path=str(tmp_path))
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    for event in ("SessionStart", "UserPromptSubmit", "PreCompact"):
        # Still exactly one block — repeated install must not duplicate.
        assert len(settings["hooks"][event]) == 1


def test_session_start_runs_decay_tick(tmp_path):
    # SessionStart should run decay() — verify by checking that an edge
    # weight strictly decreased after the hook fires.
    db = default_db_path(tmp_path)
    store = SynapseStore(db)
    store.reinforce(["a", "b"])
    before = dict(store.neighbors("a"))["b"]

    rc, _ = _run("session-start", {"cwd": str(tmp_path)})
    assert rc == 0

    fresh = SynapseStore(db)
    after = dict(fresh.neighbors("a")).get("b")
    assert after is not None
    assert after < before


def test_session_start_exports_synapse_memory(tmp_path, monkeypatch):
    # Isolate HOME so we don't touch a real Claude auto-memory dir.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))

    store = SynapseStore(default_db_path(tmp_path))
    store.reinforce(["a", "b"])

    rc, _ = _run("session-start", {"cwd": str(tmp_path)})
    assert rc == 0

    out = tmp_path / ".neuralmind" / "SYNAPSE_MEMORY.md"
    assert out.exists()
    assert "Synapse Memory" in out.read_text()


def test_session_start_export_disabled_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("NEURALMIND_SYNAPSE_EXPORT", "0")

    store = SynapseStore(default_db_path(tmp_path))
    store.reinforce(["a", "b"])

    rc, _ = _run("session-start", {"cwd": str(tmp_path)})
    assert rc == 0

    out = tmp_path / ".neuralmind" / "SYNAPSE_MEMORY.md"
    assert not out.exists()


def test_pre_compact_normalizes_hubs(tmp_path):
    db = default_db_path(tmp_path)
    store = SynapseStore(db)
    # Build a clear hub so normalize_hubs has something to do.
    for i in range(120):
        store.reinforce(["HUB", f"spoke_{i}"])
    before = store.stats()["total_weight"]

    rc, _ = _run("pre-compact", {"cwd": str(tmp_path)})
    assert rc == 0

    after = SynapseStore(db).stats()["total_weight"]
    assert after < before


def test_prompt_submit_no_synapses_emits_nothing(tmp_path):
    # No graph built, no edges learned — hook must fail open silently.
    rc, captured = _run(
        "prompt-submit",
        {"cwd": str(tmp_path), "prompt": "How does auth work?"},
    )
    assert rc == 0
    assert captured == ""


def test_prompt_submit_disabled_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_SYNAPSE_INJECT", "0")
    rc, captured = _run(
        "prompt-submit",
        {"cwd": str(tmp_path), "prompt": "anything"},
    )
    assert rc == 0
    assert captured == ""


def test_prompt_submit_empty_prompt_is_skipped(tmp_path):
    rc, captured = _run("prompt-submit", {"cwd": str(tmp_path), "prompt": ""})
    assert rc == 0
    assert captured == ""


_SAVE = "pkg_mod_py__save_fn"


class _StubMind:
    """Stands in for NeuralMind in the prompt-submit hook: a built index whose
    search returns ``HITS`` = [(node_id, similarity), ...], no synapse store."""

    HITS: list = []
    NODES = [
        {
            "id": _SAVE,
            "label": "save()",
            "file_type": "code",
            "source_file": "pkg/mod.py",
            "source_location": "L3",
        }
    ]
    synapses = None

    def __init__(self, project_path):
        hits = [{"id": node_id, "score": score, "metadata": {}} for node_id, score in self.HITS]
        self.embedder = SimpleNamespace(
            nodes=self.NODES, search=lambda query, n: hits[:n], get_nodes_by_ids=lambda ids: []
        )

    def _load_existing_index(self):
        return True


def _recall(tmp_path, monkeypatch, hits) -> str:
    import neuralmind.core

    # Hooks act only in a project with a NeuralMind directory.
    (tmp_path / ".neuralmind").mkdir(exist_ok=True)
    monkeypatch.setenv("NEURALMIND_PROVENANCE_INJECT", "0")
    monkeypatch.setenv("NEURALMIND_SESSION_RECAP", "0")
    monkeypatch.setattr(_StubMind, "HITS", hits)
    monkeypatch.setattr(neuralmind.core, "NeuralMind", _StubMind)
    rc, out = _run("prompt-submit", {"cwd": str(tmp_path), "prompt": "yes"})
    assert rc == 0
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""


def _recall_outcomes(tmp_path) -> list[str]:
    return [
        json.loads(line)["outcome"]
        for f in sorted((tmp_path / ".neuralmind" / "metrics").glob("*.jsonl"))
        for line in f.read_text().splitlines()
    ]


def test_prompt_recall_injects_on_a_good_match(tmp_path, monkeypatch):
    context = _recall(tmp_path, monkeypatch, [(_SAVE, 0.6)])
    assert context == (
        "## NeuralMind associative recall\n\n"
        "Code matching this prompt:\n"
        "- pkg/mod.py: save() L3"
    )
    assert _recall_outcomes(tmp_path) == ["injected"]


def test_prompt_recall_abstains_on_a_poor_match(tmp_path, monkeypatch):
    # Nearest neighbours always exist; a weak best match means none apply.
    assert _recall(tmp_path, monkeypatch, [(_SAVE, 0.2)]) == ""
    assert _recall_outcomes(tmp_path) == ["low_similarity"]


def test_prompt_recall_with_nothing_to_name_is_logged(tmp_path, monkeypatch):
    # A good match that maps to no file (no graph node, no metadata).
    assert _recall(tmp_path, monkeypatch, [("orphan", 0.6)]) == ""
    assert _recall_outcomes(tmp_path) == ["no_neighbors"]


def test_prompt_recall_threshold_is_configurable(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_RECALL_MIN_SIMILARITY", "0")
    assert "pkg/mod.py" in _recall(tmp_path, monkeypatch, [(_SAVE, 0.2)])
    monkeypatch.setenv("NEURALMIND_RECALL_MIN_SIMILARITY", "0.9")
    assert _recall(tmp_path, monkeypatch, [(_SAVE, 0.6)]) == ""


def test_malformed_threshold_falls_back_to_default(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_RECALL_MIN_SIMILARITY", "high")
    assert _recall(tmp_path, monkeypatch, [(_SAVE, 0.2)]) == ""
    assert "pkg/mod.py" in _recall(tmp_path, monkeypatch, [(_SAVE, 0.6)])


def test_no_learn_logs_no_recall_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_NO_LEARN", "1")
    assert "pkg/mod.py" in _recall(tmp_path, monkeypatch, [(_SAVE, 0.6)])
    assert not (tmp_path / ".neuralmind" / "metrics").exists()


def test_unknown_action_is_noop(tmp_path):
    rc, captured = _run("not-a-real-action", {"cwd": str(tmp_path)})
    assert rc == 0
    assert captured == ""
