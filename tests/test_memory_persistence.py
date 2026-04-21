"""End-to-end proof that the memory + learning pipeline persists.

Catches regressions where a refactor silently breaks:

- Event logging to ``.neuralmind/memory/query_events.jsonl``
- Cooccurrence index construction
- Writing ``.neuralmind/learned_patterns.json``
- Applying the learned patterns on the next query

We don't assert a specific numerical uplift (too noisy on a small
fixture). We assert the **mechanism** — files grow, patterns load,
reranking runs — which is what an end user depends on.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sample_project"
GRAPH_JSON = FIXTURE_DIR / "graphify-out" / "graph.json"

SEED_QUERIES = [
    "How does the JWT token get signed?",
    "Where is password hashing done?",
    "How do I charge a customer?",
    "What happens if a Stripe charge fails?",
    "How do I issue a partial refund?",
]


@pytest.fixture(scope="module", autouse=True)
def require_fixture_graph():
    if not GRAPH_JSON.exists():
        pytest.skip(
            f"Fixture graph missing at {GRAPH_JSON}. "
            "Run `graphify update tests/fixtures/sample_project` first."
        )


@pytest.fixture
def clean_project_memory():
    """Wipe project-local memory before and after the test."""
    mem_dir = FIXTURE_DIR / ".neuralmind"
    if mem_dir.exists():
        shutil.rmtree(mem_dir)
    yield mem_dir
    if mem_dir.exists():
        shutil.rmtree(mem_dir)


def test_query_events_are_persisted(clean_project_memory):
    """Every query should append one line to the project event log."""
    from neuralmind import NeuralMind, memory

    memory.write_consent_sentinel(True)
    nm = NeuralMind(str(FIXTURE_DIR))

    for q in SEED_QUERIES:
        nm.query(q)

    events_file = memory.project_query_events_file(FIXTURE_DIR)
    assert events_file.exists(), (
        f"Expected {events_file} to exist after queries. "
        "log_query_event may have been short-circuited or the memory dir path changed."
    )

    lines = [ln for ln in events_file.read_text().splitlines() if ln.strip()]
    assert len(lines) == len(SEED_QUERIES), (
        f"Expected {len(SEED_QUERIES)} events, got {len(lines)}. "
        "Events are being dropped — check is_memory_logging_enabled and log_query_event."
    )

    # Each line should be a valid JSON event with at least the fields the
    # reranker needs downstream.
    for ln in lines:
        event = json.loads(ln)
        assert "question" in event or "query" in event, f"event missing question/query: {event}"


def test_learn_builds_and_writes_patterns(clean_project_memory):
    """neuralmind learn must produce a readable patterns file."""
    from neuralmind import NeuralMind, memory

    memory.write_consent_sentinel(True)
    nm = NeuralMind(str(FIXTURE_DIR))

    for q in SEED_QUERIES:
        nm.query(q)

    events = memory.read_query_events(memory.project_query_events_file(FIXTURE_DIR))
    assert events, "Events should have been logged before learning runs."

    index = memory.build_cooccurrence_index(events)
    patterns_file = memory.write_learned_patterns(str(FIXTURE_DIR), index)

    assert patterns_file.exists(), f"write_learned_patterns did not create {patterns_file}"
    data = json.loads(patterns_file.read_text())
    assert isinstance(data, dict), f"patterns file is not a JSON object: {type(data).__name__}"
    # The exact schema is an internal detail we don't want to pin down —
    # assert only that it's non-empty and structured. If the schema
    # changes, downstream users notice; this test is about persistence.
    assert data, "patterns file is empty — cooccurrence pipeline produced nothing"


def test_learned_patterns_load_on_next_query(clean_project_memory):
    """After learn, a subsequent query should run without errors and produce context.

    This verifies the reranker picks up the learned patterns file
    without tripping. We intentionally don't assert ranked-order changes
    because that's noisy on a small fixture; the assertion is simply
    that the pipeline completes cleanly end-to-end.
    """
    from neuralmind import NeuralMind, memory

    memory.write_consent_sentinel(True)
    nm = NeuralMind(str(FIXTURE_DIR))

    for q in SEED_QUERIES:
        nm.query(q)

    events = memory.read_query_events(memory.project_query_events_file(FIXTURE_DIR))
    memory.write_learned_patterns(str(FIXTURE_DIR), memory.build_cooccurrence_index(events))

    # New NeuralMind instance — forces a fresh load of learned patterns.
    nm2 = NeuralMind(str(FIXTURE_DIR))
    result = nm2.query("How does authentication work?")

    assert result.context, "Query after learning returned empty context."
    assert result.budget.total > 0, "Query after learning reported zero tokens."
